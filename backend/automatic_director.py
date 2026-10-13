"""One-click editor: AI selects semantic visuals; the engine owns timing.

The model never needs to calculate frame counts, cuts or output duration.
The style engine can display valid AI-authored concepts when the model leaves
them on camera scenes. A failed model can use an explicitly labelled source-based fallback.
"""
import copy
import json
import math
import logging
import re
from difflib import SequenceMatcher
from pydantic import Field
from ai_director import Decision, chat, model_name, cancelled
from editing import length, mapped_subtitles, validate
from storyboard_style import caption_chunks
from typography import FontStyle, ai_guidance


class SceneChoice(Decision):
    scene_index: int = Field(ge=0)
    scene_type: str = Field(pattern='^(talking_head|explainer_card|talking_head_pip)$')
    headline: str = Field(max_length=80)
    badge_text: str = Field(max_length=60)
    graphic_kind: str = Field(pattern='^(chat|process|network)$')
    graphic_title: str = Field(max_length=60)
    graphic_items: list[str] = Field(max_length=5)
    sound_effect: str = Field(pattern='^(none|pop|whoosh|chime|click|impact)$')
    caption_text: str = Field(default='',max_length=1200)
    animation_in: str = Field(default='pop_in',pattern='^(pop_in|slide_up|fade)$')
    zoom_scale: float = Field(default=1,ge=1,le=1.2)


class AutoDirection(Decision):
    summary: str = Field(min_length=1,max_length=1000)
    scenes: list[SceneChoice] = Field(min_length=1,max_length=60)
    captions: bool = True
    font_style: FontStyle = 'auto'


class CompactScene(Decision):
    i: int = Field(ge=0)
    t: str = Field(pattern='^(talking_head|explainer_card|talking_head_pip)$')
    h: str = Field(max_length=80)
    k: str = Field(default='chat',pattern='^(chat|process|network)$')
    g: str = Field(default='',max_length=60)
    items: list[str] = Field(default_factory=list,max_length=5)
    s: str = Field(default='none',pattern='^(none|pop|whoosh|chime|click|impact)$')
    z: float = Field(default=1,ge=1,le=1.2)


class CameraWire(Decision):
    i: int = Field(ge=0)
    t: str = Field(pattern='^talking_head$')
    h: str = Field(max_length=80)
    z: float = Field(default=1,ge=1,le=1.2)


class GraphicWire(Decision):
    i: int = Field(ge=0)
    t: str = Field(pattern='^(explainer_card|talking_head_pip)$')
    h: str = Field(max_length=80)
    k: str = Field(pattern='^(chat|process|network)$')
    g: str = Field(min_length=1,max_length=60)
    items: list[str] = Field(min_length=2,max_length=5)
    s: str = Field(default='none',pattern='^(none|pop|whoosh|chime|click|impact)$')
    z: float = Field(default=1,ge=1,le=1.2)


class CompactDirection(Decision):
    summary: str = Field(min_length=1,max_length=1000)
    scenes: list[CameraWire | GraphicWire] = Field(min_length=1,max_length=60)
    captions: bool = True
    font_style: FontStyle = 'auto'


def expand_choice(scene):
    if 'scene_index' in scene:
        return scene  # Existing verbose repair/test responses remain readable.
    compact=CompactScene.model_validate(scene)
    return {'scene_index':compact.i,'scene_type':compact.t,'headline':compact.h,
            'badge_text':'','graphic_kind':compact.k,'graphic_title':compact.g,
            'graphic_items':compact.items,'sound_effect':compact.s,'zoom_scale':compact.z}


def graphic_labels(units):
    """Constrain visible graphic text to source phrases and neutral greetings."""
    labels=['Chào bạn','Bạn cần hỗ trợ gì?','Giới thiệu']
    fillers=set('và là thì mà cái này đó một những các đã đang sẽ rất cũng để với của cho từ như hơn tên nói dùng mình tôi anh chị em nó được có vừa rồi nhiều'.split())
    for unit in units:
        words=unit['text'].split()
        for size,stride in ((2,1),(3,3)):
            for offset in range(0,len(words)-size+1,stride):
                phrase=' '.join(words[offset:offset+size]).strip(' ,.;:!?')
                meaningful=not re.search(r'[,.;:!?]',phrase) and not (set(phrase.casefold().split()) & fillers)
                if phrase and meaningful and len(phrase)<=60 and phrase not in labels:
                    labels.append(phrase)
                if len(labels)>=160:
                    return labels
    return labels


def aligned_words(words,text,start,end):
    """Keep recognizer timing when correcting spelling, including split names."""
    new=text.split()
    if not new:
        return []
    if not words:
        # Segment timing is not word alignment. Leave it as a segment rather
        # than claiming invented timestamps came from speech recognition.
        return []
    old=[w['word'].strip() for w in words]
    out=[]
    for tag,a0,a1,b0,b1 in SequenceMatcher(None,[s.casefold() for s in old],[s.casefold() for s in new],autojunk=False).get_opcodes():
        if tag=='equal':
            out.extend({**words[a0+i],'word':' '+new[b0+i]} for i in range(b1-b0))
        elif tag!='delete':
            lo=words[a0]['start'] if a0<len(words) else words[-1]['end']
            hi=words[a1-1]['end'] if a1>a0 else words[a0]['start'] if a0<len(words) else end
            hi=max(lo,hi)
            out.extend({'word':' '+new[i],'start':lo+(hi-lo)*(i-b0)/(b1-b0),
                        'end':lo+(hi-lo)*(i-b0+1)/(b1-b0)} for i in range(b0,b1))
    return out


def correct_recognition_copy(text,brief):
    # A few invalid Vietnamese ASR homophones, not an editing/scene preset.
    for wrong,right in [('thân hiệu','thương hiệu'),('thử nghiệp','thử nghiệm'),
                        ('dân nghiệp','doanh nghiệp'),('trở lý','trợ lý'),('hiệü','hiệu')]:
        if not re.search(r'\b'+wrong+r'\b',brief,re.IGNORECASE):
            text=re.sub(r'\b'+wrong+r'\b',right,text,flags=re.IGNORECASE)
    # Prefer a user's explicit spelling of names, never inject a brand into
    # unrelated videos. Handle joined names such as ANNA -> AN NA.
    names=re.findall(r'\b[A-Z][A-Z]{3,}\b',brief)
    names+=re.findall(r'\b[A-Z]{2,3} [A-Z]{2,3}\b',brief)
    for name in names:
        target=name.replace(' ','').casefold()
        def replace(match):
            word=match.group(0)
            if SequenceMatcher(None,word.casefold(),target).ratio()>=.84:
                return name
            return word
        text=re.sub(r'\b[A-Za-z]{4,}\b',replace,text)
    return text


def unsupported_graphic_words(choice, vocabulary):
    # Illustrations label source concepts; they must not introduce new claims.
    # Neutral chat/diagram vocabulary supports generic conceptual artwork.
    neutral=set(re.findall(r'[^\W_]+',
        'xin chào bạn tôi là cần hỗ trợ gì ý tưởng mới chính nội dung kết nối '
        'lan tỏa truyền tải người nghe người xem cộng đồng mạng lưới và tới giới thiệu'.casefold()))
    missing=set()
    for item in [choice.graphic_title,*choice.graphic_items]:
        item=re.sub(r'^bước\s+\d+\s*[:.]?\s*','',item,flags=re.IGNORECASE)
        missing.update(set(re.findall(r'[^\W_]+',item.casefold()))-vocabulary-neutral)
    return sorted(missing)


def compose_requested_graphics(choices,units,prompt,total,vocabulary,has_speech):
    """Apply the approved layout to AI-authored concepts, never invent content.

    Rank by overlap with each scene's actual speech, not a seconds schedule.
    Opening/closing camera scenes stay visible when interior scenes exist.
    """
    requested=bool(re.search(r'minh họa|đồ họa|thẻ trắng|sinh động',prompt,re.IGNORECASE))
    excluded=bool(re.search(r'không (?:thêm |chèn |dùng |cần )?(?:minh họa|đồ họa|hình|hiệu ứng)',prompt,re.IGNORECASE))
    if not has_speech or total<=8 or not requested or excluded:
        return []
    adjusted=[]
    interior=set(range(1,len(units)-1)) if len(units)>2 else set(range(len(units)))
    def eligible(i):
        c=choices[i]
        return (i in interior and c.scene_type=='talking_head' and c.graphic_title.strip()
                and len(c.graphic_items)>=2 and not unsupported_graphic_words(c,vocabulary))
    def relevance(i):
        speech=set(re.findall(r'[^\W_]+',units[i]['text'].casefold()))
        labels=set(re.findall(r'[^\W_]+',' '.join(choices[i].graphic_items).casefold()))
        return len(speech&labels)
    def display(kinds):
        candidates=[i for i,c in choices.items() if eligible(i) and c.graphic_kind in kinds]
        if not candidates:
            return
        index=max(candidates,key=lambda i:(relevance(i),-i))
        choice=choices[index]
        choice.scene_type='talking_head_pip' if choice.graphic_kind=='chat' else 'explainer_card'
        no_sound=bool(re.search(r'(?:không|tắt|bỏ|no)\s+(?:thêm |chèn |dùng )?(?:âm thanh|tiếng|sfx|sound)',prompt,re.IGNORECASE))
        if choice.sound_effect=='none' and not no_sound:
            choice.sound_effect='pop' if choice.graphic_kind=='chat' else 'whoosh'
        adjusted.append(index)
    graphics=[c for c in choices.values() if c.scene_type!='talking_head']
    # Reusable style composition: conversational concept + explanatory concept
    # when the AI supplied both. Short videos need only one illustration.
    if not graphics:
        display({'chat'})
    if total>20 and not any(c.scene_type!='talking_head' and c.graphic_kind in {'process','network'} for c in choices.values()):
        display({'process','network'})
    if not any(c.scene_type!='talking_head' for c in choices.values()):
        display({'chat','process','network'})
    if 'hội thoại' in prompt.casefold() and not any(c.scene_type!='talking_head' and c.graphic_kind=='chat' for c in choices.values()):
        display({'chat'})
    return adjusted


def balance_graphics(choices,units,prompt,total):
    """Bound illustration density by meaning while preserving source camera."""
    if len(units)<=2:
        return []
    excluded=bool(re.search(r'không (?:thêm |chèn |dùng |cần )?(?:minh họa|đồ họa|hình|hiệu ứng)',prompt,re.IGNORECASE))
    eligible=[i for i,c in choices.items() if 0<i<len(units)-1 and c.scene_type!='talking_head']
    def score(i):
        speech=set(re.findall(r'[^\W_]+',units[i]['text'].casefold()))
        labels=set(re.findall(r'[^\W_]+',' '.join(choices[i].graphic_items).casefold()))
        return len(speech & labels)
    selected=[]
    if not excluded:
        chat=[i for i in eligible if choices[i].graphic_kind=='chat']
        diagram=[i for i in eligible if choices[i].graphic_kind in {'process','network'}]
        if chat:selected.append(max(chat,key=score))
        if diagram and (total>20 or not selected):selected.append(max(diagram,key=score))
    changed=[]
    no_sound=bool(re.search(r'(?:không|tắt|bỏ|no)\s+(?:thêm |chèn |dùng )?(?:âm thanh|tiếng|sfx|sound)',prompt,re.IGNORECASE))
    no_zoom=bool(re.search(r'(?:không|tắt|bỏ)\s+(?:thêm |chèn |dùng )?(?:zoom|hiệu ứng)',prompt,re.IGNORECASE))
    for i,choice in choices.items():
        typ=('talking_head_pip' if choice.graphic_kind=='chat' else 'explainer_card') if i in selected else 'talking_head'
        if choice.scene_type!=typ:changed.append(i)
        choice.scene_type=typ
        if typ=='talking_head':
            choice.sound_effect='none'
            if units[i]['text'].strip() and not no_zoom:
                choice.zoom_scale=max(choice.zoom_scale,1.035)
        elif choice.sound_effect=='none' and not no_sound:
            choice.sound_effect='pop' if choice.graphic_kind=='chat' else 'whoosh'
    return changed


def semantic_units(plan):
    total=length(plan)
    subs=mapped_subtitles(plan)
    tokens=[]
    for sub in subs:
        if sub.get('words'):
            tokens.extend({'start':w['start'],'end':w['end'],'text':w['word'].strip()} for w in sub['words'] if w['end']>w['start'])
        else:
            tokens.extend(caption_chunks([sub],max_words=7))
    tokens.sort(key=lambda t:t['start'])
    units=[];start=0.0;group=[]
    for token in tokens:
        group.append(token['text'])
        end=min(total,token['end'])
        sentence=token['text'].rstrip().endswith(('.','!','?'))
        if end-start>=7 or (sentence and end-start>=2.8):
            units.append({'start':start,'end':end,'text':' '.join(group)})
            start=end;group=[]
    if total-start>0:
        if units and total-start<1.5:
            units[-1]['end']=total
            units[-1]['text']+=' '+' '.join(group)
        else:
            units.append({'start':start,'end':total,'text':' '.join(group)})
    if not units:
        units=[{'start':0,'end':total,'text':''}]
    # Merge neighboring units for long sources instead of dropping speech.
    while len(units)>60:
        index=min(range(len(units)-1),key=lambda i:units[i+1]['end']-units[i]['start'])
        units[index:index+2]=[{'start':units[index]['start'],'end':units[index+1]['end'],
                             'text':units[index]['text']+' '+units[index+1]['text']}]
    return [{'scene_index':i,**unit} for i,unit in enumerate(units)]


SYSTEM="""Edit Vietnamese speech into a premium explainer video. JSON only.
Engine preserves original voice, captions and timing. Return each supplied scene index exactly once, or ONLY requested repair indices.
Each scene: i=index, t=type, h=short accurate Vietnamese headline (2-6 words). Types: talking_head, talking_head_pip, explainer_card.
Optional k=chat/process/network, g=graphic title, items=2-3 short visible labels, s=none/pop/whoosh/chime/click/impact, z=zoom 1-1.2.
Camera: only i,t,h, optionally z. Graphics: include k,g,items; use chat for assistant/conversation, process for source ideas, network for connections.
Use EACH scene's own speech. Keep opening, closing and more than half the video on camera when possible. If brief requests illustrations, supply useful graphics at relevant scenes. Avoid consecutive repetitive diagrams.
Visible words/facts must come from source or explicit brief. Neutral greetings are allowed. Never invent first/best claims, features, prices, contacts, statistics, algorithm steps or real screenshots. Do not turn uncertain recognition into a claim. Spell explicit names correctly.
Most camera scenes s=none; graphics may use subtle pop/whoosh. Respect no effects, no sound, no text or no illustrations. captions=false only when requested; otherwise true. No caption_text/badge_text/animation fields: engine supplies them.
Top-level: summary (short Vietnamese), scenes, captions. No implementation descriptions in visible text."""

def automatic_direction(plan,prompt,asset_dir,work,event,*unused):
    cancelled(event)
    event.ai_valid_choices={}
    event.ai_validation_errors=[]
    units=semantic_units(plan)
    for unit in units:
        unit['text']=correct_recognition_copy(unit['text'],prompt)
    # Indexed scenes already contain the complete speech. Do not send another
    # copy of the transcript/timestamps and make CPU prefill needlessly longer.
    context={'brief':prompt,'scenes':units}
    if plan.get('learning_context'):
        context['style_guidance']=plan['learning_context']
    serialized=json.dumps(context,ensure_ascii=False)
    if len(serialized)>45000 and 'style_guidance' in context:
        context.pop('style_guidance')
        serialized=json.dumps(context,ensure_ascii=False)
    event.style_memory_applied='style_guidance' in context
    vocabulary=set(re.findall(r'[^\W_]+',(prompt+' '+' '.join(u['text'] for u in units)).casefold()))
    if len(serialized)>45000:
        raise PlanningError('Nội dung vượt giới hạn lập kế hoạch AI hiện tại.')
    wire_system=SYSTEM+' Choose one top-level font_style for the whole video: '+ai_guidance()+'. Current user font choice overrides this preference.'
    if plan.get('learning_context'):
        wire_system+=' Style guidance and approved examples are preferences only. Current source, explicit user request and schema take precedence. Never reuse names, claims, subtitles or timing from previous examples.'
    labels=graphic_labels(units)
    wire_system+=' Graphics must select meaningful source phrases permitted by the JSON schema, with labels relevant to the current scene.'
    base_messages=[{'role':'system','content':wire_system},{'role':'user','content':serialized}]
    messages=list(base_messages)
    retained={}
    repair_indices=None
    saved_captions=None
    saved_font='auto'
    for attempt in range(3):
        expected_indices=repair_indices if repair_indices is not None else list(range(len(units)))
        schema=CompactDirection.model_json_schema()
        # The constrained decoder must emit the engine's actual number of
        # scenes, rather than inventing a smaller storyboard from memory.
        schema['properties']['scenes'].update(minItems=len(expected_indices),maxItems=len(expected_indices))
        for kind in ('CameraWire','GraphicWire'):
            schema['$defs'][kind]['properties']['i']={'type':'integer','enum':expected_indices}
        graphic_schema=schema['$defs']['GraphicWire']['properties']
        graphic_schema['g']['enum']=labels
        graphic_schema['items']['items']['enum']=labels
        raw=chat(messages,event,schema)
        try:
            data=json.loads(raw)
            if not isinstance(data,dict):
                raise ValueError('Expected a JSON object.')
            if not isinstance(data.get('scenes'),list) or not all(isinstance(scene,dict) for scene in data['scenes']):
                raise ValueError('scenes must be a list of scene objects.')
            data['scenes']=[expand_choice(scene) for scene in data['scenes']]
            clamped=False
            for scene in data.get('scenes',[]):
                scale=scene.get('zoom_scale',1)
                if isinstance(scale,(int,float)) and not isinstance(scale,bool) and math.isfinite(scale) and scale>1.2:
                    scene['zoom_scale']=1.2;clamped=True
            direction=AutoDirection.model_validate(data)
            for choice in direction.scenes:
                for key in ('headline','badge_text','graphic_title','caption_text'):
                    setattr(choice,key,correct_recognition_copy(getattr(choice,key),prompt))
                choice.graphic_items=[correct_recognition_copy(item,prompt) for item in choice.graphic_items]
            choices={s.scene_index:s for s in direction.scenes}
            expected=set(repair_indices) if repair_indices is not None else set(range(len(units)))
            if repair_indices is not None and expected.issubset(choices) and set(choices)-expected<=set(retained):
                # Some small models return the full plan despite a partial
                # repair request. Ignore rewrites to already-valid scenes.
                if len(choices)!=len(direction.scenes):
                    raise ValueError('No duplicate scene_index values in a repair.')
                choices={i:choices[i] for i in expected}
                direction.scenes=list(choices.values())
            if len(choices)!=len(direction.scenes) or set(choices)!=expected:
                raise ValueError(f'Provide each scene_index in {sorted(expected)} exactly once; no duplicates or omissions.')
            if repair_indices is None:
                saved_captions=direction.captions
                saved_font=direction.font_style
            else:
                direction.captions=saved_captions
            choices={**retained,**choices}
            layout_adjustments=compose_requested_graphics(choices,units,prompt,length(plan),vocabulary,bool(plan.get('subtitles')))
            invalid_graphics=[u['scene_index'] for u in units
                if choices[u['scene_index']].scene_type!='talking_head'
                and (not choices[u['scene_index']].graphic_title.strip() or len(choices[u['scene_index']].graphic_items)<2
                     or unsupported_graphic_words(choices[u['scene_index']],vocabulary))]
            if invalid_graphics:
                retained={i:s for i,s in choices.items() if i not in invalid_graphics}
                event.ai_valid_choices=copy.deepcopy(retained)
                repair_indices=invalid_graphics
                raise ValueError('Repair ONLY scene_index '+str(invalid_graphics)+'. Return only those scenes; the other valid scenes are retained by the engine. Each graphic needs a meaningful graphic_title and at least 2 short graphic_items. Labels must use vocabulary from the transcript/brief or neutral greetings/connections. Do not introduce first/only/optimization/algorithm claims absent from the source. Never return empty items. Unsupported words: '+str({i:unsupported_graphic_words(choices[i],vocabulary) for i in invalid_graphics}))
            event.ai_valid_choices=copy.deepcopy(choices)
            repair_indices=None
            retained={}
            caption_fallbacks=[]
            for unit in units:
                choice=choices[unit['scene_index']]
                if unit['text'].strip() and direction.captions:
                    similarity=SequenceMatcher(None,unit['text'].casefold(),choice.caption_text.casefold()).ratio()
                    if not choice.caption_text.strip():
                        choice.caption_text=unit['text']
                    elif similarity<.78:
                        # A model moving/summarizing speech must not prevent
                        # rendering or silently remove the source captions.
                        choice.caption_text=unit['text']
                        caption_fallbacks.append(unit['scene_index']+1)
                elif not unit['text'].strip() and choice.caption_text.strip():
                    raise ValueError('Do not invent subtitles for silent scenes.')
            layout_adjustments=sorted(set(layout_adjustments+balance_graphics(choices,units,prompt,length(plan))))
            graphics=[s for s in choices.values() if s.scene_type!='talking_head']
            want_graphics=bool(re.search(r'minh họa|đồ họa|thẻ trắng|sinh động',prompt,re.IGNORECASE))
            no_graphics=bool(re.search(r'không (?:thêm |chèn |dùng |cần )?(?:minh họa|đồ họa|hình|hiệu ứng)',prompt,re.IGNORECASE))
            if length(plan)>8 and plan.get('subtitles') and want_graphics and not no_graphics and not graphics:
                raise ValueError('The brief asks for illustrations. You returned only talking_head scenes. Choose at least one meaningful explainer_card with actual illustration items; do not avoid graphics to bypass validation.')
            if length(plan)>15 and 'hội thoại' in prompt.casefold() and 'sơ đồ' in prompt.casefold() and not no_graphics:
                kinds={s.graphic_kind for s in graphics}
                if 'chat' not in kinds or not kinds.intersection({'process','network'}):
                    raise ValueError('The user requests both an assistant conversation illustration AND a diagram. Use at least one chat graphic and one process/network graphic at suitable semantic scenes.')
            p=apply_choices(plan,prompt,units,choices,direction.captions)
            warnings=[]
            if caption_fallbacks:
                warnings.append('Đã giữ phụ đề nhận dạng ở cảnh '+', '.join(map(str,caption_fallbacks))+' vì AI sửa quá nhiều lời nói. Xem lại chính tả trước khi đăng.')
            if clamped:
                warnings.append('Đã giảm zoom về mức an toàn 1.2 để giữ hình rõ.')
            if not plan.get('subtitles'):
                warnings.append('Video không có lời thoại nhận dạng; hình minh họa chỉ dựa trên yêu cầu bạn nhập.')
            p['director']={'engine':'ollama','model':model_name(),'summary':direction.summary,'prompt':prompt,
                           'warnings':warnings,'mode':'automatic_semantic_scenes','font_style':saved_font,
                           'layout_adjustments':layout_adjustments}
            return validate(p,plan['assets'])
        except (ValueError,TypeError,KeyError) as exc:
            errors=getattr(event,'ai_validation_errors',[])
            errors.append({'attempt':attempt+1,'error':str(exc)[:1500]})
            event.ai_validation_errors=errors
            logging.getLogger('uvicorn.error').info('video_ai_validation attempt=%s error=%s',attempt+1,str(exc)[:1500])
            if attempt==2:
                raise PlanningError('AI chưa chọn được cảnh hợp lệ sau khi tự sửa: '+str(exc)) from exc
            # Retain source context and only the latest failed response/error;
            # previous repairs are not useful additional speech context.
            messages = base_messages+[{'role':'assistant','content':raw[:15000]},
                                      {'role':'user','content':'Repair the JSON. '+str(exc)[:1500]}]


def apply_choices(plan,prompt,units,choices,captions):
    """Shared adapter: AI and fallback both use the existing validated plan."""
    p=copy.deepcopy(plan)
    p['recognition_subtitles']=copy.deepcopy(plan.get('recognition_subtitles',plan.get('subtitles',[])))
    p['storyboard']=[{**choices[u['scene_index']].model_dump(),'scene_id':f"auto_{u['scene_index']}",
        'headline':choices[u['scene_index']].headline.upper(),
        'timeline_start':u['start'],'duration':u['end']-u['start'],
        'transcript_meaning':u['text'],'badge_color':'teal' if choices[u['scene_index']].scene_type!='talking_head' else 'navy',
        'sound_volume':.10,'animation_out':'none'} for u in units]
    if captions and plan.get('subtitles'):
        source_words=[w for sub in mapped_subtitles(plan) for w in sub.get('words',[])]
        aid=plan['video_clips'][0]['asset_id']
        p['subtitles']=[{'id':f"caption_{u['scene_index']}",'asset_id':aid,
            'start':u['start'],'end':u['end'],'text':choices[u['scene_index']].caption_text,
            'words':aligned_words([w for w in source_words if w['end']>u['start'] and w['start']<u['end']],
                choices[u['scene_index']].caption_text,u['start'],u['end'])} for u in units if choices[u['scene_index']].caption_text.strip()]
    if captions and 'user_subtitles' in plan:
        # Explicit corrections are authoritative, including their existing timing.
        p['subtitles']=copy.deepcopy(plan['user_subtitles'])
    # Replace generated decorations, retain manual project assets.
    for key in ('text_overlays','visual_overlays','effect_keyframes','audio_tracks'):
        p[key]=[e for e in p.get(key,[]) if e.get('origin')!='auto']
    for unit in units:
        choice=choices[unit['scene_index']]
        if choice.scene_type=='talking_head' and choice.zoom_scale>1:
            p['effect_keyframes'].append({'id':f"zoom_{unit['scene_index']}",'origin':'auto',
                'timeline_start':unit['start'],'duration':unit['end']-unit['start'],'scale':choice.zoom_scale})
    p['show_captions']=captions
    return p


class PlanningError(RuntimeError):
    code = 'AI_PLAN_INVALID'


def fallback_direction(plan,prompt,event,reason):
    """Source-only camera composition. Never claim invented graphics are AI."""
    cancelled(event)
    units=semantic_units(plan)
    for unit in units:
        unit['text']=correct_recognition_copy(unit['text'],prompt)
    captions=not bool(re.search(r'(?:không|tắt|bỏ|no)\s+(?:thêm |chèn |dùng )?(?:phụ đề|caption|subtitles?)',prompt,re.IGNORECASE))
    no_text=bool(re.search(r'(?:không|tắt|bỏ)\s+(?:thêm |chèn |dùng )?(?:chữ|text)',prompt,re.IGNORECASE))
    no_effects=bool(re.search(r'(?:không|tắt|bỏ)\s+(?:thêm |chèn |dùng )?(?:zoom|hiệu ứng)',prompt,re.IGNORECASE))
    if no_text:
        captions=False
    retained=getattr(event,'ai_valid_choices',{})
    choices={}
    preserved=[]
    for unit in units:
        cancelled(event)
        i=unit['scene_index']
        choice=copy.deepcopy(retained.get(i))
        if choice is not None:
            preserved.append(i)
        else:
            # Exact excerpt, never paraphrase uncertain recognition as a claim.
            headline=' '.join(unit['text'].split()[:6]).strip(' ,.;:!?')[:80] if not no_text else ''
            choice=SceneChoice(scene_index=i,scene_type='talking_head',headline=headline,
                badge_text='',graphic_kind='chat',graphic_title='',graphic_items=[],
                sound_effect='none',zoom_scale=1.035 if unit['text'].strip() and not no_effects else 1)
        # Fallback captions always use source, including partially retained AI.
        choice.caption_text=unit['text'] if captions else ''
        if no_text:
            choice.scene_type='talking_head';choice.headline='';choice.badge_text=''
        if no_effects:
            choice.zoom_scale=1;choice.sound_effect='none'
        choices[i]=choice
    balance_graphics(choices,units,prompt,length(plan))
    p=apply_choices(plan,prompt,units,choices,captions)
    p['director']={'engine':'rules','model':None,'mode':'automatic_fallback',
        'summary':'Bản dựng dự phòng từ lời nói gốc; AI chưa hoàn thành kế hoạch.',
        'prompt':prompt,'fallback_reason':reason,'retained_ai_scene_indices':preserved,
        'warnings':['Đã dùng chế độ dựng dự phòng vì AI chưa hoàn thành. Giữ lời nói và phụ đề nguồn; kiểm tra chính tả trước khi đăng. Minh họa AI mới chưa được tạo.']}
    cancelled(event)
    return validate(p,plan['assets'])
