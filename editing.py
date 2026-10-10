"""Deterministic, offline edit planning and FFmpeg compilation."""
import copy
import json
import math
import os
import re
import subprocess
import textwrap
import uuid
import random
import struct
import wave
from pathlib import Path


def uid():
    return str(uuid.uuid4())


def probe(path):
    result = subprocess.run(['ffprobe', '-v', 'error', '-show_streams', '-show_format', '-of', 'json', str(path)], capture_output=True, text=True, timeout=30)
    if result.returncode:
        raise ValueError('Không đọc được tài nguyên bằng FFprobe.')
    info = json.loads(result.stdout)
    video = next((s for s in info['streams'] if s['codec_type'] == 'video'), None)
    if not video:
        raise ValueError('Tài nguyên không có hình ảnh/video hợp lệ.')
    rotation = next((s.get('rotation', 0) for s in video.get('side_data_list', []) if 'rotation' in s), video.get('tags', {}).get('rotate', 0))
    w, h = video['width'], video['height']
    if abs(int(rotation)) % 180 == 90:
        w, h = h, w
    duration = float(info.get('format', {}).get('duration', video.get('duration', 0)) or 0)
    return {'width': w, 'height': h, 'duration': duration, 'has_audio': any(s['codec_type'] == 'audio' for s in info['streams']), 'rotation': rotation}


def probe_audio(path):
    result = subprocess.run(['ffprobe', '-v', 'error', '-show_streams', '-show_format', '-of', 'json', str(path)], capture_output=True, text=True, timeout=30)
    if result.returncode:
        raise ValueError('Không đọc được file âm thanh.')
    info = json.loads(result.stdout)
    if not any(stream['codec_type'] == 'audio' for stream in info['streams']):
        raise ValueError('File không có âm thanh.')
    duration = float(info.get('format', {}).get('duration', 0))
    if not math.isfinite(duration) or duration <= 0:
        raise ValueError('Thời lượng âm thanh không hợp lệ.')
    return {'duration': duration, 'has_audio': True}


def synth_sound(path, kind, duration):
    """Small original procedural accents; no downloaded/copyrighted sound packs."""
    rate = 48000
    rng = random.Random(17)
    duration = min(duration, 4)
    samples = bytearray()
    for i in range(round(rate * duration)):
        t = i / rate
        phase = t / duration
        if kind == 'whoosh':
            value = rng.uniform(-1, 1) * math.sin(math.pi * phase) ** 2 * .6
        elif kind == 'impact':
            value = (math.sin(2 * math.pi * (65*t + 25*t*t)) + .25*rng.uniform(-1, 1)) * math.exp(-10*phase) * .65
        else:
            value = (math.sin(2*math.pi*880*t) + .4*math.sin(2*math.pi*1320*t)) * math.exp(-5*phase) * .45
        value *= min(1, t / .01, (duration-t) / .02)
        samples += struct.pack('<h', round(max(-1, min(1, value))*32767))
    with wave.open(str(path), 'wb') as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(rate)
        output.writeframes(samples)


def length(plan):
    return sum(float(c['duration']) for c in plan['video_clips'])


def finite(value, low, high, label):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not low <= value <= high:
        raise ValueError(f'{label}: giá trị phải nằm trong {low}–{high}.')


def validate(plan, trusted_assets):
    """Only project-owned assets and contiguous clips can enter the compiler."""
    p = copy.deepcopy(plan)
    assets = {a['id']: a for a in trusted_assets}
    if not p.get('video_clips') or len(p['video_clips']) > 100:
        raise ValueError('Cần 1–100 đoạn video chính.')
    cursor = 0
    for c in p['video_clips']:
        asset = assets.get(c.get('asset_id'))
        if not asset or asset['type'] != 'video':
            raise ValueError('Đoạn chính phải dùng video thuộc dự án.')
        source_duration = float(asset['metadata']['duration'])
        finite(c.get('source_in'), 0, source_duration, 'Điểm đầu')
        finite(c.get('duration'), .04, source_duration, 'Thời lượng')
        if c['source_in'] + c['duration'] > source_duration + .02:
            raise ValueError('Đoạn cắt vượt thời lượng nguồn.')
        c['timeline_start'] = cursor
        c['source_out'] = c['source_in'] + c['duration']
        cursor += c['duration']
    settings = p.setdefault('output_settings', {})
    for key in ('width', 'height'):
        finite(settings.get(key), 120, 1920, key)
        settings[key] = int(settings[key]) // 2 * 2
    finite(settings.get('fps', 30), 10, 60, 'FPS')
    settings['fps'] = int(settings.get('fps', 30))
    if settings.get('fit', 'contain') not in ('contain', 'cover'):
        raise ValueError('Cách fit không hợp lệ.')
    for key in ('subtitles', 'text_overlays', 'visual_overlays', 'effect_keyframes'):
        items = p.setdefault(key, [])
        if not isinstance(items, list) or len(items) > 2000:
            raise ValueError('Quá nhiều đối tượng trên timeline.')
    for sub in p['subtitles']:
        # Subtitles are intentionally stored in source time and mapped at render.
        finite(sub.get('start'), 0, 86400, 'Phụ đề bắt đầu')
        finite(sub.get('end'), sub['start'] + .001, 86400, 'Phụ đề kết thúc')
        if not isinstance(sub.get('text'), str) or len(sub['text']) > 2000:
            raise ValueError('Nội dung phụ đề không hợp lệ.')
    for key in ('text_overlays', 'visual_overlays', 'effect_keyframes'):
        for item in p[key]:
            finite(item.get('timeline_start'), 0, max(0, cursor - .001), 'Thời gian hiệu ứng')
            finite(item.get('duration'), .04, cursor, 'Thời lượng hiệu ứng')
            if item['timeline_start'] + item['duration'] > cursor + .02:
                raise ValueError('Hiệu ứng vượt timeline. Hãy dựng lại sau khi cắt video.')
            if key == 'text_overlays':
                if not isinstance(item.get('text'), str) or not 1 <= len(item['text']) <= 160:
                    raise ValueError('Chữ nhấn mạnh cần 1–160 ký tự.')
            elif key == 'visual_overlays':
                a = assets.get(item.get('asset_id'))
                if not a or a['type'] not in ('image', 'video'):
                    raise ValueError('Minh họa phải là ảnh/video thuộc dự án.')
                for field, default in [('x', .05), ('y', .08), ('width', .38)]:
                    finite(item.get(field, default), 0 if field != 'width' else .1, 1, field)
                if item.get('mode', 'pip') not in ('pip', 'full'):
                    raise ValueError('Chế độ minh họa không hợp lệ.')
                if a['type'] == 'video':
                    finite(item.get('source_in', 0), 0, a['metadata']['duration'], 'Nguồn minh họa')
                    if item.get('source_in', 0) + item['duration'] > a['metadata']['duration'] + .02:
                        raise ValueError('Minh họa vượt thời lượng video nguồn.')
            else:
                finite(item.get('scale', 1.08), 1, 1.2, 'Mức zoom')
    p['assets'] = copy.deepcopy(trusted_assets)
    tracks = p.setdefault('audio_tracks', [])
    if not isinstance(tracks, list) or len(tracks) > 100:
        raise ValueError('Cần tối đa 100 đối tượng âm thanh.')
    for track in tracks:
        finite(track.get('timeline_start'), 0, max(0, cursor - .001), 'Âm thanh bắt đầu')
        finite(track.get('duration'), .04, cursor, 'Thời lượng âm thanh')
        finite(track.get('volume', .15), 0, 1, 'Âm lượng')
        if track['timeline_start'] + track['duration'] > cursor + .02:
            raise ValueError('Âm thanh vượt timeline.')
        if track.get('kind') == 'music':
            a = assets.get(track.get('asset_id'))
            if not a or a['type'] != 'audio':
                raise ValueError('Nhạc nền phải là file âm thanh đã tải lên dự án.')
            finite(track.get('source_in', 0), 0, a['metadata']['duration'] - .001, 'Điểm đầu nhạc')
            if not isinstance(track.get('loop', True), bool):
                raise ValueError('Lặp nhạc phải là boolean.')
            if not track.get('loop', True) and track.get('source_in', 0) + track['duration'] > a['metadata']['duration'] + .02:
                raise ValueError('Nhạc vượt thời lượng nguồn.')
        elif track.get('kind') not in ('whoosh', 'impact', 'chime') or track['duration'] > 4:
            raise ValueError('Hiệu ứng âm thanh chỉ hỗ trợ whoosh/impact/chime, tối đa 4 giây.')
    finite(settings.get('source_volume', 1), 0, 1.5, 'Âm lượng tiếng gốc')
    return p


def mapped_subtitles(plan):
    result = []
    for clip in plan['video_clips']:
        for sub in plan.get('subtitles', []):
            if sub.get('asset_id') and sub['asset_id'] != clip['asset_id']:
                continue
            start = max(sub['start'], clip['source_in'])
            end = min(sub['end'], clip['source_in'] + clip['duration'])
            if end > start:
                result.append({**sub, 'start': start - clip['source_in'] + clip['timeline_start'], 'end': end - clip['source_in'] + clip['timeline_start']})
    return sorted(result, key=lambda x: x['start'])


def auto_plan(plan, intensity='balanced', headline=''):
    p = copy.deepcopy(plan)
    presets = {'gentle': (12, 1.055), 'balanced': (9, 1.085), 'bold': (7, 1.11)}
    interval, zoom = presets.get(intensity, presets['balanced'])
    total = length(p)
    # Preserve manual edits; replace only generated objects on reruns.
    for key in ('effect_keyframes', 'text_overlays', 'visual_overlays', 'audio_tracks'):
        p[key] = [x for x in p.get(key, []) if x.get('origin') != 'auto']
    shortest = min(a['metadata']['width'] for a in p['assets'] if a['type'] == 'video')
    zoom = min(zoom, 1.06) if shortest < 480 else zoom
    for start in range(1, max(1, math.ceil(total - 1)), interval):
        p['effect_keyframes'].append({'id': uid(), 'origin': 'auto', 'timeline_start': start, 'duration': min(4, total - start), 'scale': zoom})
    mapped = mapped_subtitles(p)
    last = -interval
    for sub in mapped:
        if sub['start'] - last < interval or not sub['text'].strip():
            continue
        words = sub['text'].strip().split()
        # Extract real source words, not invented semantic claims.
        text = ' '.join(words[:6]).strip(' ,.!?')
        duration = min(2.5, sub['end'] - sub['start'], total - sub['start'])
        if text and duration >= .3:
            p['text_overlays'].append({'id': uid(), 'origin': 'auto', 'timeline_start': sub['start'], 'duration': duration, 'text': text})
            last = sub['start']
    if headline.strip():
        p['text_overlays'].insert(0, {'id': uid(), 'origin': 'auto', 'timeline_start': 0, 'duration': min(3, total), 'text': headline.strip()[:120]})
    main_ids = {c['asset_id'] for c in p['video_clips']}
    candidates = [a for a in p['assets'] if a['type'] in ('image', 'video') and a['id'] not in main_ids and a.get('keywords')]
    used = set()
    for sub in mapped:
        if any(abs(sub['start'] - t) < 6 for t in used):
            continue
        a = next((a for a in candidates if any(k.strip().casefold() in sub['text'].casefold() for k in a['keywords'].split(',') if k.strip())), None)
        if not a:
            continue
        duration = min(3, total - sub['start'], a['metadata']['duration'] if a['type'] == 'video' else 3)
        if duration >= .3:
            p['visual_overlays'].append({'id': uid(), 'origin': 'auto', 'asset_id': a['id'], 'timeline_start': sub['start'], 'duration': duration, 'mode': 'pip', 'x': .05, 'y': .1, 'width': .4})
            used.add(sub['start'])
    p.pop('director', None)
    p['output_settings']['source_volume'] = 1
    p['preset'] = intensity
    return p


def parse_srt(content, asset_id):
    blocks = re.split(r'\n\s*\n', content.replace('\r', '').strip().lstrip('\ufeff'))
    result = []
    pattern = r'(\d{2,}):(\d{2}):(\d{2})[,.](\d{3})'
    def stamp(match):
        h, m, s, ms = map(int, match)
        return h * 3600 + m * 60 + s + ms / 1000
    for block in blocks:
        lines = block.splitlines()
        index = next((i for i, line in enumerate(lines) if '-->' in line), None)
        if index is None:
            raise ValueError('SRT thiếu mốc thời gian.')
        matches = re.findall(pattern, lines[index])
        if len(matches) != 2:
            raise ValueError('Mốc SRT phải có dạng 00:00:01,000.')
        start, end = map(stamp, matches)
        text = ' '.join(lines[index + 1:]).strip()
        if end <= start or not text:
            raise ValueError('Câu phụ đề hoặc thời gian không hợp lệ.')
        result.append({'id': uid(), 'asset_id': asset_id, 'start': start, 'end': end, 'text': text})
    return result


def srt_time(s):
    ms = round(s * 1000)
    return f'{ms // 3600000:02}:{ms // 60000 % 60:02}:{ms // 1000 % 60:02},{ms % 1000:03}'


def srt_content(subs):
    return '\n\n'.join(f'{i+1}\n{srt_time(s["start"])} --> {srt_time(s["end"])}\n{s["text"]}' for i, s in enumerate(subs)) + '\n'


def filter_path(path):
    return str(path).replace('\\', '/').replace(':', '\\:').replace("'", "'\\''")


def ass_time(s):
    cs = round(s * 100)
    return f'{cs // 360000}:{cs // 6000 % 60:02}:{cs // 100 % 60:02}.{cs % 100:02}'


def write_ass(path, subs, w, h, visual_style='clean_expert'):
    font_size = max(14, round(w * .04))
    wrap = max(16, min(48, round(w / font_size * 1.65)))
    
    # ASS colors are &HAABBGGRR (Alpha, Blue, Green, Red) in hex.
    if visual_style == 'dynamic_reels':
        # Vàng (Primary), Đen (Outline), BorderStyle=1 (Outline)
        font_size = max(18, round(w * .05))
        style_line = f"Style: Default,Arial,{font_size},&H0000FFFF,&H0000FFFF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,3,1,2,{round(w*.07)},{round(w*.07)},{round(h*.10)},1"
    elif visual_style == 'danava_brand':
        # Trắng (Primary), Tím (Background Box), BorderStyle=3 (Opaque box) - Tím là ED3A7C -> BGR = 7C3AED (nhưng opacity 50% = 80) -> &H80ED3A7C
        style_line = f"Style: Default,Arial,{font_size},&H00FFFFFF,&H00FFFFFF,&H00212121,&H80ED3A7C,-1,0,0,0,100,100,0,0,3,2,0,2,{round(w*.07)},{round(w*.07)},{round(h*.07)},1"
    else: # clean_expert
        style_line = f"Style: Default,Arial,{font_size},&H00FFFFFF,&H00FFFFFF,&H00212121,&H80212121,-1,0,0,0,100,100,0,0,3,2,0,2,{round(w*.07)},{round(w*.07)},{round(h*.07)},1"

    header = f'''[Script Info]
ScriptType: v4.00+
PlayResX: {w}
PlayResY: {h}
WrapStyle: 0
[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
{style_line}
[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
'''
    events = []
    for s in subs:
        text = re.sub(r'[{}\\\r\n]', ' ', s['text'])
        lines = textwrap.wrap(text, width=wrap)
        # Split very long captions into timed two-line pages, never hide words.
        pages = [lines[i:i+2] for i in range(0, len(lines), 2)] or [['']]
        page_duration = (s['end'] - s['start']) / len(pages)
        for i, page in enumerate(pages):
            text = r'\N'.join(page)
            events.append(f'Dialogue: 0,{ass_time(s["start"]+i*page_duration)},{ass_time(s["start"]+(i+1)*page_duration)},Default,,0,0,0,,{text}\n')
    path.write_text(header + ''.join(events), encoding='utf-8')


def compile_render(plan, asset_dir, work_dir, output, preview=False, visual_style='clean_expert'):
    """Compile contiguous A/V clips, timed zoom, titles, overlays and captions."""
    settings = plan['output_settings']
    w, h, fps = settings['width'], settings['height'], settings.get('fps', 30)
    if preview and max(w, h) > 640:
        ratio = 640 / max(w, h)
        w, h = int(w * ratio) // 2 * 2, int(h * ratio) // 2 * 2
    total = min(length(plan), 12) if preview else length(plan)
    assets = {a['id']: a for a in plan['assets']}
    cmd = ['ffmpeg', '-hide_banner', '-y', '-filter_complex_threads', '1']
    clips = plan['video_clips']
    for c in clips:
        cmd += ['-ss', str(c['source_in']), '-t', str(c['duration']), '-i', str(asset_dir / assets[c['asset_id']]['filename'])]
    overlays = plan.get('visual_overlays', [])
    for ov in overlays:
        a = assets[ov['asset_id']]
        if a['type'] == 'image':
            cmd += ['-loop', '1', '-framerate', str(fps), '-t', str(ov['duration']), '-i', str(asset_dir / a['filename'])]
        else:
            cmd += ['-ss', str(ov.get('source_in', 0)), '-t', str(ov['duration']), '-i', str(asset_dir / a['filename'])]
    tracks = plan.get('audio_tracks', [])
    for i, track in enumerate(tracks):
        if track['kind'] == 'music':
            a = assets[track['asset_id']]
            if track.get('loop', True):
                cmd += ['-stream_loop', '-1']
            cmd += ['-ss', str(track.get('source_in', 0)), '-t', str(track['duration']), '-i', str(asset_dir / a['filename'])]
        else:
            path = work_dir / f'sound{i}.wav'
            synth_sound(path, track['kind'], track['duration'])
            cmd += ['-i', str(path)]
    filters = []
    def fit(width, height, mode='contain'):
        if mode == 'cover':
            return f'scale={width}:{height}:force_original_aspect_ratio=increase,crop={width}:{height},setsar=1'
        return f'scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,setsar=1'
    for i, c in enumerate(clips):
        filters.append(f'[{i}:v]setpts=PTS-STARTPTS,{fit(w,h,settings.get("fit","contain"))},fps={fps},format=yuv420p[v{i}]')
        if assets[c['asset_id']]['metadata'].get('has_audio'):
            filters.append(f'[{i}:a]asetpts=PTS-STARTPTS,aresample=48000,aformat=channel_layouts=stereo,apad,atrim=duration={c["duration"]}[a{i}]')
        else:
            filters.append(f'anullsrc=r=48000:cl=stereo,atrim=duration={c["duration"]}[a{i}]')
    filters.append(''.join(f'[v{i}][a{i}]' for i in range(len(clips))) + f'concat=n={len(clips)}:v=1:a=1[base][audio]')
    current = 'base'
    effects = plan.get('effect_keyframes', [])
    if effects:
        bumps = []
        for e in effects:
            start, d = e['timeline_start'], e['duration']
            bumps.append(f'if(between(on/{fps},{start},{start+d}),{e["scale"]-1}*pow(sin(PI*(on/{fps}-{start})/{d}),2),0)')
        z = '1+' + '+'.join(bumps)
        filters.append(f"[{current}]scale={w*2}:{h*2},zoompan=z='min(1.2,{z})':x='(iw-iw/zoom)/2':y='(ih-ih/zoom)/2':d=1:s={w}x{h}:fps={fps}[zoom]")
        current = 'zoom'
    for i, ov in enumerate(overlays):
        a = assets[ov['asset_id']]
        full = ov.get('mode') == 'full'
        ow = w if full else max(2, int(w * ov.get('width', .38)) // 2 * 2)
        oh = h if full else max(2, min(int(h * .45), round(ow * a['metadata']['height'] / a['metadata']['width'])) // 2 * 2)
        start, end = ov['timeline_start'], ov['timeline_start'] + ov['duration']
        filters.append(f'[{len(clips)+i}:v]{fit(ow,oh)},fps={fps},format=rgba,setpts=PTS-STARTPTS+{start}/TB,fade=t=in:st={start}:d=0.2:alpha=1,fade=t=out:st={end-0.2}:d=0.2:alpha=1[ov{i}]')
        x = 0 if full else min(round(ov.get('x', .05) * w), w-ow)
        y = 0 if full else min(round(ov.get('y', .08) * h), h-oh)
        filters.append(f"[{current}][ov{i}]overlay=x={x}:y={y}:eof_action=pass:repeatlast=0:enable='gte(t,{start})*lt(t,{end})'[layer{i}]")
        current = f'layer{i}'
    fontfile = os.getenv('VIDEO_FONT_FILE')
    font = f"fontfile='{filter_path(fontfile)}'" if fontfile else "font='Arial'"
    for i, title in enumerate(plan.get('text_overlays', [])):
        path = work_dir / f'title{i}.txt'
        start, end = title['timeline_start'], title['timeline_start'] + title['duration']
        # Fit long titles to frame instead of cropping them.
        size = max(10, round(w*.06))
        line_width = max(12, int(w*.85 / (size*.65)))
        path.write_text('\n'.join(textwrap.wrap(title['text'], width=line_width)), encoding='utf-8')
        alpha = f'min(1,min((t-{start})/0.18,({end}-t)/0.18))'
        
        # Style cho title
        if visual_style == 'dynamic_reels':
            text_style = f"fontcolor=yellow:borderw=4:bordercolor=black"
        elif visual_style == 'danava_brand':
            text_style = f"fontcolor=white:borderw=2:bordercolor=black:box=1:boxcolor=0x7C3AED@0.8:boxborderw=8"
        else: # clean_expert
            text_style = f"fontcolor=white:borderw=1:bordercolor=black:box=1:boxcolor=black@0.6:boxborderw=8"
            
        filters.append(f"[{current}]drawtext={font}:textfile='{filter_path(path)}':expansion=none:fontsize={size}:{text_style}:x=(w-tw)/2:y=h*0.14:alpha='{alpha}':enable='gte(t,{start})*lt(t,{end})'[title{i}]")
        current = f'title{i}'
    subs = mapped_subtitles(plan)
    if subs:
        path = work_dir / 'captions.ass'
        write_ass(path, subs, w, h, visual_style)
        filters.append(f"[{current}]subtitles=filename='{filter_path(path)}'[captions]")
        current = 'captions'
    audio = 'audio'
    if tracks or settings.get('source_volume', 1) != 1:
        filters.append(f'[audio]volume={settings.get("source_volume", 1)}[voice]')
        music_count = sum(t['kind'] == 'music' for t in tracks)
        if music_count:
            filters.append('[voice]asplit=' + str(music_count+1) + '[dry]' + ''.join(f'[duck{i}]' for i in range(music_count)))
            audio = 'dry'
        else:
            audio = 'voice'
        mixed = [audio]
        duck = 0
        for i, track in enumerate(tracks):
            idx = len(clips) + len(overlays) + i
            d, start = track['duration'], track['timeline_start']
            fade = min(.25, d/3)
            filters.append(f'[{idx}:a]asetpts=PTS-STARTPTS,aresample=48000,aformat=channel_layouts=stereo,apad,atrim=duration={d},volume={track.get("volume", .15)},afade=t=in:d={fade},afade=t=out:st={d-fade}:d={fade},adelay={round(start*1000)}:all=1[track{i}]')
            if track['kind'] == 'music':
                filters.append(f'[track{i}][duck{duck}]sidechaincompress=threshold=0.025:ratio=8:attack=15:release=300[ducked{i}]')
                mixed.append(f'ducked{i}')
                duck += 1
            else:
                mixed.append(f'track{i}')
        filters.append(''.join(f'[{label}]' for label in mixed) + f'amix=inputs={len(mixed)}:duration=first:normalize=0,alimiter=limit=0.95:latency=1[mixed]')
        audio = 'mixed'
    cmd += ['-filter_complex', ';'.join(filters), '-map', f'[{current}]', '-map', f'[{audio}]' , '-t', str(total), '-c:v', 'libx264', '-preset', 'ultrafast' if preview else 'fast', '-crf', '25' if preview else '20', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '128k', '-movflags', '+faststart', '-threads', '2', '-progress', 'pipe:1', '-nostats', str(output)]
    return cmd, total
