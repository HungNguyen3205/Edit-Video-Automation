import copy,json
import main
from text_review import subtitle_fingerprint,valid_confirmations,unconfirmed_issues,review_issues
from learning_store import LearningStore
from test_pipeline import media,new_project,client


def flagged_project(media):
    p=new_project(media);aid=p['video']['asset_id']
    p['edit_plan']['subtitles']=[{'id':'s','asset_id':aid,'start':0,'end':4,'text':'Lời nói cần nghe lại.',
        'words':[{'word':' Lời nói cần nghe lại.','start':0,'end':4,'probability':.1}]}]
    p['edit_plan']['subtitle_review']=review_issues(p['edit_plan']['subtitles'])
    p.update(job={'status':'succeeded','planning_mode':'fallback'},output_path='/outputs/review.mp4',output_revision=p['revision'])
    main.save_project(p['id'],p);return p


def confirm(p,yes=True,index=0,revision=None):
    return client.post(f'/api/projects/{p["id"]}/subtitle-review',json={'revision':p['revision'] if revision is None else revision,'subtitle_index':index,'confirmed':yes})


def test_confirmation_is_source_text_and_interval_bound_and_not_a_pixel_edit(media):
    p=flagged_project(media);rev=p['revision'];path=p['output_path']
    r=confirm(p);assert r.status_code==200,r.text
    q=r.json();assert q['revision']==q['output_revision']==rev and q['output_path']==path
    assert q['subtitle_review_status']['confirmed_indices']==[0]
    assert not q['edit_plan']['subtitle_review'] and len(valid_confirmations(q['edit_plan']))==1
    for change in ('text','start','asset'):
        altered=copy.deepcopy(q['edit_plan'])
        if change=='text':altered['subtitles'][0]['text']='Đã thay câu'
        elif change=='start':altered['subtitles'][0]['start']=.1
        else:altered['assets'][0]['sha256']='f'*64
        assert not valid_confirmations(altered)
    assert confirm(q).json()['edit_plan']['subtitle_confirmations']==q['edit_plan']['subtitle_confirmations']
    undone=confirm(q,False).json();assert undone['edit_plan']['subtitle_review']
    assert not undone['subtitle_review_status']['confirmed_indices']


def test_confirmation_rejects_stale_index_and_running_job(media):
    p=flagged_project(media)
    assert confirm(p,revision=-1).status_code==409
    assert confirm(p,index=20).status_code==422
    assert confirm(p,index=-1).status_code==422
    p['job']['status']='running';main.save_project(p['id'],p)
    assert confirm(p).status_code==409


def test_editor_cannot_spoof_confirmation_and_changed_text_drops_it(media):
    p=flagged_project(media);plan=copy.deepcopy(p['edit_plan'])
    plan['subtitle_confirmations']=[subtitle_fingerprint(plan,plan['subtitles'][0])];plan['subtitle_review']=[]
    plan['subtitle_review_evidence']={'forged':'Forged warning'}
    r=client.post(f'/api/projects/{p["id"]}/edit_plan',json={'revision':p['revision'],'plan':plan});assert r.status_code==200,r.text
    q=r.json();assert not q['edit_plan']['subtitle_confirmations'] and q['edit_plan']['subtitle_review']
    assert 'forged' not in q['edit_plan']['subtitle_review_evidence']
    q=confirm(q).json();plan=copy.deepcopy(q['edit_plan']);plan['subtitles'][0]['text']='Câu mới.'
    q=client.post(f'/api/projects/{q["id"]}/edit_plan',json={'revision':q['revision'],'plan':plan}).json()
    assert not q['edit_plan']['subtitle_confirmations']
    assert q['output_revision']!=q['revision']


def test_reviewed_export_excludes_style_only_legacy_and_undone_reviews(media,tmp_path,monkeypatch):
    monkeypatch.setattr(main,'DATA_DIR',tmp_path)
    p=flagged_project(media)
    body={'revision':p['revision'],'output_path':p['output_path'],'decision':'approve_style','note':'Chữ rõ.'}
    assert client.post(f'/api/projects/{p["id"]}/feedback',json={**body,'captions_checked':True}).status_code==422
    r=client.post(f'/api/projects/{p["id"]}/feedback',json=body);assert r.status_code==200
    assert r.json()['learning']['style_only_examples']==1
    assert client.get('/api/learning/reviewed-export').text==''
    q=confirm(p).json()
    r=client.post(f'/api/projects/{p["id"]}/feedback',json={**body,'captions_checked':True});assert r.status_code==200,r.text
    assert r.json()['learning']['reviewed_examples']==1 and r.json()['learning']['reviewed_sources']==1
    data=json.loads(client.get('/api/learning/reviewed-export').text)
    assert data['captions_checked'] is True and data['note']=='Chữ rõ.'
    assert all(k not in data for k in ('subtitles','output_path','project_id','source_sha256'))
    assert confirm(q,False).status_code==200
    assert client.get('/api/learning/reviewed-export').text==''
    assert json.loads(client.get('/api/learning/export').text)['captions_checked'] is False
    # Legacy feedback never gains review evidence merely because its checkbox was true.
    store=LearningStore(tmp_path);record=store.records()[0];record['captions_checked']=True;record.pop('review_evidence')
    (store.root/(record['id']+'.json')).write_text(json.dumps(record))
    assert not store.reviewed_records() and store.status()['approved_styles']==1


def test_undo_on_new_revision_does_not_copy_old_approval_to_new_output(media,tmp_path,monkeypatch):
    monkeypatch.setattr(main,'DATA_DIR',tmp_path);p=flagged_project(media)
    p['style_feedback']=LearningStore(tmp_path).save(p,'approve_style','Old approval',True)
    p['revision']+=1;p['output_path']='/outputs/new.mp4';p['output_revision']=p['revision'];main.save_project(p['id'],p)
    assert confirm(p,False).status_code==200
    assert len(LearningStore(tmp_path).records())==1


def test_confirmation_survives_real_fallback_render_without_erasing_source_warning(media,monkeypatch):
    monkeypatch.setenv('OLLAMA_URL','http://127.0.0.1:9')
    p=flagged_project(media);p=confirm(p).json()
    r=client.post(f'/api/projects/{p["id"]}/make-video',json={'illustrations':False})
    assert r.status_code==200,r.text
    q=client.get(f'/api/projects/{p["id"]}').json()
    assert q['job']['status']=='succeeded' and q['job']['planning_mode']=='fallback'
    assert q['subtitle_review_status']['confirmed_indices']==[0]
    assert not q['edit_plan']['subtitle_review']
    assert q['edit_plan']['subtitles'][0]['text']==p['edit_plan']['subtitles'][0]['text']
    # The confidence data is retained: undoing confirmation restores the warning.
    assert confirm(q,False).json()['edit_plan']['subtitle_review']


def test_confirmation_does_not_transfer_to_another_project(media):
    p=confirm(flagged_project(media)).json();q=flagged_project(media)
    q['edit_plan']['subtitle_confirmations']=p['edit_plan']['subtitle_confirmations']
    assert not valid_confirmations(q['edit_plan'])


def test_corrupt_review_evidence_cannot_break_status_or_become_reviewed(media,tmp_path):
    p=flagged_project(media);store=LearningStore(tmp_path)
    record=store.save(p,'approve_style','Chỉ phong cách.',True)
    for broken in [None,[],True,'verified']:
        record['review_evidence']=broken
        (store.root/(record['id']+'.json')).write_text(json.dumps(record))
        assert store.status()['reviewed_examples']==0
        assert store.export(reviewed_only=True)==''
