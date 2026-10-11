"""Shared typography and safe areas from the approved DANAVA review edit."""
import textwrap
from editing import ass_time, mapped_subtitles


def escape_ass(text):
    # Model / user text is always literal; never allow ASS control sequences.
    return str(text).replace('\\', '／').replace('{', '(').replace('}', ')').replace('\n', ' ')


def caption_chunks(subs, max_words=7):
    result = []
    for sub in subs:
        timed=sub.get('words',[])
        joined=' '.join(w['word'].strip() for w in timed)
        if timed and ' '.join(joined.split())==' '.join(sub['text'].split()):
            group=[]
            for word in timed:
                group.append(word)
                if len(group)>=max_words or (len(group)>=3 and word['word'].rstrip().endswith(('.',',','!','?',';'))):
                    result.append({'start':group[0]['start'],'end':group[-1]['end'],'text':' '.join(w['word'].strip() for w in group)})
                    group=[]
            if group:
                result.append({'start':group[0]['start'],'end':group[-1]['end'],'text':' '.join(w['word'].strip() for w in group)})
            continue
        words = sub['text'].split()
        if not words:
            continue
        duration = sub['end'] - sub['start']
        for index in range(0, len(words), max_words):
            end = min(len(words), index + max_words)
            result.append({'start': sub['start'] + duration * index / len(words),
                           'end': sub['start'] + duration * end / len(words),
                           'text': ' '.join(words[index:end])})
    return result


def write_storyboard_ass(path, plan, width, height):
    # Render at a fixed design coordinate system; libass scales for preview.
    lines = ['[Script Info]', 'ScriptType: v4.00+', 'PlayResX: 720', 'PlayResY: 1280',
             'WrapStyle: 2', '[V4+ Styles]',
             'Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding',
             'Style: Caption,Inter,32,&H00FFFFFF,&H00FFFFFF,&H003B2D17,&H003B2D17,-1,0,0,0,100,100,0,0,3,12,0,2,45,45,118,1',
             'Style: Head,Barlow Condensed,64,&H00FFFFFF,&H00FFFFFF,&H003B2D17,&H803B2D17,-1,0,0,0,100,100,0,0,1,2,1,8,40,40,170,1',
             'Style: Label,Inter,22,&H00FFFFFF,&H00FFFFFF,&H0088940D,&H0088940D,-1,0,0,0,100,100,2,0,3,10,0,8,40,40,110,1',
             '[Events]', 'Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text']
    def event(start, end, style, text, tags=''):
        if end <= start or not text:
            return
        safe = escape_ass(text)
        wrap = 38 if style == 'Caption' else 27
        wrapped = textwrap.wrap(safe, width=wrap)
        if len(wrapped)>2:
            wrapped = [wrapped[0],wrapped[1].rstrip('.,')+'…']
        safe = '\\N'.join(wrapped)
        lines.append(f'Dialogue: 0,{ass_time(start)},{ass_time(end)},{style},,0,0,0,,{{\\fad(150,150){tags}}}{safe}')
    for sub in caption_chunks(mapped_subtitles(plan)):
        event(sub['start'],sub['end'],'Caption',sub['text'])
    for scene in plan.get('storyboard', []):
        if scene['scene_type'] not in ('talking_head', 'broll'):
            continue
        start = scene['timeline_start']
        end = start + scene['duration']
        color = {'teal':'&H0088940D&','navy':'&H003B2D17&','red':'&H002626DC&'}.get(scene.get('badge_color'), '&H0088940D&')
        event(start,end,'Label',scene.get('badge_text',''),f'\\3c{color}\\4c{color}')
        if not any(t['timeline_start'] < end and t['timeline_start']+t['duration'] > start for t in plan.get('text_overlays', [])):
            event(start+.15,end,'Head',scene.get('headline',''), '\\move(360,194,360,176,0,260)')
    # Explicit titles remain editable. Hide camera headings during their span.
    # AI is instructed to use scene headlines instead of duplicate title tracks.
    for title in plan.get('text_overlays', []):
        start = title['timeline_start']
        event(start,start+title['duration'],'Head',title['text'])
    path.write_text('\n'.join(lines)+'\n',encoding='utf-8')
