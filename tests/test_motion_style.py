import copy,json,re,subprocess,threading
from pathlib import Path
import pytest
from motion_style import apply_motion_style,skill_context,motion_skills
from storyboard_style import write_storyboard_ass
from typography import apply_typography
from test_pipeline import client,media,new_project
import main,automatic_director


def plan():
    speeches=['Học hơi thở chậm, giữ vai thả lỏng.','Bước đầu giữ vai thả lỏng, sau đó thở chậm.','Bạn hãy theo dõi để tập cùng mỗi ngày.']
    return {'subtitles':[{'asset_id':'s','start':i*5,'end':(i+1)*5,'text':text} for i,text in enumerate(speeches)],
            'video_clips':[{'asset_id':'s','source_in':0,'source_out':15,'timeline_start':0,'duration':15}],
            'assets':[],'effect_keyframes':[{'id':'old','origin':'auto','timeline_start':0,'duration':3,'scale':1.1}],
            'storyboard':[{'scene_type':'talking_head','timeline_start':0,'duration':5,'headline':'HỌC HƠI THỞ CHẬM'},
                          {'scene_type':'explainer_card','timeline_start':5,'duration':5,'headline':'GIỮ VAI THẢ LỎNG','graphic_kind':'process','graphic_items':['Giữ vai thả lỏng','Thở chậm'],'sound_volume':.1},
                          {'scene_type':'talking_head','timeline_start':10,'duration':5,'headline':'TẬP CÙNG MỖI NGÀY'}],
            'director':{},'text_overlays':[]}


def test_pack_is_bounded_conditional_and_no_reference_claims(tmp_path):
    pack=motion_skills();assert len(pack)==10
    assert sum(len(s['rule']) for s in pack)<=1800
    selected=skill_context(plan(),'dynamic_explainer');assert 'progressive_list' in {s['id'] for s in selected}
    assert 'grounded_numbers' not in {s['id'] for s in selected}
    assert skill_context(plan(),'clean')==[]
    assert skill_context(plan(),'dynamic_explainer','Không hiệu ứng')==[]
    bad=tmp_path/'bad.json';bad.write_text('{bad');assert motion_skills(bad)==[]
    assert len(client.get('/api/learning').json()['available_motion_skills'])==10
    assert not any(term in json.dumps(pack,ensure_ascii=False) for term in ['ABM','199.000','5.000.000','NGÀY 1'])


def test_adapter_preserves_voice_timing_source_and_is_repeatable():
    original=plan();before=copy.deepcopy(original)
    result=apply_motion_style(original,'dynamic_explainer')
    assert original==before
    assert result['subtitles']==before['subtitles'] and result['video_clips']==before['video_clips']
    assert result['storyboard'][1]['motion']['stagger']
    assert result['storyboard'][0]['motion']['accent_words']==2
    assert result['storyboard'][-1]['motion']['closing_text'].startswith('theo dõi')
    assert result['storyboard'][1]['sound_volume']==.07
    assert result['effect_keyframes'][0]['scale']==1.065
    again=apply_motion_style(result,'dynamic_explainer')
    assert again==result
    assert apply_motion_style(plan(),'clean')==plan()
    assert not any(e.get('origin')=='motion_skill' for e in apply_motion_style(result,'clean')['effect_keyframes'])


def test_never_emphasizes_unsupported_labels_or_invented_prices():
    p=plan();p['storyboard'][1]['graphic_items']=['Giá tốt nhất','Giảm 90%']
    p['storyboard'][0]['headline']='CHỈ 199.000 VNĐ'
    r=apply_motion_style(p,'dynamic_explainer')
    assert not r['storyboard'][1]['motion']['stagger']
    assert r['storyboard'][0]['motion']['accent_words']==0
    assert not r['motion_style']['number_scene_indices']
    p['subtitles'][-1]['text']='Hít thở và giữ cơ thể thoải mái.'
    assert not apply_motion_style(p,'dynamic_explainer')['motion_style']['cta_scene_indices']


def test_reveal_requires_reading_time_and_preserves_uploaded_picture():
    p=plan();p['storyboard'][1]['duration']=1
    assert not apply_motion_style(p,'dynamic_explainer')['storyboard'][1]['motion']['stagger']
    p=plan();p['storyboard'][1]['visual_asset_id']='my-photo'
    assert not apply_motion_style(p,'dynamic_explainer')['storyboard'][1]['motion']['stagger']


def test_explicit_opt_out_blocks_all_motion_and_new_copy(tmp_path):
    p=apply_motion_style(plan(),'dynamic_explainer','Không hiệu ứng, không chữ, không âm thanh')
    assert p['effect_keyframes']==[]
    assert all(not s['motion']['animate'] and not s['motion']['stagger'] and not s['headline'] and s['sound_effect']=='none' for s in p['storyboard'])
    assert p['subtitles']==plan()['subtitles']  # caption visibility remains the director's explicit decision
    path=tmp_path/'static.ass';write_storyboard_ass(path,p,720,1280)
    assert '\\move' not in path.read_text(encoding='utf-8') and '\\fad' not in path.read_text(encoding='utf-8')


def test_ass_accent_is_literal_time_bounded_and_does_not_repeat_subtitles(tmp_path):
    p=apply_typography(apply_motion_style(plan(),'dynamic_explainer'),'impact')
    p['storyboard'][0]['headline']='{\\pos(0,0)} Chữ riêng'
    path=tmp_path/'styled.ass';write_storyboard_ass(path,p,720,1280);text=path.read_text(encoding='utf-8')
    assert '{\\pos(0,0)}' not in text
    assert '\\c&H00C8F2FF&' in text and '\\fscx96' in text
    assert '0:00:02.60,Head' in text
    caption_lines=[line for line in text.splitlines() if ',Caption,' in line and line.startswith('Dialogue:')]
    rendered=' '.join(line.split('}',1)[1].replace('\\N',' ') for line in caption_lines)
    assert rendered.split()==' '.join(s['text'] for s in p['subtitles']).split()


def test_invalid_api_style_rejected():
    assert client.post('/api/projects/missing/make-video',json={'motion_style':'reference_file_path'}).status_code==422


def test_director_receives_selected_motion_rules_without_schema_growth(media,tmp_path,monkeypatch):
    p=new_project(media)['edit_plan'];p['subtitles']=[{'start':0,'end':4,'text':'Học hơi thở chậm.'}]
    p['learning_context']={'motion_skills':skill_context(p,'dynamic_explainer')}
    def reply(messages,event,schema):
        ctx=json.loads(messages[1]['content'])
        assert ctx['style_guidance']['motion_skills']
        assert 'motion' not in schema['properties']
        return json.dumps({'summary':'Giữ lời','scenes':[{'i':s['scene_index'],'t':'talking_head','h':'Học hơi thở chậm'} for s in ctx['scenes']]})
    monkeypatch.setattr(automatic_director,'chat',reply)
    result=automatic_director.automatic_direction(p,'Giữ lời nói',main.ASSETS_DIR,tmp_path,threading.Event())
    assert result['subtitles'][0]['text']=='Học hơi thở chậm.'


def test_rule_lists_require_enumeration_confidence_and_opt_in():
    from motion_style import source_list
    assert source_list('Chia thành 2 nhóm, nội sinh và ngoại sinh.')==['nội sinh','ngoại sinh']
    assert source_list('Thở chậm, thả lỏng, nhẹ nhàng.')==[]
    assert source_list('Thứ nhất giữ vai thả lỏng; thứ hai thở chậm.')==['giữ vai thả lỏng','thở chậm']
    p=plan();p['director']['engine']='rules';p['storyboard'][1]['scene_type']='talking_head'
    p['subtitles'][1]['text']='Thứ nhất giữ vai thả lỏng; thứ hai thở chậm.'
    r=apply_motion_style(p,'dynamic_explainer');assert r['storyboard'][1]['scene_type']=='talking_head' # No ASR confidence or reviewed words.
    p['user_subtitles']=copy.deepcopy(p['subtitles'])
    r=apply_motion_style(p,'dynamic_explainer');assert r['storyboard'][1]['motion']['stagger']
    p['branding']={'illustrations':False}
    assert apply_motion_style(p,'dynamic_explainer')['storyboard'][1]['scene_type']=='talking_head'


@pytest.mark.parametrize('animate',[True,False])
def test_actual_staggered_list_render_and_no_effects(animate,tmp_path):
    from storyboard_compiler import run
    from editing import probe
    cfg={'scene_type':'explainer_card','duration':3.5,'headline':'HỌC HƠI THỞ CHẬM',
         'graphic_items':['Giữ vai thả lỏng','Thở chậm'],'graphic_kind':'process','asset_path':str(tmp_path/'graphic.png'),
         'motion_style':'dynamic_explainer','motion':{'stagger':True,'accent_words':2,'animate':animate}}
    from PIL import Image
    Image.new('RGB',(600,460),'white').save(cfg['asset_path'])
    inp=tmp_path/'scene.json';inp.write_text(json.dumps(cfg));out=tmp_path/'scene.mp4'
    run(['node',str(main.BASE_DIR/'motion_engine/render_scene.js'),'--input',str(inp),'--output',str(out),'--width','360','--height','640','--fps','10'])
    assert abs(probe(out)['duration']-3.5)<.11
    subprocess.run(['ffmpeg','-v','error','-xerror','-i',str(out),'-f','null','-'],check=True)
    def frame(t):
        import numpy as np
        data=subprocess.check_output(['ffmpeg','-v','error','-ss',str(t),'-i',str(out),'-frames:v','1','-f','rawvideo','-pix_fmt','rgb24','-'])
        return np.frombuffer(data,dtype='uint8').reshape(640,360,3).astype('int16')
    a,b=frame(.1),frame(2.8)
    if animate:assert abs(a-b).mean()>2
    else:assert abs(a-b).mean()<.5
