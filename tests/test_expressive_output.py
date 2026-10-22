"""Verify visible effects, source provenance and the three-panel product flow."""
import copy
import subprocess
import threading
from html.parser import HTMLParser

import numpy as np
import pytest

import main
from automatic_director import fallback_direction
from editing import compile_render, length, probe, validate
from storyboard_style import write_storyboard_ass
from style_presets import apply_style_preset
from typography import apply_typography
from test_pipeline import client, media, new_project


def styled(media,aligned=True):
    p=new_project(media)['edit_plan'];aid=p['assets'][0]['id']
    words=[{'word':word,'start':i+.1,'end':i+.8,'probability':.95}
           for i,word in enumerate(['Mỗi','ngày','một','bước.'])]
    p['subtitles']=[{'asset_id':aid,'start':0,'end':4,'text':'Mỗi ngày một bước.',
                     'words':words if aligned else []}]
    p=fallback_direction(p,'Giữ nguyên nguồn',threading.Event(),'CONTROLLED_TEST')
    return apply_typography(apply_style_preset(p,'inspirational'),'energetic')


def test_root_has_exactly_three_panels_and_no_optional_editor_controls():
    class Page(HTMLParser):
        def __init__(self):
            super().__init__()
            self.panels = []
            self.main_forms = []
            self.in_extra = False
            self.extra_details = False
            self.extra_open = False
        def handle_starttag(self, tag, attrs):
            attrs = dict(attrs)
            if tag == 'section' and 'data-panel' in attrs:
                self.panels.append(attrs.get('data-panel'))
            if tag == 'details' and attrs.get('id') == 'extra-resources':
                self.in_extra = True
                self.extra_details = True
                self.extra_open = 'open' in attrs
            if not self.in_extra and tag in ('textarea', 'select', 'input'):
                self.main_forms.append((tag, attrs))
        def handle_endtag(self, tag):
            if tag == 'details' and self.in_extra:
                self.in_extra = False

    page = Page()
    html = client.get('/frontend/index.html').text
    page.feed(html)
    # The primary workflow must strictly preserve the 3 simple panels
    assert page.panels == ['upload', 'style', 'output']
    # The 3 primary panels contain only the video file input
    assert [tag for tag, _ in page.main_forms] == ['input']
    assert page.main_forms[0][1]['type'] == 'file'
    # The extra resources section is collapsible and closed by default
    assert page.extra_details is True
    assert page.extra_open is False
    assert 'id="extra-resources"' in html
    assert 'Tài nguyên &amp; yêu cầu thêm' in html
    assert 'id="input-prompt"' in html
    assert 'id="btn-upload-logo"' in html
    assert 'id="btn-upload-music"' in html
    assert '/frontend/studio.js' in html and '/frontend/studio.css' in html
    assert 'id="render"' in html and 'id="download"' in html


def test_colored_word_captions_use_only_actual_alignment_and_escape_copy(media,tmp_path):
    p=styled(media);path=tmp_path/'words.ass';write_storyboard_ass(path,p,720,1280)
    text=path.read_text(encoding='utf-8');rows=[r for r in text.splitlines() if r.startswith('Dialogue: 1,')]
    assert len(rows)==4
    assert ',0:00:00.10,0:00:01.10,Caption,' in rows[0]
    assert ',0:00:03.10,0:00:03.80,Caption,' in rows[-1]
    assert '\\c&H0000E6FF&' in rows[0] and '\\fscx125' in rows[0]
    assert rows[0].index('\\c&H0000E6FF&')<rows[0].index('Mỗi')
    p['subtitles'][0]['text']='{\\pos(1,1)} ký tự';p['subtitles'][0]['words']=[]
    write_storyboard_ass(path,p,720,1280)
    assert '{\\pos(1,1)}' not in path.read_text(encoding='utf-8')


def test_unaligned_srt_gets_phrase_design_without_fake_word_highlights(media,tmp_path):
    p=styled(media,False);path=tmp_path/'phrase.ass';write_storyboard_ass(path,p,720,1280)
    rows=[r for r in path.read_text(encoding='utf-8').splitlines() if r.startswith('Dialogue: 1,')]
    assert len(rows)==2
    assert ',0:00:00.00,0:00:03.00,Caption,' in rows[0]
    assert ',0:00:03.00,0:00:04.00,Caption,' in rows[1]
    assert '\\c&H0000E6FF&' in rows[0]


def test_source_cutaway_is_brief_and_maps_back_to_original_source(media):
    p=styled(media);template=p['storyboard'][0]
    p['storyboard']=[{**copy.deepcopy(template),'scene_id':str(i),'timeline_start':start,'duration':duration}
        for i,(start,duration) in enumerate([(0,.4),(.4,3.2),(3.6,.4)])]
    before=copy.deepcopy(p)
    result=validate(apply_style_preset(p,'real_estate'),p['assets'])
    frames=[s for s in result['storyboard'] if s.get('source_cutaway')]
    assert len(frames)==1 and frames[0]['duration']==pytest.approx(1.4)
    assert frames[0]['source_in']==pytest.approx(2.2)
    assert frames[0]['source_out']==pytest.approx(3.6)
    assert frames[0]['source_photo_label']=='KHUNG HÌNH TỪ VIDEO GỐC'
    assert not frames[0]['headline']
    assert result['subtitles']==before['subtitles'] and result['video_clips']==before['video_clips']
    assert length(result)==4
    assert apply_style_preset(result,'real_estate')['style_preset']['source_frame_count']==1


@pytest.mark.parametrize('direction',['in','out'])
def test_real_render_zoom_direction_changes_subject_size(tmp_path,direction):
    grid=tmp_path/'grid.mp4'
    subprocess.run(['ffmpeg','-v','error','-y','-f','lavfi','-i','color=c=0x184c52:s=240x320:r=30:d=4',
        '-vf','drawbox=x=70:y=110:w=100:h=100:color=red:t=fill','-c:v','libx264','-pix_fmt','yuv420p',str(grid)],check=True)
    p=client.post('/api/projects',data={'name':'Zoom output geometry'}).json()
    with grid.open('rb') as f:
        p=client.post(f'/api/projects/{p["id"]}/upload',files={'file':('grid.mp4',f)},data={'role':'main'}).json()
    plan=p['edit_plan'];plan['effect_keyframes']=[{'id':'zoom','timeline_start':0,'duration':4,'scale':1.15,'direction':direction}]
    out=tmp_path/'zoom.mp4';cmd,_=compile_render(plan,main.ASSETS_DIR,tmp_path,out)
    subprocess.run(cmd,check=True,capture_output=True)
    def subject_width(t):
        raw=subprocess.run(['ffmpeg','-v','error','-ss',str(t),'-i',str(out),'-frames:v','1','-f','rawvideo','-pix_fmt','rgb24','-'],check=True,capture_output=True).stdout
        image=np.frombuffer(raw,dtype=np.uint8).reshape((320,240,3))
        mask=(image[:,:,0]>180)&(image[:,:,1]<100)&(image[:,:,2]<100)
        xs=np.where(mask.any(axis=0))[0];return xs[-1]-xs[0]+1
    start,end=subject_width(.25),subject_width(3.75)
    assert end>start+8 if direction=='in' else end<start-8
    assert probe(out)['duration']==pytest.approx(4,abs=.05)
