import json
import subprocess
import threading
import sys
import numpy as np
import pytest
from PIL import Image
from ai_director import Direction, direct
from asset_resolver import AssetResolver
from editing import probe, validate
from storyboard_compiler import compile_storyboard_scenes, run
from storyboard_style import write_storyboard_ass, caption_chunks
from test_pipeline import media, new_project
import main


def test_caption_safe_areas_and_literal_text(media, tmp_path):
    plan = new_project(media)['edit_plan']
    aid=plan['assets'][0]['id']
    plan['subtitles']=[{'asset_id':aid,'start':0,'end':4,'text':'Đây là một lời nói khá dài cần được chia thành các phụ đề ngắn dễ đọc.'}]
    plan['storyboard']=[{'scene_type':'talking_head','timeline_start':0,'duration':4,'headline':'{\\pos(0,0)} Không chèn mã','badge_text':'DANAVA'}]
    path=tmp_path/'style.ass'
    write_storyboard_ass(path,plan,720,1280)
    content=path.read_text()
    assert 'Barlow Condensed' in content and 'Inter' in content
    assert '{\\pos(0,0)}' not in content
    assert len(caption_chunks(plan['subtitles'])) == 3


@pytest.mark.parametrize('kind',['chat','process','network'])
def test_meaning_based_graphics_without_uploaded_images(tmp_path,kind):
    resolver=AssetResolver([],tmp_path,tmp_path)
    out=resolver.resolve_visual(graphic_kind=kind,graphic_title='Ý TƯỞNG',graphic_items=['Một','Hai','Ba'])
    assert out['source']=='conceptual_graphic'
    assert Image.open(out['local_path']).size==(600,460)


def test_preserve_policy_repairs_shortened_content(media,tmp_path,monkeypatch):
    import ai_director
    responses=[{'summary':'Rút gọn','cuts':[{'start':0,'end':3}]},
               {'summary':'Giữ đủ','cuts':[{'start':0,'end':4}]}]
    seen=[]
    def reply(messages,event):
        seen.append(str(messages))
        return json.dumps(responses.pop(0))
    monkeypatch.setattr(ai_director,'chat',reply)
    out=direct(new_project(media)['edit_plan'],'Giữ toàn bộ',main.ASSETS_DIR,tmp_path,threading.Event())
    assert len(seen)==2 and 'preserve requires' in seen[-1]
    assert sum(c['duration'] for c in out['video_clips'])==4


def test_cancel_stops_child_process():
    event=threading.Event();event.set()
    with pytest.raises(InterruptedError):
        run([sys.executable,'-c','import time; time.sleep(20)'],event)


def test_real_storyboard_preview_broll_voice_and_sound(media,tmp_path):
    plan=new_project(media,include_image=True)['edit_plan']
    image=next(a for a in plan['assets'] if a['type']=='image')
    plan['effect_keyframes']=[]
    plan['storyboard']=[{'scene_type':'talking_head','timeline_start':0,'duration':1,'headline':'GIỌNG NÓI GỐC'},
                        {'scene_type':'explainer_card','timeline_start':1,'duration':2,'headline':'MINH HỌA AI','graphic_kind':'chat','graphic_title':'AN NA','graphic_items':['Chào bạn','Một ý tưởng mới'],'sound_effect':'pop','animation_in':'slide_up'},
                        {'scene_type':'broll','timeline_start':3,'duration':1,'visual_asset_id':image['id']}]
    output=tmp_path/'preview.mp4'
    duration=compile_storyboard_scenes(plan,main.ASSETS_DIR,tmp_path/'work',output,preview=True)
    meta=probe(output)
    assert (meta['width'],meta['height'])==(360,640)
    assert duration==4 and meta['duration']==pytest.approx(4,abs=.06)
    def pcm(p):
        return np.frombuffer(subprocess.run(['ffmpeg','-v','error','-i',str(p),'-vn','-ar','16000','-ac','1','-f','f32le','-'],capture_output=True,check=True).stdout,dtype=np.float32)
    source=pcm(media[0]);result=pcm(output)
    assert np.corrcoef(source[3200:12800],result[3200:12800])[0,1]>.98
    assert np.mean(np.abs(result[18500:21500]-source[18500:21500]))>.00001
    frame=subprocess.run(['ffmpeg','-v','error','-ss','3.5','-i',str(output),'-frames:v','1','-f','rawvideo','-pix_fmt','rgb24','-'],capture_output=True,check=True).stdout
    pixels=np.frombuffer(frame,dtype=np.uint8).reshape(640,360,3)
    assert pixels[320,180,2]>180 and pixels[320,180,0]<40
    subprocess.run(['ffmpeg','-v','error','-xerror','-i',str(output),'-f','null','-'],check=True,capture_output=True)


def test_invalid_scene_assets_cannot_render(media):
    plan=new_project(media)['edit_plan']
    plan['storyboard']=[{'scene_type':'broll','timeline_start':0,'duration':4,'visual_asset_id':'unknown'}]
    with pytest.raises(ValueError,match='thuộc dự án'):
        validate(plan,plan['assets'])


def test_word_timestamps_avoid_captions_during_opening_silence():
    subs=[{'start':0,'end':4,'text':'Chào mọi người!', 'words':[
        {'start':1.8,'end':2.3,'word':' Chào'}, {'start':2.3,'end':2.8,'word':' mọi'},
        {'start':2.8,'end':3.1,'word':' người!'}]}]
    chunks=caption_chunks(subs)
    assert chunks==[{'start':1.8,'end':3.1,'text':'Chào mọi người!'}]


def test_caption_word_times_follow_source_cuts(media):
    from editing import mapped_subtitles
    plan=new_project(media)['edit_plan'];aid=plan['assets'][0]['id']
    plan['video_clips']=[{**plan['video_clips'][0],'source_in':2,'duration':2,'timeline_start':0}]
    plan['subtitles']=[{'asset_id':aid,'start':1,'end':3,'text':'Chào mọi người!', 'words':[
        {'start':1,'end':1.5,'word':' Chào'}, {'start':2.1,'end':2.4,'word':' mọi'},
        {'start':2.4,'end':2.8,'word':' người!'}]}]
    out=mapped_subtitles(plan)[0]
    assert out['text']=='mọi người!'
    assert out['words'][0]['start']==pytest.approx(.1)
