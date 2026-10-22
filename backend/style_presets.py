"""Product presets over the shared editor; no third-party skill code is bundled.

Style preferences are separate from the factual brief. Presets never authorize
cuts, invent property facts, download media, or replace a user's source words.
"""
import copy
import math
import re
from typing import Literal

from editing import length, mapped_subtitles
from motion_style import (
    NO_EFFECTS,
    NO_ZOOM,
    NO_TEXT,
    NO_CAPTIONS,
    NO_SOUND,
    NO_SFX,
    NO_MUSIC,
    NO_ILLUSTRATIONS,
    grounded_phrase,
)

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
        'description': 'Bùng nổ: chữ lớn neon, ảnh minh họa, cắt cảnh nhanh, zoom in/out và âm thanh nhấn.',
        'font_style': 'energetic', 'max_scene_seconds': 7, 'sentence_seconds': 4.8,
        'caption_words': 3, 'music_volume': .10, 'zoom_scale': 1.20,
        'zoom_seconds': 6, 'zoom_every': 2, 'transition_seconds': .23,
        'headline_seconds': 1.8, 'photo_zoom': .09,
        'background': '#21103D', 'accent': '#FFE600', 'secondary':'#44FFE1',
        'guidance': 'Emotional storytelling: preserve pauses and complete thoughts. Prefer the speaker and supplied relevant photos over diagrams. Use frequent relevant illustrations, oversized colorful literal emphasis, punchy zooms, fast transitions and pop/whoosh accents. Never invent motivational quotes or a closing call to action.',
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


def apply_user_overrides(plan, prompt='', options=None):
    """Unified final normalization enforcing strict user opt-outs over styles and presets.

    Order of precedence:
    1. User explicit opt-outs/opt-ins (prompt / options)
    2. Content grounding and factual validity
    3. Valid plan structure
    4. Style guidance & presets
    5. System defaults
    """
    p = copy.deepcopy(plan)
    warnings = p.setdefault('director', {}).setdefault('warnings', [])
    no_effects = bool(re.search(NO_EFFECTS, prompt, re.I))
    no_zoom = bool(re.search(NO_ZOOM, prompt, re.I))
    no_text = bool(re.search(NO_TEXT, prompt, re.I))
    no_captions = bool(re.search(NO_CAPTIONS, prompt, re.I))
    no_sound = bool(re.search(NO_SOUND, prompt, re.I))
    no_sfx = bool(re.search(NO_SFX, prompt, re.I))
    no_music = bool(re.search(NO_MUSIC, prompt, re.I))
    no_illustrations = bool(re.search(NO_ILLUSTRATIONS, prompt, re.I))

    # 1. Sound & Audio overrides
    if no_sound:
        p['audio_tracks'] = []
        for sc in p.get('storyboard', []):
            sc['sound_effect'] = 'none'
            sc['sound_volume'] = 0
    else:
        if no_music:
            p['audio_tracks'] = [t for t in p.get('audio_tracks', []) if t.get('kind') != 'music']
        if no_sfx:
            p['audio_tracks'] = [t for t in p.get('audio_tracks', []) if t.get('kind') != 'sfx' and not str(t.get('id', '')).startswith('sfx_')]
            for sc in p.get('storyboard', []):
                sc['sound_effect'] = 'none'
                sc['sound_volume'] = 0

    # 2. Text & Captions overrides
    if no_text:
        p['show_captions'] = False
        p['text_overlays'] = []
        for sc in p.get('storyboard', []):
            sc['headline'] = ''
            sc['badge_text'] = ''
            sc['graphic_title'] = ''
            sc['graphic_items'] = []
            if 'motion' in sc:
                sc['motion']['closing_text'] = ''
                sc['motion']['show_photo_label'] = False
                sc['motion']['stagger'] = False
            if sc.get('scene_type') == 'explainer_card' and not sc.get('visual_asset_id') and not sc.get('library_visual_id'):
                sc['scene_type'] = 'talking_head'
    elif no_captions:
        p['show_captions'] = False

    # 3. Zoom & Motion Effects overrides
    if no_effects:
        p['effect_keyframes'] = []
        p.setdefault('motion_style', {})['effects_disabled'] = True
        for sc in p.get('storyboard', []):
            sc['animation_in'] = 'none'
            sc['animation_out'] = 'none'
            sc['sound_effect'] = 'none'
            sc['sound_volume'] = 0
            motion = sc.setdefault('motion', {})
            motion['animate'] = False
            motion['stagger'] = False
            motion['transition_seconds'] = 0
            motion['photo_zoom'] = 0
    elif no_zoom:
        p['effect_keyframes'] = [e for e in p.get('effect_keyframes', [])
            if not (e.get('scale', 1.0) != 1.0 or 'zoom' in str(e.get('id', '')))]
        for sc in p.get('storyboard', []):
            if 'motion' in sc:
                sc['motion']['photo_zoom'] = 0

    # 4. Illustrations overrides
    if no_illustrations:
        user_images = p.get('branding', {}).get('image_asset_ids', [])
        user_brolls = p.get('branding', {}).get('broll_asset_ids', [])
        if user_images or user_brolls:
            warnings.append('Yêu cầu không minh họa nhưng có ảnh/B-roll được chọn cụ thể; ưu tiên tài nguyên do bạn chỉ định, bỏ minh họa tự động.')
            for sc in p.get('storyboard', []):
                sc.pop('library_visual_id', None)
                sc.pop('source_cutaway', None)
        else:
            for sc in p.get('storyboard', []):
                sc.pop('library_visual_id', None)
                sc.pop('source_cutaway', None)
                sc.pop('visual_asset_id', None)
                if sc.get('scene_type') in ('explainer_card', 'talking_head_pip', 'broll') and not sc.get('graphic_items'):
                    sc['scene_type'] = 'talking_head'
                    sc['photo_layout'] = 'pip'

    p['director']['warnings'] = list(dict.fromkeys(warnings))
    return p


def apply_style_preset(plan, identifier='explainer', prompt='', music_asset_id=''):
    """Apply timing-safe presentation after shared visual/typography adapters."""
    preset = preset_for(identifier)
    p = copy.deepcopy(plan)
    p['style_preset'] = {'id': identifier, 'version': 3, 'label': preset['label'],
        'caption_design': identifier!='explainer' or p.get('motion_style',{}).get('preset')=='dynamic_explainer'}
    if 'branding' in p:
        p['branding'].update(style_preset=identifier, music_asset_id=music_asset_id)
    p['audio_tracks'] = [t for t in p.get('audio_tracks', []) if t.get('origin') != 'style_preset']
    no_sound = bool(re.search(NO_SOUND, prompt, re.I))
    no_music = bool(re.search(NO_MUSIC, prompt, re.I))
    no_effects = bool(re.search(NO_EFFECTS, prompt, re.I))
    no_zoom = bool(re.search(NO_ZOOM, prompt, re.I))
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
        return apply_user_overrides(p, prompt)

    p['effect_keyframes'] = [e for e in p.get('effect_keyframes', [])
        if e.get('origin') not in ('auto', 'motion_skill', 'style_preset')]
    if no_effects:
        p['effect_keyframes'] = []
    elif no_zoom:
        p['effect_keyframes'] = [e for e in p['effect_keyframes']
            if not (e.get('scale', 1.0) != 1.0 or 'zoom' in str(e.get('id', '')))]

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
        and not re.search(NO_ILLUSTRATIONS, prompt, re.I))
    if allow_cutaway and 2<=len(scenes)<200 and not any(s.get('source_cutaway') for s in scenes):
        expanded=[]
        for index,sc in enumerate(scenes):
            if index==(1 if len(scenes)>=3 else 0) and sc['duration']>=3.2 and not sc.get('visual_asset_id'):
                tail=1.4 if identifier=='real_estate' else 1.2
                first=copy.deepcopy(sc);first['duration']-=tail
                last=copy.deepcopy(sc);last.update(scene_id=sc.get('scene_id','scene')+'_source_frame',
                    timeline_start=sc['timeline_start']+first['duration'],duration=tail,
                    source_in=sc.get('source_in', 0)+first['duration'],source_cutaway=True,suppress_headline=True)
                expanded.extend([first,last])
            else:expanded.append(sc)
        p['storyboard']=expanded

    # Strong preset is deterministic even when the language model is unavailable.
    # Split presentation only: source clips, subtitles and original voice stay intact.
    already_divided = any('_beat' in s.get('scene_id', '') for s in p.get('storyboard', []))
    if identifier == 'inspirational' and not no_effects and not already_divided:
        expanded=[]
        source_scenes=p.get('storyboard', [])
        for index,sc in enumerate(source_scenes):
            budget=200-len(expanded)-(len(source_scenes)-index-1)
            count=max(1,min(budget,math.ceil(sc['duration']/2.4)))
            v_asset = next((a for a in p.get('assets', []) if a['id'] == sc.get('visual_asset_id')), None)
            is_video_broll = bool(v_asset and v_asset.get('type') == 'video' and sc.get('scene_type') == 'broll')
            base_v_src_in = float(sc.get('visual_source_in', 0.0))
            v_dur = float(v_asset.get('metadata', {}).get('duration', 0.0)) if is_video_broll else 0.0
            for n in range(count):
                part=copy.deepcopy(sc)
                offset = sc['duration']*n/count
                part.update(scene_id=sc['scene_id']+f'_beat{n}' if count>1 else sc['scene_id'],
                    timeline_start=sc['timeline_start']+offset,
                    duration=sc['duration']/count,
                    source_in=sc.get('source_in', 0)+offset)
                if is_video_broll:
                    part_dur = sc['duration'] / count
                    v_pos = base_v_src_in + offset
                    if v_pos + part_dur <= v_dur + 0.02:
                        part['visual_source_in'] = v_pos
                        part['scene_type'] = 'broll'
                    else:
                        part['scene_type'] = 'talking_head'
                        part.pop('visual_asset_id', None)
                        part.pop('visual_source_in', None)
                expanded.append(part)
        p['storyboard']=expanded

    photos=0;source_frames=0;camera_count=0
    for i, sc in enumerate(p.get('storyboard', [])):
        start, duration = sc['timeline_start'], sc['duration']
        speech = sc.get('transcript_meaning') or ' '.join(s['text'] for s in subtitles
            if s['end'] > start and s['start'] < start + duration)
        if identifier == 'inspirational' and allow_cutaway and i % 3 == 1 and not sc.get('visual_asset_id'):
            from visual_library import catalog, phrase_in
            matches=[entry for entry in catalog() if any(phrase_in(k,speech) for k in entry['keywords'])]
            if matches:
                sc.pop('source_cutaway',None)
                sc.update(library_visual_id=matches[0]['id'],photo_layout='full',scene_type='explainer_card')
        visual = next((a for a in p['assets'] if a['id'] == sc.get('visual_asset_id')), None)
        items = sc.get('graphic_items', [])
        has_grounded_items = bool(items) and all(grounded_phrase(item, speech) for item in items)
        if sc.get('source_cutaway'):
            sc.update(scene_type='explainer_card',photo_layout='full',source_photo_label='KHUNG HÌNH TỪ VIDEO GỐC')
            source_frames+=1
        elif identifier == 'inspirational' and sc.get('library_visual_id') and allow_cutaway:
            sc.update(scene_type='explainer_card',photo_layout='full',source_photo_label='ẢNH MINH HỌA')
            photos += 1
        elif visual and visual['type'] == 'image':
            # Property photos fill the frame. Storytelling alternates picture/speaker.
            sc['photo_layout'] = 'full' if identifier == 'real_estate' or photos % 2 == 0 else 'pip'
            sc['scene_type'] = 'explainer_card' if sc['photo_layout'] == 'full' else 'talking_head_pip'
            photos += 1
        elif visual and visual['type'] == 'video':
            # Authentic user-provided video B-roll: preserve footage, type, and source in
            sc['scene_type'] = 'broll'
            sc.pop('library_visual_id', None)
            sc.pop('photo_layout', None)
            photos += 1
        elif has_grounded_items and sc.get('scene_type') in ('explainer_card', 'talking_head_pip'):
            # Valid explanatory/info graphic card grounded with speech: keep content intact!
            sc['scene_type'] = 'explainer_card'
            sc.pop('library_visual_id', None)
            sc.pop('visual_asset_id', None)
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
        sc['sound_effect'] = ('whoosh' if i%2 else 'pop') if identifier=='inspirational' and not no_sound and not no_effects and i < 100-len(p['audio_tracks']) else 'none'
        sc['sound_volume'] = .16 if sc['sound_effect']!='none' else 0
        sc['animation_in'] = 'none' if no_effects else 'fade'
        sc['animation_out'] = 'none' if no_effects else sc.get('animation_out', 'none')
        sc['motion'] = {'animate': not no_effects, 'stagger': identifier=='inspirational' and not no_effects,
            'accent_words': 0, 'headline_seconds': min(duration, preset['headline_seconds']),
            'transition_seconds': 0 if no_effects else preset['transition_seconds'],
            'show_photo_label': not no_text, 'photo_zoom': 0 if (no_effects or no_zoom) else preset['photo_zoom']}
        sc['style_theme'] = p['style_preset']['theme']
        if not no_effects and not no_zoom and sc['scene_type'] == 'talking_head' and duration >= 1.2:
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
    return apply_user_overrides(p, prompt)
