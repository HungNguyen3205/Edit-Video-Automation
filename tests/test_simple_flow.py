import json
import threading
import pytest
from test_pipeline import media,new_project,client,save
import automatic_director
import ai_director
import main
from automatic_director import semantic_units,automatic_direction
from editing import length,probe


def test_units_cover_source_without_model_timing(media):
    plan=new_project(media)['edit_plan']
    plan['subtitles']=[{'start':0,'end':4,'text':'Chào mọi người. Giữ toàn bộ nội dung này.'}]
    units=semantic_units(plan)
    assert units[0]['start']==0 and units[-1]['end']==4
    assert sum(u['end']-u['start'] for u in units)==4
    assert all(a['end']==b['start'] for a,b in zip(units,units[1:]))


def test_ai_selects_content_but_cannot_shorten_video(media,tmp_path,monkeypatch):
    plan=new_project(media)['edit_plan']
    plan['subtitles']=[{'start':0,'end':4,'text':'Giới thiệu trợ lý AI giúp truyền thông.'}]
    seen=[]
    def reply(messages,event,schema):
        seen.append(json.loads(messages[1]['content']))
        assert schema['properties']['scenes']['minItems']==len(seen[-1]['scenes'])
        assert schema['properties']['scenes']['maxItems']==len(seen[-1]['scenes'])
        assert schema['$defs']['CameraWire']['properties']['i']['enum']==list(range(len(seen[-1]['scenes'])))
        return json.dumps({'summary':'Thẻ trợ lý','scenes':[
            {'scene_index':u['scene_index'],'scene_type':'explainer_card','headline':'TRỢ LÝ AI','badge_text':'AI','graphic_kind':'chat','graphic_title':'AI','graphic_items':['Chào bạn!','Bạn cần hỗ trợ gì?'],'sound_effect':'pop','caption_text':u['text']}
            for u in seen[-1]['scenes']]})
    monkeypatch.setattr(automatic_director,'chat',reply)
    result=automatic_direction(plan,'Làm đẹp, đừng cắt lời',main.ASSETS_DIR,tmp_path,threading.Event())
    assert seen[0]['brief']=='Làm đẹp, đừng cắt lời'
    assert length(result)==4 and sum(s['duration'] for s in result['storyboard'])==4
    assert result['storyboard'][0]['headline']=='TRỢ LÝ AI'


def test_missing_scene_is_repaired_not_replaced_with_rules(media,tmp_path,monkeypatch):
    plan=new_project(media)['edit_plan'];calls=[]
    def reply(messages,event,schema):
        calls.append(messages[-1]['content'])
        return json.dumps({'summary':'Dựng','scenes':[{'scene_index':9 if len(calls)==1 else 0,'scene_type':'talking_head','headline':'','badge_text':'','graphic_title':'','graphic_kind':'network','graphic_items':[],'sound_effect':'none','caption_text':''}]})
    monkeypatch.setattr(automatic_director,'chat',reply)
    result=automatic_direction(plan,'Giữ giọng',main.ASSETS_DIR,tmp_path,threading.Event())
    assert len(calls)==2 and 'exactly once' in calls[1]
    assert result['storyboard'][0]['duration']==4


def test_screenshot_zoom_14_is_safely_bounded(media,tmp_path,monkeypatch):
    p=new_project(media)
    raw={'summary':'Zoom nhẹ','cuts':[{'start':0,'end':4}],'zooms':[{'start':0,'duration':2,'scale':1.4}]}
    monkeypatch.setattr(ai_director,'chat',lambda *args:json.dumps(raw))
    result=ai_director.direct(p['edit_plan'],'Nhấn nhẹ',main.ASSETS_DIR,tmp_path,threading.Event())
    assert result['effect_keyframes'][0]['scale']==1.2
    assert any('1.2' in w for w in result['director']['warnings'])


def test_one_button_endpoint_defaults_and_real_export(media,monkeypatch):
    p=new_project(media)
    plan=p['edit_plan'];aid=p['video']['asset_id']
    plan['subtitles']=[{'id':'speech','asset_id':aid,'start':0,'end':4,'text':'Trợ lý AI hỗ trợ công việc.'}]
    plan['recognition_subtitles']=[dict(plan['subtitles'][0])]
    plan['subtitles'][0]['text']='Phụ đề bị sửa sai từ lần dựng trước.'
    p=save(p,plan)
    monkeypatch.setattr(main,'ai_health',lambda:{'available':True,'model':'fixture'})
    seen=[]
    def reply(messages,event,schema):
        data=json.loads(messages[1]['content']);seen.append(data)
        return json.dumps({'summary':'Thẻ minh họa','scenes':[{'scene_index':u['scene_index'],'scene_type':'explainer_card',
            'headline':'TRỢ LÝ AI','badge_text':'AI','graphic_kind':'chat','graphic_title':'AI','graphic_items':['Ý tưởng mới','Bạn cần hỗ trợ gì?'],'sound_effect':'pop','caption_text':u['text']} for u in data['scenes']]})
    monkeypatch.setattr(automatic_director,'chat',reply)
    response=client.post(f'/api/projects/{p["id"]}/make-video',json={'prompt':''})
    assert response.status_code==200,response.text
    result=client.get(f'/api/projects/{p["id"]}').json()
    assert result['job']['status']=='succeeded',result['job']
    assert not result['job']['preview']
    assert result['edit_plan']['director']['user_prompt']==''
    assert seen[0]['brief'] and result['edit_plan']['render_profile']=='explainer_ref'
    assert seen[0]['scenes'][0]['text']=='Trợ lý AI hỗ trợ công việc.'
    output=main.OUTPUTS_DIR/result['output_path'].split('/')[-1]
    meta=probe(output)
    assert meta['duration']==pytest.approx(4,abs=.06)
    assert (meta['width'],meta['height'])==(720,1280)


def test_simple_endpoint_requires_source_and_labels_missing_ai_fallback(media,monkeypatch):
    empty=client.post('/api/projects',data={'name':'Empty'}).json()
    assert client.post(f'/api/projects/{empty["id"]}/make-video',json={}).status_code==422
    p=new_project(media)
    monkeypatch.setattr(main,'ai_health',lambda:{'available':False,'model':'qwen3:4b'})
    monkeypatch.setattr(automatic_director,'chat',lambda *args: (_ for _ in ()).throw(ai_director.AIError('AI_CONNECTION','Ollama unavailable')))
    monkeypatch.setattr(main,'transcribe',lambda *args:[])
    response=client.post(f'/api/projects/{p["id"]}/make-video',json={'prompt':'Đẹp hơn'})
    assert response.status_code==200
    result=client.get(f'/api/projects/{p["id"]}').json()
    assert result['job']['status']=='succeeded',result['job']
    assert result['job']['planning_mode']=='fallback'
    assert result['edit_plan']['director']['engine']=='rules'


def test_simple_endpoint_automatically_skips_recognition_for_silent_source(media,monkeypatch):
    p=client.post('/api/projects',data={'name':'Silent'}).json()
    with media[1].open('rb') as f:
        p=client.post(f'/api/projects/{p["id"]}/upload',files={'file':('silent.mp4',f)},data={'role':'main'}).json()
    captured=[]
    monkeypatch.setattr(main,'enqueue',lambda pid,bg,options,mode:captured.append(options) or p)
    assert client.post(f'/api/projects/{p["id"]}/make-video',json={'prompt':'Thêm chữ'}).status_code==200
    assert not captured[0].transcribe and captured[0].automatic and not captured[0].preview


def test_automatic_zoom_over_limit_is_clamped_and_no_captions_is_respected(media,tmp_path,monkeypatch):
    plan=new_project(media)['edit_plan']
    raw={'summary':'Nhấn nhẹ','captions':False,'scenes':[{'scene_index':0,'scene_type':'talking_head','headline':'','badge_text':'','graphic_title':'','zoom_scale':1.4,'graphic_kind':'network','graphic_items':[],'sound_effect':'none','caption_text':''}]}
    monkeypatch.setattr(automatic_director,'chat',lambda *args:json.dumps(raw))
    result=automatic_direction(plan,'Zoom nhẹ và không phụ đề',main.ASSETS_DIR,tmp_path,threading.Event())
    assert result['effect_keyframes'][0]['scale']==1.2
    assert result['show_captions'] is False


def test_caption_spelling_keeps_word_timing_and_names_are_user_supplied():
    from automatic_director import aligned_words,correct_recognition_copy
    text=correct_recognition_copy('Dannava và Anna xây dựng thân hiệu','Video DANAVA và AN NA')
    assert text=='DANAVA và AN NA xây dựng thương hiệu'
    assert correct_recognition_copy('Một trợ lý của nơi khác','Video DANAVA')=='Một trợ lý của nơi khác'
    words=[{'word':' thân','start':2,'end':2.4},{'word':' hiệu','start':2.4,'end':2.8}]
    mapped=aligned_words(words,'thương hiệu',0,4)
    assert [(w['start'],w['end']) for w in mapped]==[(2,2.4),(2.4,2.8)]
    assert aligned_words([], 'Đây là phụ đề không có word alignment', 0, 4)==[]


def test_style_displays_ai_authored_concepts_when_camera_plan_has_illustrations(media,tmp_path,monkeypatch):
    # Pure contract fixture; no media is rendered in this test.
    plan=new_project(media)['edit_plan'];plan['assets'][0]['metadata']['duration']=12
    plan['video_clips'][0]['duration']=12
    plan['subtitles']=[{'start':0,'end':12,'text':'Giới thiệu trợ lý AI giúp truyền tải thông điệp.'}]
    calls=[]
    def reply(messages,event,schema):
        calls.append(messages[-1]['content'])
        context=json.loads(messages[1]['content'])
        return json.dumps({'summary':'Minh họa','scenes':[{'scene_index':u['scene_index'],
            'scene_type':'talking_head' if len(calls)==1 else 'explainer_card',
            'headline':'TRỢ LÝ AI','badge_text':'Ý CHÍNH','graphic_title':'AI','graphic_kind':'chat',
            'graphic_items':['Chào bạn','Bạn cần hỗ trợ gì?'],'sound_effect':'pop','caption_text':u['text']}
            for u in context['scenes']]})
    monkeypatch.setattr(automatic_director,'chat',reply)
    result=automatic_direction(plan,'Chèn minh họa sinh động',main.ASSETS_DIR,tmp_path,threading.Event())
    assert len(calls)==1
    assert any(s['scene_type']!='talking_head' for s in result['storyboard'])
    assert result['director']['layout_adjustments']


def test_model_cannot_move_or_replace_speech_captions(media,tmp_path,monkeypatch):
    plan=new_project(media)['edit_plan']
    source='Giới thiệu trợ lý AI hỗ trợ công việc.'
    plan['subtitles']=[{'start':0,'end':4,'text':source}]
    raw={'summary':'Trợ lý AI','scenes':[{'scene_index':0,'scene_type':'talking_head',
        'headline':'TRỢ LÝ AI','badge_text':'AI','graphic_kind':'chat','graphic_title':'',
        'graphic_items':[],'sound_effect':'none','caption_text':'Mua ngay hôm nay với giá đặc biệt!'}]}
    monkeypatch.setattr(automatic_director,'chat',lambda *args:json.dumps(raw))
    result=automatic_direction(plan,'Dựng rõ ràng',main.ASSETS_DIR,tmp_path,threading.Event())
    assert result['subtitles'][0]['text']==source
    assert result['recognition_subtitles']==plan['subtitles']
    assert result['director']['warnings'] and length(result)==4


@pytest.mark.parametrize('full_response',[False,True])
def test_repair_only_incomplete_graphic_preserves_valid_scenes(media,tmp_path,monkeypatch,full_response):
    plan=new_project(media)['edit_plan'];plan['assets'][0]['metadata']['duration']=12
    plan['video_clips'][0]['duration']=12
    plan['subtitles']=[{'start':0,'end':4,'text':'Giới thiệu trợ lý AI.'},
                       {'start':4,'end':12,'text':'Trợ lý AI truyền tải thông điệp.'}]
    units=semantic_units(plan);assert len(units)==2
    def scene(index,items):
        return {'scene_index':index,'scene_type':'explainer_card','headline':'TRỢ LÝ AI',
            'badge_text':'AI','graphic_kind':'chat','graphic_title':'Trợ lý AI',
            'graphic_items':items,'sound_effect':'pop','caption_text':units[index]['text']}
    calls=[]
    def reply(messages,event,schema):
        calls.append(messages[-1]['content'])
        return json.dumps({'summary':'Minh họa','captions':False if len(calls)==1 else True,
            'scenes':[scene(0,['Chào bạn','Trợ lý AI']),scene(1,[])] if len(calls)==1
            else ([scene(0,['Không được thay thế','Cảnh đã đúng'])] if full_response else [])+[scene(1,['Thông điệp','Trợ lý AI'])]})
    monkeypatch.setattr(automatic_director,'chat',reply)
    result=automatic_direction(plan,'Thẻ minh họa, không phụ đề',main.ASSETS_DIR,tmp_path,threading.Event())
    assert len(calls)==2 and 'ONLY scene_index [1]' in calls[1]
    assert result['storyboard'][0]['graphic_items']==['Chào bạn','Trợ lý AI']
    assert result['show_captions'] is False


def test_graphics_repair_unsupported_claims_instead_of_rendering_them(media,tmp_path,monkeypatch):
    plan=new_project(media)['edit_plan']
    plan['subtitles']=[{'start':0,'end':4,'text':'Thử nghiệm trợ lý AI để truyền tải thông điệp.'}]
    calls=[]
    def reply(messages,event,schema):
        calls.append(messages[-1]['content'])
        return json.dumps({'summary':'Thử nghiệm','scenes':[{'scene_index':0,'scene_type':'explainer_card',
            'headline':'THỬ NGHIỆM AI','badge_text':'AI','graphic_kind':'process','graphic_title':'Thử nghiệm AI',
            'graphic_items':['AI đầu tiên','Tối ưu thuật toán'] if len(calls)==1 else ['Trợ lý AI','Thông điệp'],
            'sound_effect':'none','caption_text':plan['subtitles'][0]['text']}]})
    monkeypatch.setattr(automatic_director,'chat',reply)
    result=automatic_direction(plan,'Thẻ minh họa AI',main.ASSETS_DIR,tmp_path,threading.Event())
    assert len(calls)==2 and 'Unsupported words' in calls[1]
    assert result['storyboard'][0]['graphic_items']==['Trợ lý AI','Thông điệp']


def test_style_composition_uses_semantic_concepts_and_keeps_opening_and_ending():
    from automatic_director import SceneChoice,compose_requested_graphics
    texts=['Giới thiệu AN NA','Trợ lý AI AN NA','Thử nghiệm DANAVA','Xây dựng thương hiệu','Thông điệp doanh nghiệp','Tạm biệt AN NA']
    units=[{'scene_index':i,'text':t} for i,t in enumerate(texts)]
    kinds=['chat','chat','process','process','network','chat']
    choices={i:SceneChoice(scene_index=i,scene_type='talking_head',headline=t,badge_text='AI',
        graphic_kind=kinds[i],graphic_title=t,graphic_items=t.split()[:2],sound_effect='none',caption_text=t)
        for i,t in enumerate(texts)}
    vocabulary=set(' '.join(texts).casefold().split())
    adjusted=compose_requested_graphics(choices,units,'Sinh động, minh họa hội thoại và sơ đồ, không SFX',37,vocabulary,True)
    assert len(adjusted)==2 and all(i not in (0,5) for i in adjusted)
    assert choices[0].scene_type==choices[5].scene_type=='talking_head'
    assert {choices[i].scene_type for i in adjusted}=={'talking_head_pip','explainer_card'}
    assert all(choices[i].sound_effect=='none' for i in adjusted)


def test_optional_caption_copy_preserves_actual_word_timestamps(media,tmp_path,monkeypatch):
    plan=new_project(media)['edit_plan'];aid=plan['video_clips'][0]['asset_id']
    words=[{'word':' Chào','start':1,'end':1.3},{'word':' bạn.','start':1.3,'end':1.8}]
    plan['subtitles']=[{'asset_id':aid,'start':1,'end':1.8,'text':'Chào bạn.','words':words}]
    raw={'summary':'Giữ nguồn','scenes':[{'scene_index':0,'scene_type':'talking_head','headline':'',
        'badge_text':'','graphic_kind':'chat','graphic_title':'','graphic_items':[],'sound_effect':'none'}]}
    monkeypatch.setattr(automatic_director,'chat',lambda *args:json.dumps(raw))
    result=automatic_direction(plan,'Giữ lời',main.ASSETS_DIR,tmp_path,threading.Event())
    assert result['subtitles'][0]['text']=='Chào bạn.'
    assert [(w['start'],w['end']) for w in result['subtitles'][0]['words']]==[(1,1.3),(1.3,1.8)]
    assert not result['director']['warnings']


def test_repair_context_does_not_accumulate_previous_responses(media,tmp_path,monkeypatch):
    plan=new_project(media)['edit_plan'];calls=[]
    def reply(messages,event,schema):
        calls.append(len(messages))
        return json.dumps({'summary':'Giữ nguồn','scenes':[{'scene_index':0 if len(calls)==3 else 9,
            'scene_type':'talking_head','headline':'','badge_text':'','graphic_kind':'chat',
            'graphic_title':'','graphic_items':[],'sound_effect':'none'}]})
    monkeypatch.setattr(automatic_director,'chat',reply)
    automatic_direction(plan,'Giữ lời',main.ASSETS_DIR,tmp_path,threading.Event())
    assert calls==[2,4,4]
