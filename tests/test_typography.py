import json
import threading
from pathlib import Path
import pytest
from PIL import ImageFont
from fontTools.ttLib import TTFont
from typography import PROFILES, FONT_DIR, apply_typography, font_path
from storyboard_style import write_storyboard_ass
from text_review import headline_layout
from test_pipeline import client, media, new_project
import automatic_director

VIETNAMESE='ÀÁẢÃẠĂẰẮẲẴẶÂẦẤẨẪẬĐÈÉẺẼẸÊỀẾỂỄỆÌÍỈĨỊÒÓỎÕỌÔỒỐỔỖỘƠỜỚỞỠỢÙÚỦŨỤƯỪỨỬỮỰỲÝỶỸỴ'

@pytest.mark.parametrize('profile',list(PROFILES.values()),ids=list(PROFILES))
def test_fonts_cover_vietnamese_and_measure_real_headings(profile):
    for role in ('caption','heading'):
        path=font_path(profile,role)
        font=TTFont(path)
        assert set(map(ord,VIETNAMESE+VIETNAMESE.lower()))<=set(font.getBestCmap())
        assert font['name'].getDebugName(16)==profile['font_family']
        assert font['OS/2'].usWeightClass==profile[role+'_weight']
    text,size=headline_layout('Ý TƯỞNG MỚI MỖI NGÀY',font_path=font_path(profile,'heading'))
    font=ImageFont.truetype(str(font_path(profile,'heading')),size)
    assert all(font.getlength(line)<=640 for line in text.splitlines())


def test_font_selection_priority_and_old_plans():
    p={'subtitles':[{'text':'Giới thiệu công nghệ trí tuệ nhân tạo'}],'director':{'engine':'ollama','font_style':'story'}}
    assert apply_typography(p)['typography']['profile_id']=='story'
    assert apply_typography(p,'tutorial')['typography']['selected_by']=='user'
    assert apply_typography(p,'tutorial')['typography']['profile_id']=='tutorial'
    p['director']['engine']='rules'
    result=apply_typography(p)
    assert result['typography']['profile_id']=='technology' and result['typography']['selected_by']=='rules'
    assert apply_typography(p,prompt='Video kể chuyện')['typography']['profile_id']=='story'
    assert apply_typography(p,prompt='Dùng font Lora')['typography']['profile_id']=='story'
    assert 'typography' not in p
    with pytest.raises(ValueError):apply_typography(p,'../../font.ttf')


def test_catalog_and_invalid_api_selection():
    r=client.get('/api/typography');assert r.status_code==200
    assert len(r.json()['profiles'])==10
    assert len({p['font_family'] for p in r.json()['profiles']})==10
    assert client.post('/api/projects/missing/make-video',json={'font_style':'unknown'}).status_code==422
    for p in r.json()['profiles']:
        assert client.get(p['caption_url']).status_code==200


def test_ai_schema_selects_one_profile_preserves_source(media,tmp_path,monkeypatch):
    p=new_project(media)['edit_plan'];p['subtitles']=[{'start':0,'end':4,'text':'Nội dung hiện tại.'}]
    def reply(messages,event,schema):
        assert 'font_style' in schema['properties']
        assert len(schema['properties']['font_style']['enum'])==11
        data=json.loads(messages[1]['content'])
        return json.dumps({'summary':'Giữ lời','font_style':'editorial','scenes':[{'i':u['scene_index'],'t':'talking_head','h':'Nội dung hiện tại'} for u in data['scenes']]})
    monkeypatch.setattr(automatic_director,'chat',reply)
    result=automatic_director.automatic_direction(p,'Giữ lời',Path('.'),tmp_path,threading.Event())
    styled=apply_typography(result)
    assert styled['typography']['profile_id']=='editorial'
    assert styled['subtitles'][0]['text']==p['subtitles'][0]['text']


@pytest.mark.parametrize('identifier',list(PROFILES))
def test_ass_applies_fonts_without_dropping_caption_words(identifier,tmp_path):
    speech=' '.join(['Đây là những thông tin tiếng Việt quan trọng cần đọc đầy đủ.']*3)
    p={'subtitles':[{'asset_id':'source','start':0,'end':12,'text':speech}],'video_clips':[{'asset_id':'source','source_in':0,'source_out':12,'timeline_start':0,'duration':12}], 'storyboard':[], 'text_overlays':[]}
    p=apply_typography(p,identifier)
    path=tmp_path/'caption.ass';write_storyboard_ass(path,p,720,1280)
    text=path.read_text()
    assert 'Style: Caption,'+PROFILES[identifier]['font_family'] in text
    captions=[line.split('}',1)[-1].replace('\\N',' ') for line in text.splitlines() if line.startswith('Dialogue:')]
    assert ' '.join(captions).split()==speech.split()
    assert all(line.count('\\N')<=1 for line in text.splitlines() if line.startswith('Dialogue:'))


@pytest.mark.parametrize('identifier',list(PROFILES))
def test_libass_uses_actual_family_and_each_role_weight(identifier,tmp_path):
    import subprocess
    profile=PROFILES[identifier]
    plan={'subtitles':[{'asset_id':'source','start':0,'end':1,'text':'Tiếng Việt đầy đủ dấu.'}],
          'video_clips':[{'asset_id':'source','source_in':0,'source_out':1,'timeline_start':0,'duration':1}],
          'storyboard':[{'scene_type':'talking_head','timeline_start':0,'duration':1,'headline':'Ý TƯỞNG MỚI'}]}
    path=tmp_path/'fonts.ass';write_storyboard_ass(path,apply_typography(plan,identifier),720,1280)
    result=subprocess.run(['ffmpeg','-f','lavfi','-i','color=s=720x1280:r=10:d=1','-vf',f'subtitles={path}:fontsdir={FONT_DIR}','-f','null','-'],capture_output=True,text=True)
    assert result.returncode==0,result.stderr
    for weight in {profile['caption_weight'],profile['heading_weight']}:
        assert f"fontselect: ({profile['font_family']}, {weight}, 0) -> AVStudio" in result.stderr
    assert 'failed to find any fallback' not in result.stderr
