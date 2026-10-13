import copy
import threading
import pytest
from test_pipeline import media,new_project,client
import main
from ai_director import AIError
from automatic_director import fallback_direction,SceneChoice,PlanningError,automatic_direction
from editing import length,probe


def speech_plan(media):
    p=new_project(media);aid=p['video']['asset_id']
    words=[{'word':' Chào','start':.5,'end':.8},{'word':' bạn.','start':.8,'end':1.2}]
    p['edit_plan']['subtitles']=[{'id':'s','asset_id':aid,'start':.5,'end':1.2,'text':'Chào bạn.','words':words}]
    main.save_project(p['id'],p)
    return p


def test_source_fallback_preserves_words_duration_and_user_preferences(media):
    p=speech_plan(media);source=copy.deepcopy(p['edit_plan'])
    result=fallback_direction(source,'không zoom',threading.Event(),'AI_TIMEOUT')
    assert result['recognition_subtitles']==source['subtitles']
    assert [(w['start'],w['end']) for w in result['subtitles'][0]['words']]==[(.5,.8),(.8,1.2)]
    assert length(result)==4 and not result['effect_keyframes']
    assert result['director']['engine']=='rules' and source==p['edit_plan']
    hidden=fallback_direction(source,'không chữ',threading.Event(),'AI_TIMEOUT')
    assert hidden['show_captions'] is False and all(not s['headline'] for s in hidden['storyboard'])


@pytest.mark.parametrize('code',['AI_TIMEOUT','AI_CONNECTION','AI_OUTPUT_LIMIT','AI_STREAM_INCOMPLETE','AI_PLAN_INVALID'])
def test_ai_failure_exports_real_fallback_video_and_keeps_previous_bytes(media,monkeypatch,code):
    p=speech_plan(media)
    previous=main.OUTPUTS_DIR/'fallback-previous.mp4';previous.write_bytes(media[0].read_bytes())
    p['output_path']='/outputs/fallback-previous.mp4';p['output_revision']=p['revision'];main.save_project(p['id'],p)
    def fail(*args):raise PlanningError('bad plan') if code=='AI_PLAN_INVALID' else AIError(code,'test failure')
    monkeypatch.setattr(main,'automatic_direction',fail)
    r=client.post(f'/api/projects/{p["id"]}/make-video',json={});assert r.status_code==200
    result=client.get(f'/api/projects/{p["id"]}').json()
    assert result['job']['status']=='succeeded',result['job']
    assert result['job']['planning_mode']=='fallback' and result['job']['fallback_reason']==code
    assert result['job']['warnings'] and result['edit_plan']['director']['engine']=='rules'
    assert result['output_path']!=p['output_path'] and previous.read_bytes()==media[0].read_bytes()
    assert probe(main.OUTPUTS_DIR/result['output_path'].split('/')[-1])['duration']==pytest.approx(4,abs=.06)


def test_cancel_never_falls_back_or_renders(media,monkeypatch):
    p=speech_plan(media)
    def cancel(plan,prompt,assets,work,event,*args):
        event.set();raise AIError('AI_TIMEOUT','cancel race')
    monkeypatch.setattr(main,'automatic_direction',cancel)
    monkeypatch.setattr(main,'fallback_direction',lambda *args:pytest.fail('fallback after cancel'))
    monkeypatch.setattr(main,'compile_storyboard_scenes',lambda *args,**kwargs:pytest.fail('render after cancel'))
    client.post(f'/api/projects/{p["id"]}/make-video',json={})
    result=client.get(f'/api/projects/{p["id"]}').json()
    assert result['job']['status']=='cancelled'


def test_renderer_failure_is_not_fallback_success(media,monkeypatch):
    p=speech_plan(media)
    def fail(*args):raise AIError('AI_TIMEOUT','test')
    def render(*args,**kwargs):raise OSError('disk full')
    monkeypatch.setattr(main,'automatic_direction',fail)
    monkeypatch.setattr(main,'compile_storyboard_scenes',render)
    client.post(f'/api/projects/{p["id"]}/make-video',json={})
    result=client.get(f'/api/projects/{p["id"]}').json()
    assert result['job']['status']=='failed' and 'disk full' in result['job']['error']
    assert not result.get('output_path')


def test_fallback_retains_valid_ai_choices_but_source_captions(media):
    p=speech_plan(media);event=threading.Event()
    event.ai_valid_choices={0:SceneChoice(scene_index=0,scene_type='talking_head_pip',headline='CHÀO BẠN',
        badge_text='',graphic_kind='chat',graphic_title='Chào bạn',graphic_items=['Chào','Bạn'],
        sound_effect='none',caption_text='Wrong caption')}
    result=fallback_direction(p['edit_plan'],'Giữ lời',event,'AI_TIMEOUT')
    assert result['storyboard'][0]['scene_type']=='talking_head_pip'
    assert result['subtitles'][0]['text']=='Chào bạn.'
    assert result['director']['retained_ai_scene_indices']==[0]


def test_retry_reuses_recognition_and_recomputes_prompt(media,monkeypatch):
    p=speech_plan(media);calls=[]
    def fail(plan,prompt,*args):calls.append(prompt);raise AIError('AI_TIMEOUT','test')
    monkeypatch.setattr(main,'automatic_direction',fail)
    monkeypatch.setattr(main,'transcribe',lambda *args:pytest.fail('recognition should be reused'))
    for prompt in ['không phụ đề','có phụ đề']:
        client.post(f'/api/projects/{p["id"]}/make-video',json={'prompt':prompt})
        result=client.get(f'/api/projects/{p["id"]}').json()
        assert result['job']['status']=='succeeded',result['job']
    assert calls==['không phụ đề','có phụ đề']
    assert result['edit_plan']['show_captions'] is True


def test_compact_ai_response_expands_to_existing_storyboard(media,tmp_path,monkeypatch):
    import automatic_director
    p=speech_plan(media)
    raw='{"summary":"Giữ lời nói","scenes":[{"i":0,"t":"talking_head","h":"Chào bạn","z":1.04}]}'
    monkeypatch.setattr(automatic_director,'chat',lambda *args:raw)
    result=automatic_direction(p['edit_plan'],'Giữ lời',main.ASSETS_DIR,tmp_path,threading.Event())
    assert result['director']['engine']=='ollama'
    scene=result['storyboard'][0]
    assert scene['scene_index']==0 and scene['scene_type']=='talking_head'
    assert 'i' not in scene and scene['headline']=='CHÀO BẠN'
    assert result['subtitles'][0]['text']=='Chào bạn.'


def test_deadline_after_valid_ai_uses_raw_source_for_fallback(media,monkeypatch):
    p=speech_plan(media);source=p['edit_plan']['subtitles']
    monkeypatch.setenv('VIDEO_AUTO_AI_TIMEOUT','.0001')
    def slow_result(plan,*args):
        import time
        result=copy.deepcopy(plan);result['subtitles'][0]['text']='Wrong rewritten speech';time.sleep(.01)
        return result
    monkeypatch.setattr(main,'automatic_direction',slow_result)
    client.post(f'/api/projects/{p["id"]}/make-video',json={})
    result=client.get(f'/api/projects/{p["id"]}').json()
    assert result['job']['status']=='succeeded',result['job']
    assert result['edit_plan']['recognition_subtitles']==source
    assert result['edit_plan']['subtitles'][0]['text']=='Chào bạn.'


def test_neutral_introduction_does_not_trigger_endless_graphic_repair():
    from automatic_director import unsupported_graphic_words
    choice=SceneChoice(scene_index=0,scene_type='explainer_card',headline='TRỢ LÝ AI',badge_text='',
        graphic_kind='chat',graphic_title='Giới thiệu AI',graphic_items=['AI','Trợ lý'],sound_effect='none')
    assert unsupported_graphic_words(choice,{'ai','trợ','lý'})==[]
    choice.graphic_items=['AI đầu tiên','Tối ưu thuật toán']
    assert unsupported_graphic_words(choice,{'ai','trợ','lý'})


def test_graphic_labels_are_source_excerpts_and_schema_constrains_them(media,tmp_path,monkeypatch):
    import automatic_director
    p=speech_plan(media);seen=[]
    def reply(messages,event,schema):
        seen.append(schema['$defs']['GraphicWire']['properties'])
        return '{"summary":"Giữ nguồn","scenes":[{"i":0,"t":"talking_head","h":"Chào bạn"}]}'
    monkeypatch.setattr(automatic_director,'chat',reply)
    automatic_direction(p['edit_plan'],'Giữ lời',main.ASSETS_DIR,tmp_path,threading.Event())
    labels=seen[0]['items']['items']['enum']
    assert 'Chào bạn' in labels and 'Giới thiệu' in labels
    assert '' not in seen[0]['g']['enum']
    assert seen[0]['items']['minItems']==2
    assert 'AI đầu tiên' not in labels


def test_layout_preserves_camera_and_limits_repetitive_graphics():
    from automatic_director import balance_graphics
    texts=['Mở đầu','Trợ lý AI','Thử nghiệm AI','Chiến lược thương hiệu','Thông điệp doanh nghiệp','Kết thúc']
    units=[{'scene_index':i,'text':text} for i,text in enumerate(texts)]
    choices={i:SceneChoice(scene_index=i,scene_type='talking_head_pip',headline=text,badge_text='',
        graphic_kind='network' if i==3 else 'chat',graphic_title=text,graphic_items=text.split(),sound_effect='none')
        for i,text in enumerate(texts)}
    balance_graphics(choices,units,'Minh họa sinh động',37)
    graphics=[i for i,c in choices.items() if c.scene_type!='talking_head']
    assert len(graphics)==2 and 0 not in graphics and 5 not in graphics
    assert any(c.scene_type=='explainer_card' for c in choices.values())
    assert all(c.sound_effect=='none' for c in choices.values() if c.scene_type=='talking_head')
