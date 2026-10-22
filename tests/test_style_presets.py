"""Preset contracts and real MP4 integration; model responses are never called real AI."""
import copy
import json
import subprocess
import threading

import pytest

import automatic_director
import ai_director
import main
from automatic_director import fallback_direction, semantic_units
from editing import length, probe, validate
from style_presets import apply_style_preset, preset_context, public_presets
from typography import apply_typography
from test_pipeline import client, media, new_project


def source_plan():
    sentences=['Mỗi ngày bạn hãy tiến thêm một bước.',
               'Căn nhà có khu vườn và không gian thoáng.',
               'Chúng ta cùng khám phá từng góc nhỏ.',
               'Giữ lại điều có ý nghĩa với bạn.']
    words=[]
    for i,text in enumerate(sentences):
        for j,word in enumerate(text.split()):
            n=len(text.split())
            words.append({'word':word+('.' if j==n-1 and not word.endswith('.') else ''),
                          'start':i*4+j*4/n,'end':i*4+(j+1)*4/n})
    return {'assets':[], 'video_clips':[{'asset_id':'source','source_in':0,'duration':16,'timeline_start':0}],
        'subtitles':[{'asset_id':'source','start':0,'end':16,'text':' '.join(w['word'] for w in words),'words':words}],
        'audio_tracks':[], 'effect_keyframes':[], 'text_overlays':[], 'visual_overlays':[]}


def directed(plan):
    return fallback_direction(plan,'Giữ nguyên lời nói',threading.Event(),'TEST_NO_MODEL')


def test_catalog_is_bounded_and_api_rejects_unknown_presets():
    catalog=client.get('/api/style-presets').json()
    assert catalog['presets']==public_presets()
    assert {p['id'] for p in catalog['presets']}=={'explainer','inspirational','real_estate'}
    assert client.post('/api/projects/missing/make-video',json={'style_preset':'../../repo'}).status_code==422
    assert preset_context('real_estate')['preferences_only']


def test_scene_pacing_changes_without_dropping_or_moving_words():
    p=source_plan();original=copy.deepcopy(p);counts={}
    for style in ('explainer','inspirational','real_estate'):
        p['style_preset']={'id':style}
        units=semantic_units(p);counts[style]=len(units)
        assert units[0]['start']==0 and units[-1]['end']==16
        assert all(a['end']==b['start'] for a,b in zip(units,units[1:]))
        assert ' '.join(u['text'] for u in units).split()==original['subtitles'][0]['text'].split()
    assert counts['inspirational']<counts['real_estate']
    assert p['subtitles']==original['subtitles']


def test_style_context_never_enters_factual_brief(media,tmp_path,monkeypatch):
    plan=new_project(media)['edit_plan']
    plan['style_preset']={'id':'real_estate'}
    plan['subtitles']=[{'asset_id':plan['assets'][0]['id'],'start':0,'end':4,'text':'Căn nhà có khu vườn.'}]
    def reply(messages,event,schema):
        ctx=json.loads(messages[1]['content'])
        assert ctx['brief']=='Giữ nguồn'
        assert ctx['editing_style']['id']=='real_estate'
        assert 'addresses' in ctx['editing_style']['rules']
        return json.dumps({'summary':'Giữ nguồn','scenes':[{'i':u['scene_index'],'t':'talking_head','h':'Căn nhà'} for u in ctx['scenes']]})
    monkeypatch.setattr(automatic_director,'chat',reply)
    result=automatic_director.automatic_direction(plan,'Giữ nguồn',main.ASSETS_DIR,tmp_path,threading.Event())
    assert length(result)==4
    assert result['subtitles'][0]['text']=='Căn nhà có khu vườn.'


def test_presentations_are_distinct_idempotent_and_source_safe(media):
    base=new_project(media,True)['edit_plan'];aid=base['video_clips'][0]['asset_id']
    base['subtitles']=[{'asset_id':aid,'start':0,'end':4,'text':'Căn nhà có khu vườn thoáng.'}]
    base=directed(base)
    base['storyboard'][0].update(headline='Giá chỉ 3 tỷ',scene_type='explainer_card',graphic_items=['Đảm bảo sinh lời'])
    before=copy.deepcopy(base)
    a=apply_style_preset(base,'inspirational')
    b=apply_style_preset(base,'real_estate')
    assert base==before
    assert a['video_clips']==b['video_clips']==base['video_clips']
    assert a['subtitles']==b['subtitles']==base['subtitles']
    assert a['effect_keyframes'][0]['scale']!=b['effect_keyframes'][0]['scale']
    assert a['storyboard'][0]['headline']=='Căn nhà có khu vườn'
    assert a['storyboard'][0]['graphic_items']==[]
    assert apply_style_preset(b,'real_estate')==b
    assert any('Chưa ghép' in w for w in b['director']['warnings'])
    image=next(x for x in base['assets'] if x['type']=='image')
    base['storyboard'][0]['visual_asset_id']=image['id']
    b=apply_style_preset(base,'real_estate')
    assert b['storyboard'][0]['photo_layout']=='full'
    assert b['director']['illustration_count']==1
    validate(b,b['assets'])


def test_user_opt_outs_and_font_override_are_respected(media):
    p=directed(new_project(media)['edit_plan'])
    r=apply_style_preset(p,'inspirational','Không hiệu ứng, không chữ, không âm thanh')
    assert r['effect_keyframes']==[] and r['audio_tracks']==[] and not r['show_captions']
    assert all(not s['headline'] and not s['motion']['animate'] and s['sound_effect']=='none' for s in r['storyboard'])
    validate(r, r['assets'])
    assert apply_typography(r,'business')['typography']['profile_id']=='business'


def test_preset_keeps_filler_cut_mapping(media):
    from test_speech_cleanup import timed_plan
    from speech_cleanup import clean_speech
    from editing import mapped_subtitles
    source=timed_plan(media)
    cut=clean_speech(source,True)
    cut['style_preset']={'id':'inspirational'}
    result=apply_style_preset(directed(cut),'inspirational')
    result=validate(result,result['assets'])
    assert length(result)==pytest.approx(3.6)
    assert result['video_clips']==cut['video_clips']
    assert mapped_subtitles(result)==mapped_subtitles(cut)


def test_music_must_be_audio_from_this_project_and_is_idempotent(media,tmp_path):
    p=new_project(media)
    assert client.post(f'/api/projects/{p["id"]}/make-video',json={'music_asset_id':'other-project'}).status_code==422
    assert client.post(f'/api/projects/{p["id"]}/make-video',json={'music_asset_id':p['video']['asset_id']}).status_code==422
    music=tmp_path/'music.wav'
    subprocess.run(['ffmpeg','-v','error','-y','-f','lavfi','-i','sine=frequency=220:duration=2',str(music)],check=True)
    with music.open('rb') as f:
        p=client.post(f'/api/projects/{p["id"]}/upload',files={'file':('music.wav',f)},data={'role':'asset'}).json()
    aid=next(a['id'] for a in p['edit_plan']['assets'] if a['type']=='audio')
    base=directed(p['edit_plan'])
    r=apply_style_preset(base,'real_estate',music_asset_id=aid)
    assert len(r['audio_tracks'])==1 and r['audio_tracks'][0]['duration']==2
    assert r['audio_tracks'][0]['volume']==.08
    assert apply_style_preset(r,'real_estate',music_asset_id=aid)==r
    validate(r,r['assets'])
    assert not apply_style_preset(r,'real_estate','Không âm thanh',aid)['audio_tracks']
    assert not apply_style_preset(r,'real_estate','Không nhạc nền',aid)['audio_tracks']


@pytest.mark.parametrize('style,font',[('inspirational','energetic'),('real_estate','business')])
def test_make_video_real_mp4_and_persistent_style(media,monkeypatch,style,font):
    """Real renderer and HTTP route; explicitly forced model-unavailable fallback."""
    p=new_project(media)
    aid=p['video']['asset_id']
    p['edit_plan']['subtitles']=[{'id':'speech','asset_id':aid,'start':0,'end':4,'text':'Mỗi ngày một bước tiến.'}]
    p['edit_plan']['recognition_subtitles']=copy.deepcopy(p['edit_plan']['subtitles'])
    main.save_project(p['id'],p)
    monkeypatch.setattr(main,'recognition_engine',lambda:'faster_whisper')
    monkeypatch.setattr(main,'transcribe',lambda *args:copy.deepcopy(p['edit_plan']['subtitles']))
    monkeypatch.setattr(automatic_director,'chat',lambda *args:(_ for _ in ()).throw(ai_director.AIError('AI_CONNECTION','Test: no model')))
    response=client.post(f'/api/projects/{p["id"]}/make-video',json={'style_preset':style})
    assert response.status_code==200,response.text
    result=client.get(f'/api/projects/{p["id"]}').json()
    assert result['job']['status']=='succeeded',result['job']
    assert result['job']['planning_mode']=='fallback'
    assert result['job']['branding']['style_preset']==style
    assert result['job']['branding']['font_style']=='auto'
    assert result['edit_plan']['style_preset']['id']==style
    assert result['edit_plan']['typography']['profile_id']==font
    assert result['edit_plan']['typography']['selected_by']=='preset'
    output=main.OUTPUTS_DIR/result['output_path'].split('/')[-1]
    meta=probe(output)
    assert (meta['width'],meta['height'])==(720,1280)
    assert meta['has_audio'] and meta['duration']==pytest.approx(4,abs=.05)
    subprocess.run(['ffmpeg','-v','error','-xerror','-i',str(output),'-f','null','-'],check=True,capture_output=True)
    # Source is solid red: gold pixels in the caption band prove that themed
    # color was burned into MP4, rather than merely recorded in plan metadata.
    import numpy as np
    raw=subprocess.run(['ffmpeg','-v','error','-ss','1','-i',str(output),'-frames:v','1',
        '-f','rawvideo','-pix_fmt','rgb24','-'],check=True,capture_output=True).stdout
    band=np.frombuffer(raw,dtype=np.uint8).reshape((1280,720,3))[1000:1200].astype(float)
    gold=(band[:,:,0]>180)&(band[:,:,1]>110)&(band[:,:,2]<band[:,:,1]*.83)&(band[:,:,0]>band[:,:,1]*1.04)
    assert int(gold.sum())>50


def test_strong_style_keeps_relevant_images_and_voice_timeline(media):
    base=directed(new_project(media)['edit_plan'])
    for scene in base['storyboard']:
        scene['transcript_meaning']='Trợ lý AI và chiến lược thương hiệu'
    result=apply_style_preset(base,'inspirational')
    assert all(s['duration']<=2.4+1e-6 for s in result['storyboard'])
    assert any(s.get('library_visual_id') for s in result['storyboard'])
    assert any(s['sound_effect']=='whoosh' for s in result['storyboard'])
    assert result['video_clips']==base['video_clips']
    assert result['subtitles']==base['subtitles']
    assert apply_style_preset(result,'inspirational')==result
