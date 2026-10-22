"""Shared typography and safe areas from the approved DANAVA review edit."""
import textwrap
from editing import ass_time, mapped_subtitles
from text_review import headline_layout
from typography import profile_for, font_path


def escape_ass(text):
    # Model / user text is always literal; never allow ASS control sequences.
    return str(text).replace('\\', '／').replace('{', '(').replace('}', ')').replace('\n', ' ')


def caption_chunks(subs, max_words=7, proper_names=""):
    names=[line.split("|")[0].strip().casefold().split() for line in proper_names.splitlines()]
    names=[name for name in names if 1<len(name)<=4]
    def protected(tokens,boundary):
        tokens=[token.strip(" ,.!?;:").casefold() for token in tokens]
        return any(tokens[start:start+len(name)]==name and start<boundary<start+len(name)
                   for name in names for start in range(max(0,boundary-len(name)+1),boundary))
    result = []
    for sub in subs:
        timed=sub.get('words',[])
        joined=' '.join(w['word'].strip() for w in timed)
        if timed and ' '.join(joined.split())==' '.join(sub['text'].split()):
            group=[]
            for index,word in enumerate(timed):
                group.append(word)
                if (len(group)>=max_words or (len(group)>=3 and word['word'].rstrip().endswith(('.',',','!','?',';')))) and not protected([w['word'].strip() for w in timed],index+1):
                    result.append({'start':group[0]['start'],'end':group[-1]['end'],'text':' '.join(w['word'].strip() for w in group)})
                    group=[]
            if group:
                result.append({'start':group[0]['start'],'end':group[-1]['end'],'text':' '.join(w['word'].strip() for w in group)})
            continue
        words = sub['text'].split()
        if not words:
            continue
        duration = sub['end'] - sub['start']
        index=0
        while index<len(words):
            end = min(len(words), index + max_words)
            while end<len(words) and protected(words,end):
                end+=1
            result.append({'start': sub['start'] + duration * index / len(words),
                           'end': sub['start'] + duration * end / len(words),
                           'text': ' '.join(words[index:end])})
            index=end
    return result


def expressive_captions(lines,plan,preset,profile,ass_color):
    """Colored phrase captions, highlighting words only with real alignment.

    All inserted ASS tags are engine-owned. Source copy is escaped separately;
    SRT/segment-only input gets phrase emphasis, never invented word timing.
    """
    from PIL import ImageFont
    subs=mapped_subtitles(plan)
    all_words=[w for s in subs for w in s.get('words',[])
        if ' '.join(w['word'].strip() for w in s.get('words',[]))==' '.join(s['text'].split())]
    animate=not plan.get('motion_style',{}).get('effects_disabled',False)
    accent=ass_color(preset['accent']);secondary=ass_color(preset['secondary'])
    base_size=64 if preset['id']=='inspirational' else 38
    weight=800 if preset['id']=='inspirational' else 700
    for chunk in caption_chunks(subs,preset['caption_words'],plan.get('proper_names','')):
        tokens=chunk['text'].split();size=base_size
        def layout(font):
            rows=[];line=[];breaks=set()
            for index,token in enumerate(tokens):
                if line and font.getlength(' '.join([*line,token]))>600:
                    rows.append(line);breaks.add(index);line=[]
                line.append(token)
            if line:rows.append(line)
            return rows,breaks
        if profile:
            while True:
                font=ImageFont.truetype(str(font_path(profile,'caption')),size)
                rows,breaks=layout(font)
                if size<=18 or len(rows)<=2 and all(font.getlength(' '.join(r))<=600 for r in rows):break
                size-=1
        else:breaks=set()
        aligned=[w for w in all_words if w['start']>=chunk['start']-.001 and w['end']<=chunk['end']+.001 and w['end']>w['start']]
        credible=(' '.join(w['word'].strip() for w in aligned).split()==tokens
            and all(a['end']<=b['start']+.001 for a,b in zip(aligned,aligned[1:])))
        spans=[(w['start'],aligned[i+1]['start'] if i+1<len(aligned) else chunk['end'],i) for i,w in enumerate(aligned)] if credible else [(chunk['start'],chunk['end'],None)]
        for start,end,active in spans:
            if end<=start:continue
            rendered=[]
            for index,token in enumerate(tokens):
                highlighted=index==active if active is not None else index>=max(0,len(tokens)-2)
                color=accent if highlighted else secondary if index==len(tokens)-1 and active is None else '&H00FFFFFF&'
                scale=125 if preset['id']=='inspirational' else 108
                grow=f'\\fscx{scale}\\fscy{scale}\\t(0,160,\\fscx100\\fscy100)' if highlighted and animate else ''
                rendered.append(('\\N' if index in breaks else ' ' if index else '')+
                    '{\\c'+color+'\\fscx100\\fscy100'+grow+'}'+escape_ass(token))
            entry='\\fad(90,70)' if animate and not credible else ''
            tags='\\b'+str(weight)+'\\fs'+str(size)+entry
            lines.append(f'Dialogue: 1,{ass_time(start)},{ass_time(end)},Caption,,0,0,0,,{{{tags}}}'+''.join(rendered))


def write_storyboard_ass(path, plan, width, height):
    from style_presets import preset_for
    preset=preset_for(plan.get('style_preset',{}).get('id','explainer'))
    expressive=bool(plan.get('style_preset',{}).get('caption_design'))
    themed=preset['id']!='explainer' or expressive
    def ass_color(color):
        return '&H00'+color[5:7]+color[3:5]+color[1:3]+'&'
    profile = profile_for(plan)
    dynamic = plan.get('motion_style',{}).get('preset')=='dynamic_explainer'
    # Render at a fixed design coordinate system; libass scales for preview.
    lines = ['[Script Info]', 'ScriptType: v4.00+', 'PlayResX: 720', 'PlayResY: 1280',
             'WrapStyle: 2', '[V4+ Styles]',
             'Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding',
             'Style: Caption,Inter,32,&H00FFFFFF,&H00FFFFFF,&H003B2D17,&H003B2D17,-1,0,0,0,100,100,0,0,3,12,0,2,45,45,118,1',
             'Style: Head,Barlow Condensed,64,&H00FFFFFF,&H00FFFFFF,&H003B2D17,&H803B2D17,-1,0,0,0,100,100,0,0,1,2,1,8,40,40,170,1',
             'Style: Label,Inter,22,&H00FFFFFF,&H00FFFFFF,&H0088940D,&H0088940D,-1,0,0,0,100,100,2,0,3,10,0,8,40,40,110,1',
             'Style: Brand,Inter,26,&H00FFFFFF,&H00FFFFFF,&H003B2D17,&H803B2D17,0,0,0,0,100,100,0,0,1,2,0,2,35,35,35,1',
             '[Events]', 'Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text']
    if profile:
        replacements = {'Caption': (profile['caption_size'], profile['caption_weight']),
                        'Head': (profile['heading_size'], profile['heading_weight']),
                        'Label': (22, profile['caption_weight']), 'Brand': (26, profile['caption_weight'])}
        for index, line in enumerate(lines):
            if line.startswith('Style: '):
                columns = line.split(',')
                role = columns[0].removeprefix('Style: ')
                columns[1] = profile['font_family']
                columns[2] = str(replacements[role][0])
                columns[7] = '-1' if replacements[role][1]>=700 else '0'
                lines[index] = ','.join(columns)
    if themed:
        for index,line in enumerate(lines):
            if line.startswith('Style: '):
                columns=line.split(',')
                columns[5]=ass_color(preset['background'])
                columns[6]=ass_color(preset['background'])
                if columns[0]=='Style: Head':columns[3]=ass_color(preset['accent'])
                if columns[0]=='Style: Caption' and expressive:
                    columns[2]='42' if preset['id']=='inspirational' else '38'
                    columns[7]='-1';columns[15]='1';columns[16]='3';columns[17]='1';columns[21]='155'
                lines[index]=','.join(columns)
    def event(start, end, style, text, tags='', accent=False, animate=False):
        if end <= start or not text:
            return
        if profile:
            weight=profile['heading_weight'] if style=='Head' else profile['caption_weight']
            tags='\\b'+str(weight)+tags
        safe = escape_ass(text)
        wrap = 38 if style == 'Caption' else 50 if style=='Brand' else 27
        if style=='Head':
            formatted,font_size=headline_layout(safe,size=profile['heading_size'] if profile else 64,proper_names=plan.get('proper_names',''),font_path=font_path(profile,'heading') if profile else None)
            wrapped=formatted.split('\n')
            if themed and preset['id']=='inspirational':
                formatted,font_size=headline_layout(safe.upper(),size=88,proper_names=plan.get('proper_names',''),font_path=font_path(profile,'heading') if profile else None)
                wrapped=formatted.split('\n')
                tags+='\\bord10\\3c&H003D1021&\\shad7\\4c&H00D62BFF&'
            tags+='\\fs'+str(font_size)
        elif style=='Caption' and profile:
            from PIL import ImageFont
            font=ImageFont.truetype(str(font_path(profile,'caption')),profile['caption_size'])
            wrapped=[]; words=[]
            for word in safe.split():
                if words and font.getlength(' '.join([*words,word]))>620:
                    wrapped.append(' '.join(words));words=[]
                words.append(word)
            if words:wrapped.append(' '.join(words))
            if len(wrapped)>2:
                total=sum(len(line.split()) for line in wrapped);offset=0
                for index in range(0,len(wrapped),2):
                    page=' '.join(wrapped[index:index+2]);count=len(page.split())
                    event(start+(end-start)*offset/total,start+(end-start)*(offset+count)/total,style,page,tags)
                    offset+=count
                return
        else:
            wrapped = textwrap.wrap(safe, width=wrap)
        if len(wrapped)>2:
            wrapped = [wrapped[0],wrapped[1].rstrip('.,')+'…']
        if accent:
            count=sum(len(line.split()) for line in wrapped);offset=0;colored=[]
            for line in wrapped:
                tokens=[]
                for word in line.split():
                    tokens.append(('{\\c&H00C8F2FF&}'+word+'{\\c&H00FFFFFF&}') if offset>=count-2 else word)
                    offset+=1
                colored.append(' '.join(tokens))
            wrapped=colored
        if animate:
            tags+='\\fscx96\\fscy96\\t(0,220,\\fscx100\\fscy100)'
        safe = '\\N'.join(wrapped)
        fade='' if dynamic and plan['motion_style'].get('effects_disabled') else '\\fad(150,150)'
        lines.append(f'Dialogue: 0,{ass_time(start)},{ass_time(end)},{style},,0,0,0,,{{{fade}{tags}}}{safe}')

    text_enabled = plan.get('show_text', True) and plan.get('text_enabled', True)
    show_captions = text_enabled and plan.get('show_captions', True)

    if show_captions:
        if expressive:
            expressive_captions(lines,plan,preset,profile,ass_color)
        else:
            for sub in caption_chunks(mapped_subtitles(plan),max_words=preset['caption_words'] if themed else profile['max_words'] if profile else 7,proper_names=plan.get("proper_names","")):
                event(sub['start'],sub['end'],'Caption',sub['text'])

    if text_enabled:
        for scene in plan.get('storyboard', []):
            if scene['scene_type'] not in ('talking_head', 'broll'):
                continue
            start = scene['timeline_start']
            end = start + scene['duration']
            motion=scene.get('motion',{}) if dynamic else {}
            closing=motion.get('closing_text','')
            headline_end=min(end,start+motion.get('headline_seconds',scene['duration']))
            closing_start=max(start,end-2.6) if closing else end
            if closing:headline_end=min(headline_end,closing_start-.15)
            color = {'teal':'&H0088940D&','navy':'&H003B2D17&','red':'&H002626DC&'}.get(scene.get('badge_color'), '&H0088940D&')
            if scene.get('badge_text'):
                event(start,end,'Label',scene.get('badge_text',''),f'\\3c{color}\\4c{color}')
            if scene.get('headline') and not any(t['timeline_start'] < end and t['timeline_start']+t['duration'] > start for t in plan.get('text_overlays', [])):
                strong=themed and preset['id']=='inspirational'
                movement=('\\move(360,940,360,900,0,180)\\frz-3' if strong else '\\move(360,194,360,176,0,260)') if motion.get('animate',True) else ('\\pos(360,900)' if strong else '')
                event(start+.15,headline_end,'Head',scene.get('headline',''),movement,accent=bool(motion.get('accent_words')),animate=bool(motion.get('animate',False)))
            if closing:
                event(closing_start,end,'Head',closing,accent=True,animate=motion.get('animate',False))

        # Explicit titles remain editable. Hide camera headings during their span.
        for title in plan.get('text_overlays', []):
            start = title['timeline_start']
            if title.get('text'):
                event(start,start+title['duration'],'Head',title['text'])

        branding_cfg = plan.get('branding', {})
        if branding_cfg.get('brand_name') and branding_cfg.get('show_brand_name', True) and not plan.get('brand_footer') == '':
            event(0,sum(c['duration'] for c in plan['video_clips']),'Brand',branding_cfg['brand_name'])

    path.write_text('\n'.join(lines)+'\n',encoding='utf-8')
