import copy,json,threading
import pytest
import main,automatic_director
from learning_store import LearningStore
from test_pipeline import media,new_project,client
from text_review import headline_layout


def exported_project(media):
    p=new_project(media);p['job']={'status':'succeeded','planning_mode':'fallback'}
    p['output_path']='/outputs/example.mp4';p['output_revision']=p['revision']
    p['edit_plan']['storyboard']=[{'scene_type':'talking_head','headline':'PRIVATE BRAND'}]
    return p


def test_style_memory_does_not_replay_private_speech_or_brand(media,tmp_path):
    p=exported_project(media);p['edit_plan']['subtitles']=[{'text':'PRIVATE SPEECH','start':0,'end':4}]
    store=LearningStore(tmp_path);r=store.save(p,'approve_style','Zoom nhẹ.',False)
    text=json.dumps(store.context(),ensure_ascii=False);assert 'PRIVATE SPEECH' not in text and 'PRIVATE BRAND' not in text
    assert 'Zoom nhẹ.' in text and 'initial_visual_reference' in store.context()
    assert store.status()['model_weights_trained'] is False
    assert 'output_path' not in store.export()
    store.save(p,'needs_changes','Tiêu đề ngắn hơn.',False)
    assert store.status()['approved_styles']==0
    assert store.context()['approved_style_examples']==[]
    assert store.context()['requested_changes']==['Tiêu đề ngắn hơn.']


def test_feedback_guard_and_duplicate_updates(media,monkeypatch,tmp_path):
    monkeypatch.setattr(main,'DATA_DIR',tmp_path)
    p=new_project(media)
    body={'revision':p['revision'],'output_path':'/outputs/example.mp4','decision':'approve_style'}
    assert client.post(f'/api/projects/{p["id"]}/feedback',json=body).status_code==409
    p['job']={'status':'succeeded'};p['output_path']=body['output_path'];p['output_revision']=p['revision'];main.save_project(p['id'],p)
    assert client.post(f'/api/projects/{p["id"]}/feedback',json={**body,'revision':-1}).status_code==409
    assert client.post(f'/api/projects/{p["id"]}/feedback',json=body).status_code==200
    r=client.post(f'/api/projects/{p["id"]}/feedback',json={**body,'note':'Chữ ngắn hơn.'})
    assert r.status_code==200 and r.json()['learning']['approved_styles']==1
    assert json.loads(client.get('/api/learning/export').text)['note']=='Chữ ngắn hơn.'
    p['edit_plan']['subtitle_review']=[{'reason':'Hear again'}];main.save_project(p['id'],p)
    assert client.post(f'/api/projects/{p["id"]}/feedback',json={**body,'captions_checked':True}).status_code==422
    assert client.post(f'/api/projects/{p["id"]}/feedback',json=body).status_code==200


def test_ai_receives_bounded_style_memory_and_current_source(media,tmp_path,monkeypatch):
    plan=new_project(media)['edit_plan'];plan['subtitles']=[{'start':0,'end':4,'text':'Nội dung hiện tại.'}]
    store=LearningStore(tmp_path);p=exported_project(media)
    for i in range(6):
        p['id']=str(i);store.save(p,'approve_style','Ưu tiên chữ rõ '+str(i),False)
    plan['learning_context']=store.context();assert len(plan['learning_context']['approved_style_examples'])==3
    seen=[]
    def chat(messages,event,schema):
        context=json.loads(messages[1]['content']);seen.append(context)
        return json.dumps({'summary':'Giữ lời','scenes':[{'i':u['scene_index'],'t':'talking_head','h':'','z':1.04} for u in context['scenes']],'captions':True})
    monkeypatch.setattr(automatic_director,'chat',chat)
    result=automatic_director.automatic_direction(plan,'Không minh họa',main.ASSETS_DIR,tmp_path,threading.Event())
    assert seen[0]['style_guidance']['approved_style_examples']
    assert seen[0]['scenes'][0]['text']=='Nội dung hiện tại.'
    assert result['subtitles'][0]['text']=='Nội dung hiện tại.'
    assert all(s['scene_type']=='talking_head' for s in result['storyboard'])


def test_heading_never_splits_explicit_name():
    text,size=headline_layout('THỬ NGHIỆM AN NA VỚI DANAVA',proper_names='AN NA | Anna')
    assert 'AN\nNA' not in text and 'AN NA' in text
    assert ' '.join(text.split())=='THỬ NGHIỆM AN NA VỚI DANAVA'


def test_oversized_style_memory_does_not_displace_source(media,tmp_path,monkeypatch):
    plan=new_project(media)['edit_plan'];plan['subtitles']=[{'start':0,'end':4,'text':'Lời hiện tại.'}]
    plan['learning_context']={'rules':['x'*50000]}
    seen=[]
    def chat(messages,event,schema):
        context=json.loads(messages[1]['content']);seen.append(context)
        return json.dumps({'summary':'Giữ lời','scenes':[{'i':u['scene_index'],'t':'talking_head','h':''} for u in context['scenes']],'captions':True})
    monkeypatch.setattr(automatic_director,'chat',chat)
    event=threading.Event()
    result=automatic_director.automatic_direction(plan,'Giữ lời',main.ASSETS_DIR,tmp_path,event)
    assert 'style_guidance' not in seen[0]
    assert seen[0]['scenes'][0]['text']=='Lời hiện tại.'
    assert not event.style_memory_applied
