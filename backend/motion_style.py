"""Reference-derived, opt-in motion adapter; never learns source claims or timing."""
import copy
import json
import re
from typing import Literal
from project_paths import SKILLS_DIR

MotionStyle = Literal['clean', 'dynamic_explainer']
NO_EFFECTS = r'(?:không|tắt|bỏ|đừng|ko)\s+(?:thêm |chèn |dùng |cần )?(?:hiệu ứng|chuyển động|animation|motion)|no effects'
NO_ZOOM = r'(?:không|tắt|bỏ|đừng|ko)\s+(?:thêm |chèn |dùng |cần )?(?:zoom|phóng to|thu nhỏ)|no zoom'
NO_TEXT = r'(?:không|tắt|bỏ|đừng|ko)\s+(?:thêm |chèn |dùng |cần )?(?:chữ|text|tiêu đề|headline)|no text'
NO_CAPTIONS = r'(?:không|tắt|bỏ|đừng|ko)\s+(?:thêm |chèn |dùng |cần )?(?:phụ đề|subtitles|caption|sub)|no (?:subtitles|captions|sub)'
NO_SOUND = r'(?:không|tắt|bỏ|no|đừng|ko)\s+(?:thêm |chèn |dùng |cần )?(?:âm thanh|tiếng|sound)'
NO_SFX = r'(?:không|tắt|bỏ|no|đừng|ko)\s+(?:thêm |chèn |dùng |cần )?(?:sfx|âm thanh hiệu ứng|tiếng động|tiếng whoosh|tiếng pop)|no sfx'
NO_MUSIC = r'(?:không|tắt|bỏ|no|đừng|ko)\s+(?:thêm |chèn |dùng |cần )?(?:nhạc|music|nhạc nền|bgr? music)|no music'
NO_ILLUSTRATIONS = r'(?:không|tắt|bỏ|đừng|ko)\s+(?:thêm |chèn |dùng |cần )?(?:minh họa|đồ họa|hình ảnh|ảnh|b-roll|cutaway)|no (?:illustrations|graphics|images)'
CTA = re.compile(r'\b(?:đăng ký|theo dõi|liên hệ|bình luận|chia sẻ|lưu lại|đặt lịch)\b', re.I)
NUMBER = re.compile(r'\b\d+(?:[.,]\d+)*\s*(?:VNĐ|VND|đồng|triệu|phút|ngày|giờ|%)', re.I)


def motion_skills(path=None):
    try:
        data=json.loads((path or SKILLS_DIR/'motion_skills.json').read_text(encoding='utf-8'))
        skills=data['skills']
        if data['schema_version']!=1 or not isinstance(skills,list) or len(skills)>12: return []
        ids=set()
        for skill in skills:
            if not isinstance(skill,dict) or not isinstance(skill.get('id'),str) or not 1<=len(skill['id'])<=40 or skill['id'] in ids: return []
            ids.add(skill['id'])
            if not isinstance(skill.get('rule'),str) or not 1<=len(skill['rule'])<=240 or not isinstance(skill.get('enabled'),bool):return []
            if not isinstance(skill.get('triggers'),list) or any(t not in ('always','lists','assets','numbers','cta') for t in skill['triggers']):return []
        return [s for s in skills if s['enabled']]
    except (OSError,ValueError,KeyError,TypeError):return []


def skill_context(plan, requested, prompt=''):
    if requested!='dynamic_explainer' or re.search(NO_EFFECTS,prompt,re.I):return []
    text=' '.join(s.get('text','') for s in plan.get('subtitles',[]))
    triggers={'always'}
    if re.search(r'[,;:]|thứ nhất|thứ hai|đầu tiên|bước',text,re.I):triggers.add('lists')
    if any(a.get('type')=='image' for a in plan.get('assets',[])) or any(sc.get('library_visual_id') for sc in plan.get('storyboard',[])):triggers.add('assets')
    if NUMBER.search(text):triggers.add('numbers')
    if CTA.search(text):triggers.add('cta')
    selected=[{'id':s['id'],'rule':s['rule']} for s in motion_skills() if triggers.intersection(s['triggers'])]
    # Keep all source content; bound extra guidance independently of base skills.
    return selected if sum(len(s['rule']) for s in selected)<=1800 else []


def words(text):
    return re.findall(r'[^\W_]+',text.casefold())


def grounded_phrase(phrase, speech):
    needle=words(phrase);haystack=words(speech)
    return bool(needle) and any(haystack[i:i+len(needle)]==needle for i in range(len(haystack)-len(needle)+1))


def source_list(speech):
    """Extract literal, explicitly enumerated source phrases, never a new list."""
    pair=re.search(r'(?:hai|2)\s+nhóm[.,:]?\s+([^.,;!?]{1,50}?)\s+và\s+([^.,;!?]{1,50})(?:[.,;!?]|$)',speech,re.I)
    if pair:
        items=[x.strip(' ,:') for x in pair.groups()]
        return items if all(1<=len(x.split())<=5 for x in items) else []
    markers=list(re.finditer(r'(?:thứ nhất|thứ hai|thứ ba|đầu tiên|tiếp theo|cuối cùng)\s*[:,]?\s*',speech,re.I))
    if len(markers)<2:return []
    items=[]
    for i,marker in enumerate(markers[:5]):
        end=markers[i+1].start() if i+1<len(markers) else len(speech)
        excerpt=re.split(r'[.;!?]',speech[marker.end():end],maxsplit=1)[0].strip(' ,:')
        if not 1<=len(excerpt.split())<=7 or len(excerpt)>60:return []
        items.append(excerpt)
    return items if len(items)==len(set(x.casefold() for x in items)) else []


def apply_motion_style(plan, requested='clean', prompt=''):
    if requested not in ('clean','dynamic_explainer'):raise ValueError('Unknown motion style')
    p=copy.deepcopy(plan)
    # Remove only the adapter's state; retrying never accumulates motion.
    p.pop('motion_style',None)
    p['effect_keyframes']=[e for e in p.get('effect_keyframes',[]) if e.get('origin')!='motion_skill']
    for sc in p.get('storyboard',[]):sc.pop('motion',None)

    no_effects=bool(re.search(NO_EFFECTS,prompt,re.I))
    no_zoom=bool(re.search(NO_ZOOM,prompt,re.I))
    no_text=bool(re.search(NO_TEXT,prompt,re.I))
    no_sound=bool(re.search(NO_SOUND,prompt,re.I))
    no_sfx=bool(re.search(NO_SFX,prompt,re.I))

    if requested=='clean':
        if no_effects:
            p['effect_keyframes']=[]
            for sc in p.get('storyboard',[]):
                sc['animation_in']='none'
                sc['animation_out']='none'
                sc['sound_effect']='none'
                sc['sound_volume']='none' if False else 0
                motion=sc.setdefault('motion',{})
                motion['animate']=False
                motion['transition_seconds']=0
                motion['photo_zoom']=0
                motion['stagger']=False
        elif no_zoom:
            p['effect_keyframes']=[e for e in p.get('effect_keyframes',[]) if not (e.get('scale',1.0)!=1.0 or 'zoom' in str(e.get('id','')))]
            for sc in p.get('storyboard',[]):
                if 'motion' in sc:
                    sc['motion']['photo_zoom']=0
        if no_sound or no_sfx:
            for sc in p.get('storyboard',[]):
                sc['sound_effect']='none'
                sc['sound_volume']=0
        if no_text:
            for sc in p.get('storyboard',[]):
                sc['headline']=''
                sc['badge_text']=''
        return p

    context=skill_context(p,requested,prompt)
    enabled={s['id'] for s in context}
    if no_effects:
        p['effect_keyframes']=[]
    elif no_zoom:
        p['effect_keyframes']=[e for e in p.get('effect_keyframes',[]) if not (e.get('scale',1.0)!=1.0 or 'zoom' in str(e.get('id','')))]
    elif 'camera_breath' in enabled:
        p['effect_keyframes']=[e for e in p.get('effect_keyframes',[]) if e.get('origin') not in ('auto','motion_skill')]

    statistics=[];cta=[];camera=0;added_list=False
    allow_lists=('progressive_list' in enabled and not no_text and p.get('branding',{}).get('illustrations',True) and not re.search(r'không (?:thêm |chèn |dùng |cần )?(?:minh họa|đồ họa|hình)',prompt,re.I))
    photos=0
    for index,sc in enumerate(p.get('storyboard',[])):
        visual=next((a for a in p.get('assets',[]) if a.get('id')==sc.get('visual_asset_id')),None)
        if visual and visual.get('type')=='image':
            sc['photo_layout']='full' if photos%2==0 else 'pip'
            sc['scene_type']='explainer_card' if sc['photo_layout']=='full' else 'talking_head_pip'
            photos+=1
        elif visual and visual.get('type')=='video':
            sc['scene_type']='broll'
            sc.pop('photo_layout',None)
            photos+=1
        start=sc['timeline_start'];end=start+sc['duration']
        subs=[s for s in p.get('subtitles',[]) if s['end']>start and s['start']<end]
        timed=[w for sub in subs for w in sub.get('words',[]) if w['end']>start and w['start']<end]
        speech=sc.get('transcript_meaning') or (' '.join(w['word'].strip() for w in timed) if timed else ' '.join(s['text'] for s in subs))
        if allow_lists and not added_list and p.get('director',{}).get('engine')=='rules' and 0<index<len(p['storyboard'])-1 and sc['scene_type']=='talking_head':
            items=source_list(speech)
            label_words=set(words(' '.join(items)))
            aligned=[w for w in timed if label_words.intersection(words(w['word']))]
            credible=bool(p.get('user_subtitles')) or bool(aligned) and all(w.get('probability',0)>=.75 for w in aligned)
            if items and credible and sc['duration']>=1.2+.55*len(items):
                sc.update(scene_type='explainer_card',graphic_kind='process',graphic_items=items,graphic_title=items[0],sound_effect='none')
                if not grounded_phrase(sc.get('headline',''),speech):sc['headline']=''
                added_list=True
        headline=sc.get('headline','')
        # An AI summary may be accurate, but must not become a claimed verbatim emphasis.
        accent=not no_text and grounded_phrase(headline,speech)
        motion={'headline_seconds':min(2.6,sc['duration']),
                'accent_words':2 if accent and 'keyword_accent' in enabled else 0,
                'animate':not no_effects,'stagger':False}
        if sc['scene_type']=='talking_head':
            if 'camera_breath' in enabled and not no_effects and not no_zoom and speech.strip() and camera%2==0:
                duration=min(4.8,sc['duration'])
                if duration>=1.2:p.setdefault('effect_keyframes',[]).append({'id':f'motion_zoom_{index}','origin':'motion_skill','timeline_start':start,'duration':duration,'scale':1.065})
            camera+=1
        else:
            items=sc.get('graphic_items',[])
            motion['stagger']=('progressive_list' in enabled and sc.get('graphic_kind') in ('process','network') and not sc.get('visual_asset_id') and not sc.get('library_visual_id') and 2<=len(items)<=5 and sc['duration']>=1.2+.55*len(items) and (sc['scene_type']!='talking_head_pip' or len(items)<=3) and all(len(item)<=60 and grounded_phrase(item,speech) for item in items))
            if 'soft_entries' in enabled and not no_effects:sc['animation_in']='slide_up'
            if 'quiet_accents' in enabled:sc['sound_volume']=min(sc.get('sound_volume',.1),.07)
        if no_effects:
            sc['animation_in']='none'
            sc['animation_out']='none'
        if no_sound or no_sfx or no_effects:sc['sound_effect']='none'
        if no_text:
            sc['headline']='';sc['badge_text']='';motion['stagger']=False
            if not sc.get('visual_asset_id') and not sc.get('library_visual_id'):sc['scene_type']='talking_head';sc['graphic_items']=[];sc['graphic_title']=''
        if 'grounded_numbers' in enabled and not no_text:
            match=NUMBER.search(headline)
            if match and grounded_phrase(match.group(),speech):statistics.append(index)
        if index==len(p['storyboard'])-1 and 'grounded_cta' in enabled and not no_text:
            match=CTA.search(speech)
            if match:
                # Excerpt from the closing speech; no invented link or countdown.
                excerpt=' '.join(speech[match.start():].split()[:8]).strip(' ,.;:!?')
                motion['closing_text']=excerpt;cta.append(index)
        motion['transition_seconds']=.2 if 'soft_entries' in enabled and not no_effects else 0
        motion['show_photo_label']=not no_text
        sc['motion']=motion
    if p.get('director') is not None:p['director']['illustration_count']=sum(s['scene_type']!='talking_head' for s in p.get('storyboard',[]))
    p['motion_style']={'version':1,'preset':requested,'requested':requested,'active_skills':sorted(enabled),
                       'source':'reference_rules','model_weights_trained':False,
                       'number_scene_indices':statistics,'cta_scene_indices':cta,'effects_disabled':no_effects}
    return p
