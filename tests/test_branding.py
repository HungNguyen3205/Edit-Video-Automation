import copy
import threading
import subprocess
import numpy as np
import pytest
from PIL import Image,ImageDraw
from test_pipeline import media,new_project,client
import main
from automatic_director import fallback_direction
from video_branding import apply_visual_assets
from editing import probe
from asset_resolver import AssetResolver


def plan_with_speech(media):
    p=new_project(media);aid=p['video']['asset_id']
    p['edit_plan']['subtitles']=[{'id':'s','asset_id':aid,'start':0,'end':4,'text':'Trợ lý AI hỗ trợ công việc.'}]
    main.save_project(p['id'],p);return p


def ruled_plan(media):
    p=plan_with_speech(media)
    return fallback_direction(p['edit_plan'],'Giữ lời',threading.Event(),'AI_CONNECTION')


def test_source_graphics_are_added_without_inventing_features(media):
    plan=ruled_plan(media)
    plan['assets'][0]['metadata']['duration']=24;plan['video_clips'][0]['duration']=24
    texts=['Mở đầu','Trợ lý AI','Thử nghiệm','Chiến lược xây dựng thương hiệu','Thông điệp doanh nghiệp','Kết thúc']
    plan['storyboard']=[{'scene_id':str(i),'scene_type':'talking_head','timeline_start':4*i,'duration':4,
        'headline':text,'transcript_meaning':text} for i,text in enumerate(texts)]
    result=apply_visual_assets(plan,'Minh họa')
    assert result['director']['illustration_count']==2
    assert result['storyboard'][0]['scene_type']==result['storyboard'][-1]['scene_type']=='talking_head'
    assert {s['source'] for s in result['director']['visual_sources']}=={'source_rules'}
    assert all('giá' not in s.get('graphic_title','') for s in result['storyboard'])
    hidden=apply_visual_assets(plan,'Giữ lời',illustrations=False)
    assert hidden['director']['illustration_count']==0


def test_no_context_does_not_fabricate_graphics(media):
    p=ruled_plan(media)
    p['storyboard'][0]['transcript_meaning']='Một câu không rõ ý.'
    result=apply_visual_assets(p,'Minh họa')
    assert result['director']['illustration_count']==0
    assert result['director']['warnings']


def test_logo_and_photos_require_project_owned_images(media):
    p=ruled_plan(media)
    with pytest.raises(ValueError):apply_visual_assets(p,'',logo_asset_id='other-project')
    with pytest.raises(ValueError):apply_visual_assets(p,'',image_asset_ids=[p['assets'][0]['id']])
    project=new_project(media,True);image=next(a for a in project['edit_plan']['assets'] if a['type']=='image')
    assert client.post(f'/api/projects/{project["id"]}/make-video',json={'logo_asset_id':'wrong'}).status_code==422
    assert client.post(f'/api/projects/{project["id"]}/make-video',json={'logo_asset_id':image['id'],'image_asset_ids':[image['id']]}).status_code==422


def test_image_topic_matching_and_explicit_photo_when_auto_disabled(media):
    project=new_project(media,True);plan=project['edit_plan'];image=next(a for a in plan['assets'] if a['type']=='image')
    plan['subtitles']=[{'start':0,'end':4,'text':'Trợ lý AI hỗ trợ công việc.'}]
    plan=fallback_direction(plan,'Giữ lời',threading.Event(),'AI_CONNECTION')
    next(a for a in plan['assets'] if a['id']==image['id'])['keywords']='Trợ lý AI'
    result=apply_visual_assets(plan,'',image_asset_ids=[image['id']],illustrations=False)
    assert result['storyboard'][0]['visual_asset_id']==image['id']
    assert result['director']['illustration_count']==1
    next(a for a in plan['assets'] if a['id']==image['id'])['keywords']='Bể bơi'
    result=apply_visual_assets(plan,'',image_asset_ids=[image['id']])
    assert not result['storyboard'][0].get('visual_asset_id')
    assert any('chủ đề' in w for w in result['director']['warnings'])


def test_logo_upload_usage_cannot_be_automatically_resolved_as_photo(media,tmp_path):
    p=new_project(media)
    with media[2].open('rb') as f:
        p=client.post(f'/api/projects/{p["id"]}/upload',files={'file':('brand.png',f)},data={'role':'logo','keywords':'trợ lý'}).json()
    image=next(a for a in p['edit_plan']['assets'] if a['type']=='image')
    assert image['usage']=='logo'
    r=AssetResolver(p['edit_plan']['assets'],main.ASSETS_DIR,tmp_path).resolve_visual(query='trợ lý',graphic_kind='chat',graphic_title='Trợ lý',graphic_items=['Chào bạn','Hỗ trợ'])
    assert r['source']!='user_uploaded'


def test_real_logo_transparency_and_brand_persist_on_rerender(media,tmp_path,monkeypatch):
    p=plan_with_speech(media)
    logo=tmp_path/'logo.png';im=Image.new('RGBA',(100,100),(0,0,0,0));ImageDraw.Draw(im).ellipse((20,20,80,80),fill=(0,255,0,255));im.save(logo)
    with logo.open('rb') as f:
        p=client.post(f'/api/projects/{p["id"]}/upload',files={'file':('logo.png',f)},data={'role':'logo'}).json()
    aid=p['edit_plan']['assets'][-1]['id']
    monkeypatch.setenv('OLLAMA_URL','http://127.0.0.1:9')
    body={'brand_name':'TEST BRAND','logo_asset_id':aid,'illustrations':False}
    for _ in range(2):
        assert client.post(f'/api/projects/{p["id"]}/make-video',json=body).status_code==200
        r=client.get(f'/api/projects/{p["id"]}').json();assert r['job']['status']=='succeeded',r['job']
        assert len([o for o in r['edit_plan']['visual_overlays'] if o.get('role')=='logo'])==1
        assert r['edit_plan']['branding']['brand_name']=='TEST BRAND'
    out=main.OUTPUTS_DIR/r['output_path'].split('/')[-1];assert probe(out)['has_audio']
    raw=subprocess.run(['ffmpeg','-v','error','-ss','1','-i',str(out),'-frames:v','1','-f','rawvideo','-pix_fmt','rgb24','-'],capture_output=True,check=True).stdout
    pixels=np.frombuffer(raw,dtype=np.uint8).reshape(1280,720,3)
    assert pixels[90,626,1]>150 and pixels[90,626,0]<100
    assert pixels[34,556,0]>180 and pixels[34,556,1]<80  # Transparent corner stays source red.
    assert np.mean(pixels[1210:1250,260:460,1])>5  # White brand footer changes source pixels.


def test_real_photo_export_uses_selected_image(media,monkeypatch):
    p=plan_with_speech(media)
    with media[2].open('rb') as f:
        p=client.post(f'/api/projects/{p["id"]}/upload',files={'file':('photo.png',f)},data={'role':'asset','keywords':'Trợ lý AI'}).json()
    aid=p['edit_plan']['assets'][-1]['id'];monkeypatch.setenv('OLLAMA_URL','http://127.0.0.1:9')
    assert client.post(f'/api/projects/{p["id"]}/make-video',json={'image_asset_ids':[aid],'illustrations':False}).status_code==200
    r=client.get(f'/api/projects/{p["id"]}').json();assert r['job']['status']=='succeeded',r['job']
    assert r['edit_plan']['storyboard'][0]['visual_asset_id']==aid
    out=main.OUTPUTS_DIR/r['output_path'].split('/')[-1]
    raw=subprocess.run(['ffmpeg','-v','error','-ss','2','-i',str(out),'-frames:v','1','-f','rawvideo','-pix_fmt','rgb24','-'],capture_output=True,check=True).stdout
    pixels=np.frombuffer(raw,dtype=np.uint8).reshape(1280,720,3)
    blue=(pixels[:650,:,2]>180)&(pixels[:650,:,0]<80)&(pixels[:650,:,1]<80)
    assert int(blue.sum())>3000


def test_max_user_prompt_can_include_brand_and_layout_instructions(media,monkeypatch):
    p=new_project(media);captured=[]
    monkeypatch.setattr(main,'enqueue',lambda pid,bg,options,mode:captured.append(options) or p)
    r=client.post(f'/api/projects/{p["id"]}/make-video',json={'prompt':'x'*4000,'brand_name':'B'*100,'illustrations':False})
    assert r.status_code==200,r.text
    assert captured[0].user_prompt=='x'*4000
    assert 'Không thêm đồ họa' in captured[0].prompt and captured[0].brand_footer=='B'*100


def test_uncertain_recognition_is_not_promoted_to_fallback_heading(media):
    plan=ruled_plan(media);plan['storyboard'][0]['transcript_meaning']='Mọi người có thể chết cái này.'
    result=apply_visual_assets(plan,'',brand_name='TEST BRAND',illustrations=False)
    assert result['storyboard'][0]['headline']=='TEST BRAND'
    assert 'CHẾT' not in result['storyboard'][0]['headline']
