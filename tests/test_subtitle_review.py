import copy
import threading
from fastapi.testclient import TestClient
import main
from automatic_director import fallback_direction
from test_pipeline import media,new_project

client=TestClient(main.app)

def test_user_correction_survives_automatic_retry(media,monkeypatch):
    p=new_project(media)
    aid=p['video']['asset_id']
    original=[{'id':'s','asset_id':aid,'start':0,'end':4,'text':'Tên chưa đúng.'}]
    p['edit_plan']['subtitles']=copy.deepcopy(original)
    p['edit_plan']['recognition_subtitles']=copy.deepcopy(original)
    main.save_project(p['id'],p)
    plan=copy.deepcopy(p['edit_plan']);plan['subtitles'][0]['text']='Tên riêng đã sửa.'
    r=client.post(f'/api/projects/{p["id"]}/edit_plan',json={'revision':p['revision'],'plan':plan})
    assert r.status_code==200,r.text
    assert r.json()['edit_plan']['user_subtitles'][0]['text']=='Tên riêng đã sửa.'
    monkeypatch.setenv('OLLAMA_URL','http://127.0.0.1:9')
    for _ in range(2):
        r=client.post(f'/api/projects/{p["id"]}/make-video',json={'illustrations':False})
        assert r.status_code==200,r.text
        result=client.get(f'/api/projects/{p["id"]}').json()
        assert result['job']['status']=='succeeded',result['job']
        assert result['edit_plan']['subtitles']==plan['subtitles']
        assert result['edit_plan']['recognition_subtitles'][0]['text']=='Tên chưa đúng.'
        assert result['job']['timings']['recognition_seconds']<1

def test_stale_review_cannot_overwrite_project(media):
    p=new_project(media)
    r=client.post(f'/api/projects/{p["id"]}/edit_plan',json={'revision':-1,'plan':p['edit_plan']})
    assert r.status_code==409
    assert client.get(f'/api/projects/{p["id"]}').json()['revision']==p['revision']


def test_review_cache_cannot_be_changed_without_subtitle_edit(media):
    p=new_project(media)
    plan=copy.deepcopy(p['edit_plan']);plan['user_subtitles']=[{'text':'Unvalidated override'}]
    r=client.post(f'/api/projects/{p["id"]}/edit_plan',json={'revision':p['revision'],'plan':plan})
    assert r.status_code==200
    assert 'user_subtitles' not in r.json()['edit_plan']
