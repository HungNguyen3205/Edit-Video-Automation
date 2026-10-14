"""Source-time filler cuts, caption mapping and real A/V rendering."""
import copy
import subprocess
import threading
import pytest
import main
from speech_cleanup import clean_speech, detect, requested, explicitly_disabled, source_key
from editing import mapped_subtitles, length, compile_render, probe
from automatic_director import fallback_direction
from test_pipeline import media, new_project, client


def timed_plan(media):
    p=new_project(media)['edit_plan'];aid=p['assets'][0]['id']
    p['subtitles']=[{'asset_id':aid,'start':0,'end':4,'text':'Xin chào ờ mọi người.',
        'words':[{'word':' Xin','start':.1,'end':.4,'probability':.95},
                 {'word':' chào','start':.45,'end':.8,'probability':.95},
                 {'word':' ờ','start':1,'end':1.4,'probability':.95},
                 {'word':' mọi','start':1.65,'end':2,'probability':.95},
                 {'word':' người.','start':2.1,'end':2.6,'probability':.95}]}]
    p['recognition_subtitles']=copy.deepcopy(p['subtitles'])
    return p


def test_cuts_actual_timeline_not_only_caption_and_preserves_source(media):
    p=timed_plan(media);before=copy.deepcopy(p);r=clean_speech(p,True)
    assert p==before and r['recognition_subtitles']==p['recognition_subtitles']
    assert r['speech_cleanup']['applied'] and r['speech_cleanup']['removed_count']==1
    assert abs(length(r)-3.6)<1e-6
    assert r['video_clips'][0]['source_in']==0 and r['video_clips'][1]['source_in']==1.4
    assert r['subtitles'][0]['text']=='Xin chào mọi người.'
    mapped=mapped_subtitles(r)
    assert ' '.join(s['text'] for s in mapped)=='Xin chào mọi người.'
    assert next(w['start'] for s in mapped for w in s['words'] if w['word'].strip()=='mọi')==pytest.approx(1.25)
    directed=fallback_direction(r,'Bỏ tiếng đệm',threading.Event(),'TEST_CONTROLLED')
    assert directed['subtitles']==r['subtitles'] and length(directed)==pytest.approx(3.6)


@pytest.mark.parametrize('word', ['à','ừ','òm','"ờ"','“ờ”'])
def test_protects_meaningful_or_quoted_words(media,word):
    p=timed_plan(media);p['subtitles'][0]['words'][2]['word']=word
    assert not clean_speech(p,True)['speech_cleanup']['applied']


@pytest.mark.parametrize('mutation', ['low','overlap','no_words','quoted_context','too_short','no_confidence'])
def test_uncertain_boundaries_keep_speech(media,mutation):
    p=timed_plan(media);words=p['subtitles'][0]['words']
    if mutation=='low':words[2]['probability']=.3
    if mutation=='overlap':words[1]['end']=1.3
    if mutation=='no_words':p['subtitles'][0].pop('words')
    if mutation=='quoted_context':words[1]['word']='tiếng'
    if mutation=='too_short':words[2]['end']=1.1
    if mutation=='no_confidence':words[2].pop('probability')
    r=clean_speech(p,True)
    assert not r['speech_cleanup']['applied'] and r['video_clips']==p['video_clips']


def test_prompt_intent_and_explicit_keep_override():
    assert requested('Xóa các khúc ờ, ừm rồi nối lời mượt')
    assert requested('Bỏ tiếng đệm')
    assert not requested('không cắt ờ') and explicitly_disabled('giữ tiếng đệm')
    assert not requested('Dựng video đẹp')


def test_cancellation_and_disabled_leave_source(media):
    p=timed_plan(media);assert clean_speech(p)==p
    event=threading.Event();event.set()
    with pytest.raises(InterruptedError):clean_speech(p,True,event)


def test_manual_edits_and_cached_cut_provenance(media):
    p=timed_plan(media);r=clean_speech(p,True)
    # Automatic retry always starts from original source clips and ASR words.
    retry=copy.deepcopy(r);retry['video_clips']=copy.deepcopy(p['video_clips']);retry['subtitles']=copy.deepcopy(p['subtitles'])
    assert length(clean_speech(retry,True))==pytest.approx(3.6)
    retry['user_subtitles']=[{k:v for k,v in p['subtitles'][0].items() if k!='words'}]
    retry['user_subtitles'][0]['text']='Xin chào mọi người.'
    r2=clean_speech(retry,True)
    assert r2['speech_cleanup']['applied'] and r2['subtitles'][0]['text']=='Xin chào mọi người.'
    retry['user_subtitles'][0]['text']='Xin chào ờ mọi người.'
    assert not clean_speech(retry,True)['speech_cleanup']['applied']
    retry['user_subtitles'][0]['text']='Xin chào mọi người.';retry['speech_cleanup']['source_key']='stale'
    assert not clean_speech(retry,True)['speech_cleanup']['applied']
    p['user_subtitles']=copy.deepcopy(retry['user_subtitles'])
    assert not clean_speech(p,True)['speech_cleanup']['applied']


def test_source_ranges_filter_outside_words_and_preserve_nonzero_in(media):
    p=timed_plan(media);p['video_clips'][0].update(source_in=1.5,duration=2.5)
    assert not clean_speech(p,True)['speech_cleanup']['applied']
    p['video_clips'][0].update(source_in=.5,duration=3.5)
    r=clean_speech(p,True);assert length(r)==pytest.approx(3.1)
    assert r['video_clips'][0]['source_in']==.5


def test_client_cannot_forge_verified_cuts(media):
    p=new_project(media);plan=copy.deepcopy(p['edit_plan']);plan['speech_cleanup']={'applied':True,'cuts':[{'start':0,'end':3}]}
    res=client.post(f'/api/projects/{p["id"]}/edit_plan',json={'revision':p['revision'],'plan':plan})
    assert res.status_code==200,res.text
    assert 'speech_cleanup' not in res.json()['edit_plan']


def test_real_ffmpeg_filler_cut_audio_duration_and_caption_mapping(media,tmp_path):
    # A controlled timestamp fixture verifies cut mechanics, not recognition quality.
    p=timed_plan(media);r=clean_speech(p,True);work=tmp_path/'render';work.mkdir();out=tmp_path/'clean.mp4'
    cmd,duration=compile_render(r,main.ASSETS_DIR,work,out)
    assert 'afade=t=in' in ' '.join(cmd) and 'afade=t=out' in ' '.join(cmd)
    subprocess.run(cmd,check=True,capture_output=True)
    meta=probe(out);assert meta['has_audio'] and abs(meta['duration']-3.6)<.04
    subprocess.run(['ffmpeg','-v','error','-xerror','-i',str(out),'-f','null','-'],check=True)
    audio=subprocess.check_output(['ffmpeg','-v','error','-i',str(out),'-f','f32le','-ac','1','-ar','48000','-'])
    import numpy as np
    a=np.frombuffer(audio,dtype='<f4');join=48000
    assert np.sqrt(np.mean(a[join-2400:join-480]**2))>.03
    assert np.sqrt(np.mean(a[join+480:join+2400]**2))>.03
    assert np.max(np.abs(a[join-30:join+30]))<.04  # tiny edge ramp prevents a click


def test_api_toggle_retry_and_negative_prompt_preserve_full_source(media,monkeypatch):
    monkeypatch.setenv('OLLAMA_URL','http://127.0.0.1:9')
    p=new_project(media);plan=timed_plan(media)
    # Fixture timings belong to this uploaded synthetic source, not a model reply.
    aid=p['video']['asset_id'];old=plan['video_clips'][0]['asset_id']
    plan['assets']=p['edit_plan']['assets']
    for clip in plan['video_clips']:clip['asset_id']=aid
    for key in ['subtitles','recognition_subtitles']:
        for sub in plan[key]:sub['asset_id']=aid
    p['edit_plan']=plan;main.save_project(p['id'],p)
    outputs=[]
    for options,expected in [({'remove_fillers':True},3.6),({'remove_fillers':False},4),({'remove_fillers':True,'prompt':'Không cắt ờ, giữ tiếng đệm'},4)]:
        response=client.post(f'/api/projects/{p["id"]}/make-video',json={'illustrations':False,**options})
        assert response.status_code==200,response.text
        latest=client.get(f'/api/projects/{p["id"]}').json();assert latest['job']['status']=='succeeded',latest['job']
        assert latest['duration_audit']['ffprobe_duration']==pytest.approx(expected,abs=.04)
        assert latest['job']['timings']['recognition_seconds']<.1
        outputs.append(main.OUTPUTS_DIR / latest['output_path'].split('/')[-1])
    assert all(out.exists() for out in outputs)


def test_adjacent_filler_run_joins_without_tiny_silent_clip(media):
    p=timed_plan(media);words=p['subtitles'][0]['words']
    words.insert(3,{'word':' ừm','start':1.4,'end':1.7,'probability':.95})
    words[4]['start']=1.9
    p['recognition_subtitles']=copy.deepcopy(p['subtitles'])
    r=clean_speech(p,True)
    assert r['speech_cleanup']['removed_count']==2 and len(r['video_clips'])==2
    assert 'ừm' not in r['subtitles'][0]['text'] and length(r)==pytest.approx(3.3)


def test_filler_only_recognition_does_not_empty_speech(media):
    p=timed_plan(media);p['subtitles'][0]['words']=p['subtitles'][0]['words'][2:3]
    p['subtitles'][0]['text']='ờ';p['recognition_subtitles']=copy.deepcopy(p['subtitles'])
    assert not clean_speech(p,True)['speech_cleanup']['applied']
