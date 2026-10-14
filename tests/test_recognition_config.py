import copy,hashlib,sys,types
import pytest
from recognition_config import name_hint,recognition_config,cache_changed
from test_pipeline import media,new_project,client
import main


def test_hints_only_use_current_canonical_names():
    assert name_hint('DANAVA Solutions','AN NA | Anna\nDANAVA Solutions | Wrong')=='DANAVA Solutions, AN NA'
    assert 'Wrong' not in name_hint('', 'Correct | Wrong')
    assert len(name_hint('Brand','x'*600))<=300


def test_cache_identity_changes_with_model_source_or_hint(media,monkeypatch):
    p=new_project(media)['edit_plan']
    a=recognition_config(p,'faster_whisper','Brand','Name | Old')
    p['recognition_cache']=a
    assert not cache_changed(p,a)
    assert not cache_changed(p,recognition_config(p,'faster_whisper','Brand','Name | Different alias'))
    assert cache_changed(p,recognition_config(p,'faster_whisper','Other brand','Name'))
    monkeypatch.setenv('WHISPER_MODEL','base')
    assert cache_changed(p,recognition_config(p,'faster_whisper','Brand','Name'))
    p['user_subtitles']=[];assert not cache_changed(p,recognition_config(p,'whisper'))
    p.pop('recognition_cache');assert not cache_changed(p,a)


def test_upload_hash_and_readonly_name_draft_persist_only_after_save(media):
    p=new_project(media);asset=p['edit_plan']['assets'][0]
    assert asset['sha256']==hashlib.sha256(media[0].read_bytes()).hexdigest()
    draft=[{'asset_id':p['video']['asset_id'],'start':0,'end':4,'text':'Dannava Solution hỗ trợ Anna.','words':[{'word':'old','start':0,'end':4}]}]
    body={'revision':p['revision'],'brand_name':'DANAVA Solutions','proper_names':'AN NA | Anna','subtitles':draft}
    r=client.post(f'/api/projects/{p["id"]}/subtitle-name-draft',json=body)
    assert r.status_code==200;r=r.json();assert not r['saved']
    assert r['subtitles'][0]['text']=='DANAVA Solutions hỗ trợ AN NA.' and not r['subtitles'][0].get('words')
    untouched=client.get(f'/api/projects/{p["id"]}').json();assert untouched==p
    assert client.post(f'/api/projects/{p["id"]}/subtitle-name-draft',json={**body,'revision':-1}).status_code==409
    assert client.post(f'/api/projects/{p["id"]}/subtitle-name-draft',json={**body,'subtitles':[{'text':3}]}).status_code==422
    plan=copy.deepcopy(p['edit_plan']);plan['subtitles']=r['subtitles']
    saved=client.post(f'/api/projects/{p["id"]}/edit_plan',json={'revision':p['revision'],'plan':plan}).json()
    assert saved['edit_plan']['user_subtitles'][0]['text']==r['subtitles'][0]['text']


def test_draft_respects_unrelated_words_and_preserves_timing(media):
    p=new_project(media);row={'text':'Anh An đang nói về một solution.','start':0,'end':4}
    r=client.post(f'/api/projects/{p["id"]}/subtitle-name-draft',json={'revision':p['revision'],'brand_name':'DANAVA Solutions','proper_names':'AN NA | Anna','subtitles':[row]}).json()
    assert r['changes']==[] and r['subtitles']==[row]


def test_client_cannot_spoof_recognition_key(media):
    p=new_project(media);plan=copy.deepcopy(p['edit_plan']);plan['recognition_cache']={'asset_id':'someone-else'}
    r=client.post(f'/api/projects/{p["id"]}/edit_plan',json={'revision':p['revision'],'plan':plan}).json()
    assert 'recognition_cache' not in r['edit_plan']


def test_transcribe_passes_hint_and_reloads_changed_model(media,tmp_path,monkeypatch):
    p=new_project(media);plan=p['edit_plan'];plan.update(brand_footer='Brand',proper_names='Name | Wrong')
    p['job']={'status':'running'};main.save_project(p['id'],p)
    instances=[]
    class FakeWhisper:
        def __init__(self,name,**kw):instances.append(name)
        def transcribe(self,data,**kw):
            assert kw['initial_prompt']=='Brand, Name'
            return iter([]),None
    monkeypatch.setitem(sys.modules,'faster_whisper',types.SimpleNamespace(WhisperModel=FakeWhisper))
    monkeypatch.setattr(main,'recognition_engine',lambda:'faster_whisper')
    monkeypatch.setattr(main,'MODEL',None);monkeypatch.setattr(main,'MODEL_KEY',None)
    for name in ['small','small','base']:
        monkeypatch.setenv('WHISPER_MODEL',name);main.transcribe(plan,tmp_path,p['id'])
    assert instances==['small','base']


def test_real_retry_invalidates_changed_hint_but_reuses_identical_config(media,monkeypatch):
    import ai_director,automatic_director
    calls=[]
    p=new_project(media);aid=p['video']['asset_id']
    def recognize(plan,work,identifier):
        calls.append(name_hint(plan.get('brand_footer',''),plan.get('proper_names','')))
        return [{'id':'asr','asset_id':aid,'start':0,'end':4,'text':'Nguồn nhận dạng hiện tại.'}]
    def unavailable(*a):raise ai_director.AIError('AI_CONNECTION','Controlled unavailable AI')
    monkeypatch.setattr(main,'transcribe',recognize)
    monkeypatch.setattr(automatic_director,'automatic_direction',unavailable)
    monkeypatch.setattr(main,'automatic_direction',unavailable)
    body={'brand_name':'Brand','proper_names':'Name | Wrong','illustrations':False}
    for proper in ['Name | Wrong','Name | Other alias','Different name | Wrong']:
        r=client.post(f'/api/projects/{p["id"]}/make-video',json={**body,'proper_names':proper});assert r.status_code==200,r.text
        latest=client.get(f'/api/projects/{p["id"]}').json();assert latest['job']['status']=='succeeded',latest['job']
    assert calls==['Brand, Name','Brand, Different name']
    assert latest['edit_plan']['recognition_cache']['hint_sha256']==hashlib.sha256(calls[-1].encode()).hexdigest()


def test_real_browser_headline_keeps_two_lines_with_selected_font(tmp_path):
    import json,subprocess
    from typography import PROFILES,font_path
    from text_review import headline_layout
    profile=PROFILES['business']
    title,size=headline_layout('XÂY DỰNG THƯƠNG HIỆU HIỆU QUẢ',60,590,font_path=font_path(profile,'heading'))
    cfg={'scene_type':'explainer_card','headline':title,'headline_font_size':size,'duration':.3,
         'motion_style':'dynamic_explainer','motion':{'animate':False},
         'heading_font_file':profile['heading_file'],'caption_font_file':profile['caption_file'],
         'heading_weight':profile['heading_weight'],'caption_weight':profile['caption_weight']}
    source=tmp_path/'scene.json';source.write_text(json.dumps(cfg));out=tmp_path/'title.mp4'
    r=subprocess.run(['node',str(main.BASE_DIR/'motion_engine/render_scene.js'),'--input',str(source),'--output',str(out),'--width','360','--height','640','--fps','10'],capture_output=True,text=True)
    assert r.returncode==0,r.stderr
    record=next(json.loads(line) for line in r.stdout.splitlines() if 'title_layout' in line)
    assert record['title_layout'][0]['lines']<=2
    subprocess.run(['ffmpeg','-v','error','-xerror','-i',str(out),'-f','null','-'],check=True)


def test_diagram_labels_cannot_borrow_from_other_scene():
    from automatic_director import SceneChoice,scene_graphic_errors
    choice=SceneChoice(scene_index=1,scene_type='explainer_card',headline='Thương hiệu',badge_text='',graphic_kind='network',graphic_title='Trợ lý AI',graphic_items=['DANAVA Solutions','Trợ lý AI'],sound_effect='none')
    unit={'text':'Xây dựng thương hiệu bằng chiến lược truyền thông.'}
    global_vocabulary=set('trợ lý ai danava solutions xây dựng thương hiệu bằng chiến lược truyền thông'.split())
    assert scene_graphic_errors(choice,unit,global_vocabulary)
    choice.graphic_title='Thương hiệu';choice.graphic_items=['Thương hiệu','Chiến lược']
    assert not scene_graphic_errors(choice,unit,global_vocabulary)


def test_repair_schema_excludes_unanchored_greetings(media,tmp_path,monkeypatch):
    import json,threading
    import automatic_director
    p=new_project(media)['edit_plan'];p['subtitles']=[{'start':0,'end':4,'text':'Thương hiệu và chiến lược.'}]
    calls=[]
    def reply(messages,event,schema):
        calls.append(schema)
        if len(calls)>1:
            allowed=schema['$defs']['GraphicWire']['properties']['g']['enum']
            assert 'Giới thiệu' not in allowed and 'Chào bạn' not in allowed
        return json.dumps({'summary':'Sơ đồ đúng cảnh','scenes':[{'i':0,'t':'explainer_card','h':'Thương hiệu','k':'network','g':'Giới thiệu' if len(calls)==1 else 'Thương hiệu','items':['Thương hiệu','Chiến lược']}]})
    monkeypatch.setattr(automatic_director,'chat',reply)
    result=automatic_director.automatic_direction(p,'Minh họa theo nguồn',main.ASSETS_DIR,tmp_path,threading.Event())
    assert len(calls)==2 and result['director']['engine']=='ollama'
    assert result['storyboard'][0]['graphic_title']=='Thương hiệu'


def test_graphic_adapter_drops_duplicates_and_foreign_chat_labels():
    from automatic_director import normalize_graphic_items
    words=set('thương hiệu chiến lược trợ lý ai an na'.split())
    assert normalize_graphic_items(['thương hiệu','THƯƠNG HIỆU!','thương hiệu'],'chiến lược','network',words)==['thương hiệu','chiến lược']
    assert normalize_graphic_items(['trợ lý AI','dựng thương','trợ lý'],'AN NA','chat',set('trợ lý ai an na'.split()))==['trợ lý AI','trợ lý']
    assert normalize_graphic_items(['thương hiệu'],'ưu đãi 99%','network',words)==['thương hiệu']


def test_export_defaults_to_saved_motion_profile_and_respects_override(media,monkeypatch):
    p=new_project(media);p['edit_plan']['render_profile']='explainer_ref'
    p['edit_plan']['storyboard']=[{'scene_type':'talking_head','timeline_start':0,'duration':4,'headline':'Giữ bố cục đã chọn'}]
    main.save_project(p['id'],p);seen=[]
    actual=main.compile_storyboard_scenes
    def motion(*args,**kwargs):seen.append('motion');return actual(*args,**kwargs)
    monkeypatch.setattr(main,'compile_storyboard_scenes',motion)
    for body in ({},{'visual_style':'clean_expert'}):
        r=client.post(f'/api/projects/{p["id"]}/export',json=body);assert r.status_code==200,r.text
        latest=client.get(f'/api/projects/{p["id"]}').json();assert latest['job']['status']=='succeeded',latest['job']
    assert seen==['motion']


def test_chat_labels_do_not_borrow_unrelated_words_from_brief(media,tmp_path,monkeypatch):
    import json,threading,automatic_director
    p=new_project(media)['edit_plan'];p['subtitles']=[{'start':0,'end':4,'text':'Bạn trợ lý AI tên AN NA.'}]
    def reply(*args):
        return json.dumps({'summary':'Minh họa trợ lý','scenes':[{'i':0,'t':'talking_head_pip','h':'Trợ lý AI','k':'chat','g':'AN NA','items':['trợ lý AI','dựng thương','trợ lý']}]})
    monkeypatch.setattr(automatic_director,'chat',reply)
    result=automatic_director.automatic_direction(p,'Minh họa trợ lý AN NA. Xây dựng thương hiệu.',main.ASSETS_DIR,tmp_path,threading.Event())
    assert result['storyboard'][0]['graphic_items']==['trợ lý AI','trợ lý']
    assert result['director']['normalized_label_scene_indices']==[0]
