import copy,json,subprocess,threading
from pathlib import Path
import pytest
import main
from visual_library import apply_library_visuals,library_image,phrase_in,catalog
from motion_style import apply_motion_style
from automatic_director import fallback_direction
from editing import validate,probe
from scene_transitions import assemble_scenes
from storyboard_compiler import run
from test_pipeline import media,new_project,client,rgb_at


def speaking_plan(media):
    p=new_project(media)['edit_plan'];aid=p['assets'][0]['id']
    p['subtitles']=[{'asset_id':aid,'start':0,'end':4,'text':'Mở đầu. Trợ lý AI. Xây dựng thương hiệu. Kết thúc.'}]
    p['storyboard']=[{'scene_id':str(i),'scene_type':'talking_head','timeline_start':i,'duration':1,'headline':'','transcript_meaning':text} for i,text in enumerate(['Mở đầu.','Trợ lý AI.','Xây dựng thương hiệu.','Kết thúc.'])]
    # Use a longer synthetic timeline to exercise bounded image beats.
    p['video_clips'][0]['duration']=4
    p['branding']={'illustrations':True}
    return p


def test_library_catalog_is_local_small_grounded_and_safe():
    assert len(catalog())==2
    assert all(library_image(e['id']).stat().st_size<200000 for e in catalog())
    assert phrase_in('AI','Trợ lý AI.') and not phrase_in('AI','Hai người đang tập.')
    with pytest.raises(ValueError):library_image('../../private')


def test_photo_selection_is_content_based_preserves_time_and_prioritizes_upload(media):
    plan=speaking_plan(media)
    # Four real seconds are enough for a single interior photo beat.
    plan['storyboard']=[{'scene_id':'a','scene_type':'talking_head','timeline_start':0,'duration':.4,'headline':'','transcript_meaning':'Mở đầu'},
        {'scene_id':'b','scene_type':'talking_head','timeline_start':.4,'duration':3,'headline':'','transcript_meaning':'Trợ lý AI hỗ trợ.'},
        {'scene_id':'c','scene_type':'talking_head','timeline_start':3.4,'duration':.6,'headline':'','transcript_meaning':'Kết thúc'}]
    before=copy.deepcopy(plan);result=apply_library_visuals(plan)
    assert plan==before and result['subtitles']==plan['subtitles'] and result['video_clips']==plan['video_clips']
    assert result['storyboard'][1]['library_visual_id']=='ai_assistant'
    assert result['storyboard'][0]['scene_type']==result['storyboard'][-1]['scene_type']=='talking_head'
    assert sum(s['duration'] for s in result['storyboard'])==4
    assert apply_library_visuals(result)==result
    assert apply_library_visuals(plan,'Không chèn ảnh')==plan
    assert apply_library_visuals(plan,enabled=False)==plan
    unrelated=copy.deepcopy(plan);unrelated['storyboard'][1]['transcript_meaning']='Hít thở chậm và thả lỏng vai.'
    assert apply_library_visuals(unrelated)==unrelated
    protected=copy.deepcopy(plan);protected['storyboard'][1]['visual_asset_id']='user-photo'
    assert apply_library_visuals(protected)==protected


def test_validation_rejects_unknown_library_image_and_layout(media):
    p=speaking_plan(media);p['storyboard'][1]['library_visual_id']='../../../file'
    with pytest.raises(ValueError):validate(p,p['assets'])
    p['storyboard'][1].pop('library_visual_id');p['storyboard'][1]['photo_layout']='arbitrary'
    with pytest.raises(ValueError):validate(p,p['assets'])


def test_real_dissolve_preserves_duration_and_blends_only_visual_boundaries(tmp_path):
    files=[]
    for i,color in enumerate(['red','blue','green']):
        file=tmp_path/f'{i}.mp4';subprocess.run(['ffmpeg','-v','error','-y','-f','lavfi','-i',f'color={color}:s=120x160:r=10:d=1','-c:v','libx264','-pix_fmt','yuv420p',str(file)],check=True);files.append(file)
    scenes=[{'scene_type':typ,'duration':1,'motion':{'animate':True,'transition_seconds':.2}} for typ in ['talking_head','explainer_card','talking_head']]
    out=tmp_path/'blend.mp4';metrics=assemble_scenes(files,scenes,10,out,tmp_path,run,threading.Event())
    assert metrics['count']==2 and not metrics['voice_overlap'] and abs(probe(out)['duration']-3)<.01
    mixed=rgb_at(out,1.1,60,80);assert mixed[0]>50 and mixed[2]>50
    after=rgb_at(out,1.4,60,80);assert after[2]>200 and after[0]<30
    subprocess.run(['ffmpeg','-v','error','-xerror','-i',str(out),'-f','null','-'],check=True)
    for s in scenes:s['motion']['animate']=False
    out2=tmp_path/'hard.mp4';assert assemble_scenes(files,scenes,10,out2,tmp_path,run)['count']==0
    assert rgb_at(out2,1.1,60,80)[0]<30


def test_real_photo_scene_renderer_and_static_opt_out(tmp_path):
    cfg={'scene_type':'explainer_card','photo_layout':'full','asset_path':str(library_image('ai_assistant')),
        'headline':'TRỢ LÝ AI','duration':.7,'motion_style':'dynamic_explainer','motion':{'animate':False,'show_photo_label':True}}
    source=tmp_path/'photo.json';source.write_text(json.dumps(cfg));out=tmp_path/'photo.mp4'
    subprocess.run(['node',str(main.BASE_DIR/'motion_engine/render_scene.js'),'--input',str(source),'--output',str(out),'--width','360','--height','640','--fps','10'],check=True,capture_output=True)
    import numpy as np
    frames=[]
    for t in [.1,.5]:
        data=subprocess.check_output(['ffmpeg','-v','error','-ss',str(t),'-i',str(out),'-frames:v','1','-f','rawvideo','-pix_fmt','rgb24','-']);frames.append(np.frombuffer(data,dtype=np.uint8).reshape(640,360,3))
    assert frames[0][250:520].std()>25
    assert np.abs(frames[0].astype(float)-frames[1]).mean()<2


def test_short_source_does_not_force_photos_over_opening(media,monkeypatch):
    monkeypatch.setenv('OLLAMA_URL','http://127.0.0.1:9')
    p=new_project(media);plan=speaking_plan(media)
    # Use the correct uploaded asset for this project; no mocked planner response.
    plan['assets']=p['edit_plan']['assets'];plan['video_clips']=p['edit_plan']['video_clips'];plan['subtitles']=[{'asset_id':p['video']['asset_id'],'start':0,'end':4,'text':'Trợ lý AI hỗ trợ.'}]
    p['edit_plan']=plan;main.save_project(p['id'],p)
    # A 4-second source has no interior semantic scene; do not force an image over its opening.
    r=client.post(f'/api/projects/{p["id"]}/make-video',json={'motion_style':'dynamic_explainer','illustrations':True});assert r.status_code==200,r.text
    p=client.get(f'/api/projects/{p["id"]}').json();assert p['job']['status']=='succeeded' and p['job']['planning_mode']=='fallback'
    assert abs(p['duration_audit']['ffprobe_duration']-4)<.04


def test_preview_clips_last_photo_before_dissolve_assembly(media,tmp_path):
    from storyboard_compiler import compile_storyboard_scenes
    source=tmp_path/'long.mp4'
    subprocess.run(['ffmpeg','-v','error','-y','-f','lavfi','-i','color=red:s=240x320:r=10:d=16','-f','lavfi','-i','sine=frequency=440:duration=16','-c:v','libx264','-c:a','aac',str(source)],check=True)
    asset={'id':'source','type':'video','filename':'long.mp4','metadata':probe(source)}
    plan=new_project(media)['edit_plan'];plan['assets']=[asset];plan['video_clips']=[{'id':'v','asset_id':'source','source_in':0,'duration':16,'timeline_start':0}]
    plan['subtitles']=[];plan['output_settings']['fps']=10
    plan['storyboard']=[{'scene_id':'a','scene_type':'talking_head','timeline_start':0,'duration':8,'headline':'','motion':{'animate':True,'transition_seconds':.2}},
        {'scene_id':'b','scene_type':'explainer_card','timeline_start':8,'duration':8,'headline':'','library_visual_id':'ai_assistant','photo_layout':'full','motion':{'animate':True,'transition_seconds':.2}}]
    plan['motion_style']={'preset':'dynamic_explainer'};out=tmp_path/'preview.mp4';metrics={}
    compile_storyboard_scenes(plan,tmp_path,tmp_path/'render',out,preview=True,metrics=metrics)
    assert abs(probe(out)['duration']-12)<.11 and probe(out)['has_audio']
    assert metrics['scene_transitions']['count']==1
    subprocess.run(['ffmpeg','-v','error','-xerror','-i',str(out),'-f','null','-'],check=True)
