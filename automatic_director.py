"""One-click editor: AI selects semantic visuals; the engine owns timing.

The model never needs to calculate frame counts, cuts or output duration.
The style engine can display valid AI-authored concepts when the model leaves
them on camera scenes. A missing/invalid model response is never replaced.
"""
import copy
import json
import math
import re
from difflib import SequenceMatcher
from pydantic import Field
from ai_director import Decision, chat, model_name
from editing import length, mapped_subtitles, validate
from storyboard_style import caption_chunks


class SceneChoice(Decision):
    scene_index: int = Field(ge=0)
    scene_type: str = Field(pattern='^(talking_head|explainer_card|talking_head_pip)$')
    headline: str = Field(max_length=80)
    badge_text: str = Field(max_length=60)
    graphic_kind: str = Field(pattern='^(chat|process|network)$')
    graphic_title: str = Field(max_length=60)
    graphic_items: list[str] = Field(max_length=5)
    sound_effect: str = Field(pattern='^(none|pop|whoosh|chime|click|impact)$')
    caption_text: str = Field(max_length=1200)
    animation_in: str = Field(default='pop_in',pattern='^(pop_in|slide_up|fade)$')
    zoom_scale: float = Field(default=1,ge=1,le=1.2)


class AutoDirection(Decision):
    summary: str = Field(min_length=1,max_length=1000)
    scenes: list[SceneChoice] = Field(min_length=1,max_length=60)
    captions: bool = True


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
        'lan tỏa truyền tải người nghe người xem cộng đồng mạng lưới và tới'.casefold()))
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


SYSTEM='''You edit Vietnamese videos using an existing premium explainer renderer. Return JSON only.
The engine owns ALL timing and preserves the original voice. Select content/layout for the supplied scenes; never calculate cuts or invent new scenes.
Return every supplied scene_index exactly once. For a repair requesting ONLY certain indices, return those indices only; the engine retains the other scenes.
Read the full transcript for context, then EACH indexed scene's own text. Never shift the next scene's speech into the current scene.
Use talking_head for introductions/personal remarks/conclusions; talking_head_pip for a speaker with illustration; explainer_card for a useful white graphic cutaway. Keep the speaker visible for more than half the video when possible. Choose by meaning, not a fixed schedule. Avoid repetitive consecutive network diagrams.
headline: a short accurate 2-6-word Vietnamese idea, not fillers or a whole sentence. badge_text: a short topic label. Do not add brands or facts absent from speech/user facts. Spell user-supplied names correctly.
graphic_kind: chat for assistant/conversation; process for related ideas/steps; network for distribution/connections.
graphic_title and graphic_items are visible display text. Use 2-3 SHORT bare labels/messages; NEVER prefix them with Chat:, Process:, or Network:. Camera scenes also supply 2 short labels, though they are not displayed.
Graphics must use concepts/words from the transcript or explicit user facts. Neutral chat greetings are fine (Chào bạn / Bạn cần hỗ trợ gì?). Do not fabricate first/only/best claims, features, benefits, optimization/algorithm stages, statistics, prices, contacts, testimonials or real screenshots. A process can label related source ideas; it need not invent steps.
caption_text: speech from THIS indexed scene only. Correct obvious spelling using full context/user names; do not summarize, add or move sentences. If uncertain, copy this scene's text rather than invent wording. Silent scene = empty string. Never promote uncertain ASR words into headings or illustrations.
sound_effect: none on most camera scenes; subtle pop/whoosh/chime/click on useful graphics. Respect requests for no sound, no text or minimal effects. captions=true unless explicitly disabled.
zoom_scale: 1 unless camera emphasis benefits the content; at most 1.2. animation_in: pop_in, slide_up or fade.
The renderer supplies white/teal/navy styling, rounded cards, Vietnamese fonts and automatic captions. Do not put implementation descriptions in visible text. summary must be Vietnamese.'''


def automatic_direction(plan,prompt,asset_dir,work,event,*unused):
    units=semantic_units(plan)
    for unit in units:
        unit['text']=correct_recognition_copy(unit['text'],prompt)
    context={'brief':prompt,'transcript':[{'start':s['start'],'end':s['end'],'text':correct_recognition_copy(s['text'],prompt)} for s in mapped_subtitles(plan)],'scenes':units}
    serialized=json.dumps(context,ensure_ascii=False)
    vocabulary=set(re.findall(r'[^\W_]+',(prompt+' '+' '.join(u['text'] for u in units)).casefold()))
    if len(serialized)>45000:
        raise ValueError('Video quá dài cho model hiện tại. Hãy dùng video ngắn hơn.')
    messages=[{'role':'system','content':SYSTEM},{'role':'user','content':serialized}]
    retained={}
    repair_indices=None
    saved_captions=None
    for attempt in range(3):
        expected_indices=repair_indices if repair_indices is not None else list(range(len(units)))
        schema=AutoDirection.model_json_schema()
        # The constrained decoder must emit the engine's actual number of
        # scenes, rather than inventing a smaller storyboard from memory.
        schema['properties']['scenes'].update(minItems=len(expected_indices),maxItems=len(expected_indices))
        scene_schema=schema['$defs']['SceneChoice']['properties']
        scene_schema['scene_index']={'type':'integer','enum':expected_indices}
        scene_schema['graphic_items']['minItems']=2
        raw=chat(messages,event,schema)
        try:
            data=json.loads(raw)
            if not isinstance(data,dict):
                raise ValueError('Expected a JSON object.')
            if not isinstance(data.get('scenes'),list) or not all(isinstance(scene,dict) for scene in data['scenes']):
                raise ValueError('scenes must be a list of scene objects.')
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
                repair_indices=invalid_graphics
                raise ValueError('Repair ONLY scene_index '+str(invalid_graphics)+'. Return only those scenes; the other valid scenes are retained by the engine. Each graphic needs a meaningful graphic_title and at least 2 short graphic_items. Labels must use vocabulary from the transcript/brief or neutral greetings/connections. Do not introduce first/only/optimization/algorithm claims absent from the source. Never return empty items. Unsupported words: '+str({i:unsupported_graphic_words(choices[i],vocabulary) for i in invalid_graphics}))
            repair_indices=None
            retained={}
            caption_fallbacks=[]
            for unit in units:
                choice=choices[unit['scene_index']]
                if unit['text'].strip() and direction.captions:
                    similarity=SequenceMatcher(None,unit['text'].casefold(),choice.caption_text.casefold()).ratio()
                    if similarity<.78:
                        # A model moving/summarizing speech must not prevent
                        # rendering or silently remove the source captions.
                        choice.caption_text=unit['text']
                        caption_fallbacks.append(unit['scene_index']+1)
                elif not unit['text'].strip() and choice.caption_text.strip():
                    raise ValueError('Do not invent subtitles for silent scenes.')
            graphics=[s for s in choices.values() if s.scene_type!='talking_head']
            want_graphics=bool(re.search(r'minh họa|đồ họa|thẻ trắng|sinh động',prompt,re.IGNORECASE))
            no_graphics=bool(re.search(r'không (?:thêm |chèn |dùng |cần )?(?:minh họa|đồ họa|hình|hiệu ứng)',prompt,re.IGNORECASE))
            if length(plan)>8 and plan.get('subtitles') and want_graphics and not no_graphics and not graphics:
                raise ValueError('The brief asks for illustrations. You returned only talking_head scenes. Choose at least one meaningful explainer_card with actual illustration items; do not avoid graphics to bypass validation.')
            if length(plan)>15 and 'hội thoại' in prompt.casefold() and 'sơ đồ' in prompt.casefold() and not no_graphics:
                kinds={s.graphic_kind for s in graphics}
                if 'chat' not in kinds or not kinds.intersection({'process','network'}):
                    raise ValueError('The user requests both an assistant conversation illustration AND a diagram. Use at least one chat graphic and one process/network graphic at suitable semantic scenes.')
            p=copy.deepcopy(plan)
            p['recognition_subtitles']=copy.deepcopy(plan.get('subtitles',[]))
            p['storyboard']=[{**choices[u['scene_index']].model_dump(),'scene_id':f"auto_{u['scene_index']}",
                'headline':choices[u['scene_index']].headline.upper(),
                'timeline_start':u['start'],'duration':u['end']-u['start'],
                'transcript_meaning':u['text'],'badge_color':'teal' if choices[u['scene_index']].scene_type!='talking_head' else 'navy',
                'sound_volume':.10,'animation_out':'none'} for u in units]
            if direction.captions and plan.get('subtitles'):
                source_words=[w for sub in mapped_subtitles(plan) for w in sub.get('words',[])]
                aid=plan['video_clips'][0]['asset_id']
                p['subtitles']=[{'id':f"caption_{u['scene_index']}",'asset_id':aid,
                    'start':u['start'],'end':u['end'],'text':choices[u['scene_index']].caption_text,
                    'words':aligned_words([w for w in source_words if w['end']>u['start'] and w['start']<u['end']],
                        choices[u['scene_index']].caption_text,u['start'],u['end'])} for u in units if choices[u['scene_index']].caption_text.strip()]
            # Replace generated decorations, retain manual project assets.
            for key in ('text_overlays','visual_overlays','effect_keyframes','audio_tracks'):
                p[key]=[e for e in p.get(key,[]) if e.get('origin')!='auto']
            for unit in units:
                choice=choices[unit['scene_index']]
                if choice.scene_type=='talking_head' and choice.zoom_scale>1:
                    p['effect_keyframes'].append({'id':f"zoom_{unit['scene_index']}",'origin':'auto',
                        'timeline_start':unit['start'],'duration':unit['end']-unit['start'],'scale':choice.zoom_scale})
            p['show_captions']=direction.captions
            warnings=[]
            if caption_fallbacks:
                warnings.append('Đã giữ phụ đề nhận dạng ở cảnh '+', '.join(map(str,caption_fallbacks))+' vì AI sửa quá nhiều lời nói. Xem lại chính tả trước khi đăng.')
            if clamped:
                warnings.append('Đã giảm zoom về mức an toàn 1.2 để giữ hình rõ.')
            if not plan.get('subtitles'):
                warnings.append('Video không có lời thoại nhận dạng; hình minh họa chỉ dựa trên yêu cầu bạn nhập.')
            p['director']={'engine':'ollama','model':model_name(),'summary':direction.summary,'prompt':prompt,
                           'warnings':warnings,'mode':'automatic_semantic_scenes',
                           'layout_adjustments':layout_adjustments}
            return validate(p,plan['assets'])
        except (ValueError,TypeError,KeyError) as exc:
            if attempt==2:
                raise RuntimeError('AI chưa chọn được cảnh hợp lệ sau khi tự sửa: '+str(exc)) from exc
            messages += [{'role':'assistant','content':raw},{'role':'user','content':'Repair the JSON. '+str(exc)[:1500]}]
