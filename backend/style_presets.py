"""Product presets over the shared editor; no third-party skill code is bundled.

Style preferences are separate from the factual brief. Presets never authorize
cuts, invent property facts, download media, or replace a user's source words.
"""
import copy
import re
from typing import Literal

from editing import length, mapped_subtitles
from motion_style import NO_EFFECTS, NO_SOUND, NO_TEXT, grounded_phrase

StylePreset = Literal['explainer', 'inspirational', 'real_estate']
PRESETS = {
    'explainer': {
        'id': 'explainer', 'topic': 'general', 'label': 'Giải thích · Năng động',
        'description': 'Chữ rõ, đồ họa theo lời nói và nhịp dựng hiện tại.',
        'font_style': 'technology', 'max_scene_seconds': 7, 'sentence_seconds': 2.8,
        'caption_words': 5, 'music_volume': .12, 'background':'#102C3A', 'accent':'#FFD352', 'secondary':'#71E0CF',
        'guidance': 'Use relevant explanatory graphics and quiet accents. Preserve meaningful speech.',
        'asset_note': 'Có thể thêm ảnh, logo và nhạc của bạn.',
    },
    'inspirational': {
        'id': 'inspirational', 'topic': 'inspiration', 'label': 'Truyền cảm hứng · Cảm xúc',
        'description': 'Chữ động vàng–cam, nhấn từ theo lời nói và zoom in/out theo nhịp kể chuyện.',
        'font_style': 'energetic', 'max_scene_seconds': 7, 'sentence_seconds': 4.8,
        'caption_words': 4, 'music_volume': .10, 'zoom_scale': 1.12,
        'zoom_seconds': 6, 'zoom_every': 2, 'transition_seconds': .23,
        'headline_seconds': 3.5, 'photo_zoom': .035,
        'background': '#201B29', 'accent': '#FFCA5C', 'secondary':'#FA8975',
        'guidance': 'Emotional storytelling: preserve pauses and complete thoughts. Prefer the speaker and supplied relevant photos over diagrams. Use sparse literal emphasis, slow gentle zoom and fades; no bounce or impact sounds. Never invent motivational quotes or a closing call to action.',
        'asset_note': 'Ảnh và nhạc cảm xúc là tùy chọn; không có ảnh vẫn dựng từ video gốc.',
    },
    'real_estate': {
        'id': 'real_estate', 'topic': 'real_estate', 'label': 'Bất động sản · Sang trọng',
        'description': 'Chữ trắng–gold, thẻ thông tin, khung hình thật và zoom in/out mượt.',
        'font_style': 'business', 'max_scene_seconds': 5.5, 'sentence_seconds': 2.6,
        'caption_words': 6, 'music_volume': .08, 'zoom_scale': 1.07,
        'zoom_seconds': 4.5, 'zoom_every': 3, 'transition_seconds': .17,
        'headline_seconds': 2.8, 'photo_zoom': .018,
        'background': '#112927', 'accent': '#E9C987', 'secondary':'#9EE1C1',
        'guidance': 'Premium property review: prioritize supplied photos of the actual property, show architecture clearly, use restrained fades and small camera movements. No fabricated property photos, diagrams pretending to be floor plans, prices, areas, addresses, legal status, investment promises or contacts. Without supplied property photos keep the original footage. Only show facts present in current speech.',
        'asset_note': 'Thêm ảnh đúng bất động sản để chèn minh họa. Không có ảnh sẽ dùng video gốc; không tự tạo giá, diện tích hay địa chỉ.',
    },
}


def preset_for(identifier):
    if identifier not in PRESETS:
        raise ValueError('Phong cách dựng không hợp lệ.')
    return copy.deepcopy(PRESETS[identifier])


def public_presets():
    keys = ('id', 'topic', 'label', 'description', 'asset_note', 'font_style')
    return [{k: p[k] for k in keys} for p in PRESETS.values()]


def preset_context(identifier):
    p = preset_for(identifier)
    return {'id': identifier, 'rules': p['guidance'], 'preferences_only': True}


def apply_style_preset(plan, identifier='explainer', prompt='', music_asset_id=''):
    """Apply timing-safe presentation after shared visual/typography adapters."""
    preset = preset_for(identifier)
    p = copy.deepcopy(plan)
    p['style_preset'] = {'id': identifier, 'version': 2, 'label': preset['label'],
        'caption_design': identifier!='explainer' or p.get('motion_style',{}).get('preset')=='dynamic_explainer'}
    if 'branding' in p:
        p['branding'].update(style_preset=identifier, music_asset_id=music_asset_id)
    p['audio_tracks'] = [t for t in p.get('audio_tracks', []) if t.get('origin') != 'style_preset']
    no_sound = bool(re.search(NO_SOUND, prompt, re.I))
    no_music = bool(re.search(r'(?:không|tắt|bỏ)\s+(?:thêm |chèn |dùng )?(?:nhạc|music)|no music', prompt, re.I))
    no_effects = bool(re.search(NO_EFFECTS, prompt, re.I))
    no_text = bool(re.search(NO_TEXT, prompt, re.I))
    warnings = p.setdefault('director', {}).setdefault('warnings', [])
    if music_asset_id and not no_sound and not no_music:
        asset = next((a for a in p['assets'] if a['id'] == music_asset_id and a['type'] == 'audio'), None)
        if asset is None:
            raise ValueError('Nhạc nền phải là âm thanh thuộc dự án.')
        # Never stretch a short track or invent a generated soundtrack.
        duration = min(length(p), asset['metadata']['duration'])
        p['audio_tracks'].append({'id': 'preset_music', 'origin': 'style_preset',
            'kind': 'music', 'asset_id': music_asset_id, 'source_in': 0,
            'timeline_start': 0, 'duration': duration, 'volume': preset['music_volume'], 'loop': False})
        if duration < length(p) - .1:
            warnings.append('Nhạc nền ngắn hơn video; nhạc kết thúc nhẹ khi hết file, giọng nói vẫn được giữ.')
    if no_sound:
        p['audio_tracks'] = []  # Original speech is on the source clips, never muted.
    elif no_music:
        p['audio_tracks'] = [t for t in p['audio_tracks'] if t.get('kind')!='music']
    if identifier == 'explainer':
        return p

    p['effect_keyframes'] = [e for e in p.get('effect_keyframes', [])
        if e.get('origin') not in ('auto', 'motion_skill', 'style_preset')]
    if no_effects:
        p['effect_keyframes'] = []
    p['style_preset']['theme'] = {k: preset[k] for k in ('background', 'accent', 'secondary')}
    p['style_preset']['caption_words'] = preset['caption_words']
    p['motion_style'] = {**p.get('motion_style', {}), 'preset': 'dynamic_explainer',
        'effects_disabled': no_effects, 'style_preset': identifier,
        'active_skills': ['source_photos', 'literal_emphasis'] + ([] if no_effects else ['gentle_camera', 'quiet_transitions'])}
    subtitles = mapped_subtitles(p)
    # A single-video workflow can illustrate with its own authentic frames.
    # Split a brief interior cutaway; never freeze the entire take or invent a photo.
    scenes=p.get('storyboard',[])
    allow_cutaway=(p.get('branding',{}).get('illustrations',True) and not no_effects
        and not re.search(r'không (?:thêm |chèn |dùng |cần )?(?:minh họa|đồ họa|hình|ảnh)',prompt,re.I))
    if allow_cutaway and len(scenes)>=2 and not any(s.get('source_cutaway') for s in scenes):
        expanded=[]
        for index,sc in enumerate(scenes):
            if index==(1 if len(scenes)>=3 else 0) and sc['duration']>=3.2 and not sc.get('visual_asset_id'):
                tail=1.4 if identifier=='real_estate' else 1.2
                first=copy.deepcopy(sc);first['duration']-=tail
                last=copy.deepcopy(sc);last.update(scene_id=sc.get('scene_id','scene')+'_source_frame',
                    timeline_start=sc['timeline_start']+first['duration'],duration=tail,source_cutaway=True,suppress_headline=True)
                expanded.extend([first,last])
            else:expanded.append(sc)
        p['storyboard']=expanded
    photos=0;source_frames=0;camera_count=0
    for i, sc in enumerate(p.get('storyboard', [])):
        start, duration = sc['timeline_start'], sc['duration']
        speech = sc.get('transcript_meaning') or ' '.join(s['text'] for s in subtitles
            if s['end'] > start and s['start'] < start + duration)
        visual = next((a for a in p['assets'] if a['id'] == sc.get('visual_asset_id')), None)
        if sc.get('source_cutaway'):
            sc.update(scene_type='explainer_card',photo_layout='full',source_photo_label='KHUNG HÌNH TỪ VIDEO GỐC')
            source_frames+=1
        elif visual and visual['type'] == 'image':
            # Property photos fill the frame. Storytelling alternates picture/speaker.
            sc['photo_layout'] = 'full' if identifier == 'real_estate' or photos % 2 == 0 else 'pip'
            sc['scene_type'] = 'explainer_card' if sc['photo_layout'] == 'full' else 'talking_head_pip'
            photos += 1
        else:
            # A generic library illustration must never pose as a property photo.
            sc['scene_type'] = 'talking_head'
            for key in ('library_visual_id', 'photo_layout', 'visual_asset_id'):
                sc.pop(key, None)
            sc['graphic_title'] = ''; sc['graphic_items'] = []
        # Promote only literal source phrases into emphasis; no preset prose.
        if no_text or sc.get('suppress_headline'):
            sc['headline'] = ''; sc['badge_text'] = ''
        elif not grounded_phrase(sc.get('headline', ''), speech):
            sc['headline'] = ' '.join(speech.split()[:5]).strip(' ,.;:!?')[:80]
        sc['sound_effect'] = 'none'
        sc['sound_volume'] = 0
        sc['animation_in'] = 'fade'
        sc['motion'] = {'animate': not no_effects, 'stagger': False,
            'accent_words': 0, 'headline_seconds': min(duration, preset['headline_seconds']),
            'transition_seconds': 0 if no_effects else preset['transition_seconds'],
            'show_photo_label': not no_text, 'photo_zoom': preset['photo_zoom']}
        sc['style_theme'] = p['style_preset']['theme']
        if not no_effects and sc['scene_type'] == 'talking_head' and duration >= 1.2:
            p['effect_keyframes'].append({'id': f'preset_zoom_{i}', 'origin': 'style_preset',
                'timeline_start': start, 'duration': duration, 'direction':'in' if camera_count%2==0 else 'out',
                'scale': preset['zoom_scale']})
            camera_count+=1
    if no_text:
        p['text_overlays'] = []; p['show_captions'] = False
    if identifier == 'real_estate' and not photos:
        warnings.append('Chưa ghép được ảnh bất động sản phù hợp; bản dựng dùng video gốc, không tạo ảnh tài sản thay thế.')
    p['style_preset']['source_frame_count']=source_frames
    p['director']['illustration_count'] = photos+source_frames
    p['director']['visual_sources'] = [s for s in p['director'].get('visual_sources', []) if s.get('source')=='user_uploaded']
    p['director']['warnings'] = list(dict.fromkeys(warnings))
    return p
