"""Local Ollama director: semantic decisions -> bounded, executable edit plan.

Model output is data only; it can never supply paths, filters or shell commands.
"""
import base64
import copy
import json
import os
import re
import subprocess
import time

import httpx
from pydantic import BaseModel, ConfigDict, Field
from editing import length, mapped_subtitles, uid, validate


class Decision(BaseModel):
    model_config = ConfigDict(extra='forbid')


class Cut(Decision):
    start: float = Field(ge=0)
    end: float = Field(gt=0)


class Timed(Decision):
    start: float = Field(ge=0)
    duration: float = Field(ge=.04)


class Title(Timed):
    text: str = Field(min_length=1, max_length=160)


class Zoom(Timed):
    scale: float = Field(ge=1, le=1.2)


class Illustration(Timed):
    asset_id: str
    source_in: float = Field(default=0, ge=0)
    mode: str = Field(default='pip', pattern='^(pip|full)$')


class Sound(Timed):
    kind: str = Field(pattern='^(whoosh|impact|chime)$')
    volume: float = Field(default=.15, ge=0, le=2.0)


class Direction(Decision):
    summary: str = Field(min_length=1, max_length=2000)
    warnings: list[str] = Field(default_factory=list, max_length=20)
    cuts: list[Cut] = Field(min_length=1, max_length=100)
    titles: list[Title] = Field(default_factory=list, max_length=60)
    zooms: list[Zoom] = Field(default_factory=list, max_length=60)
    illustrations: list[Illustration] = Field(default_factory=list, max_length=60)
    sounds: list[Sound] = Field(default_factory=list, max_length=60)
    music_volume: float = Field(default=.12, ge=0, le=1.0)
    source_volume: float = Field(default=1, ge=0, le=2.0)


def base_url():
    return os.getenv('OLLAMA_URL', 'http://127.0.0.1:11434').rstrip('/')


def model_name():
    return os.getenv('VIDEO_AI_MODEL', 'qwen3:4b')


def ai_health():
    result = {'available': False, 'model': model_name(), 'models': [],
              'vision': os.getenv('VIDEO_AI_VISION', '0') == '1'}
    try:
        with httpx.Client(timeout=5, trust_env=False) as client:
            response = client.get(base_url() + '/api/tags')
            response.raise_for_status()
            result['models'] = [m['name'] for m in response.json().get('models', [])]
            result['available'] = model_name() in result['models'] or model_name() + ':latest' in result['models']
    except (httpx.HTTPError, ValueError, KeyError):
        pass
    return result


def cancelled(event):
    if event.is_set():
        raise InterruptedError('Đã hủy tác vụ AI.')


def analyse(plan, asset_dir, work, event):
    """Bounded scene/silence cues; frames are sent only to an opted-in vision model."""
    assets = {a['id']: a for a in plan['assets']}
    cues, images = [], []
    cursor = 0
    vision = os.getenv('VIDEO_AI_VISION', '0') == '1'
    for index, clip in enumerate(plan['video_clips']):
        cancelled(event)
        a = assets[clip['asset_id']]
        source = asset_dir / a['filename']
        # Sample up to 120s per clip; avoid falsely claiming full video analysis.
        seconds = min(120, clip['duration'])
        command = ['ffmpeg', '-hide_banner', '-ss', str(clip['source_in']), '-t', str(seconds), '-i', str(source),
                   '-vf', "select='gt(scene,0.3)',showinfo", '-an', '-f', 'null', '-']
        if a['metadata'].get('has_audio'):
            command[command.index('-an'):command.index('-an')+1] = ['-af', 'silencedetect=noise=-35dB:d=0.45']
        result = subprocess.run(command, capture_output=True, text=True, timeout=180)
        if result.returncode:
            raise RuntimeError('Không phân tích được video: ' + result.stderr[-1000:])
        scenes = [cursor + float(t) for t in re.findall(r'pts_time:([\d.]+)', result.stderr)][:60]
        silence = [{'kind': kind, 'time': cursor + float(t)} for kind, t in re.findall(r'silence_(start|end): ([\d.]+)', result.stderr)][:120]
        cues.append({'clip': index, 'analysed_start': cursor, 'analysed_end': cursor + seconds,
                     'scene_changes': scenes, 'silence': silence})
        if vision and len(images) < 8:
            for offset in (0, seconds / 2):
                cancelled(event)
                frame = work / f'frame-{index}-{offset}.jpg'
                subprocess.run(['ffmpeg', '-v', 'error', '-y', '-ss', str(clip['source_in'] + offset),
                                '-i', str(source), '-frames:v', '1', '-vf', 'scale=384:-2', str(frame)],
                               check=True, capture_output=True, timeout=30)
                images.append({'timeline_time': cursor + offset, 'data': base64.b64encode(frame.read_bytes()).decode()})
                if len(images) >= 8:
                    break
        cursor += clip['duration']
    return cues, images


SYSTEM = '''You are an expert, highly creative Vietnamese video editor specializing in viral Reels/TikTok videos.
Return ONLY the required JSON edit decision schema. Make the video highly engaging, dynamic, and punchy.

EFFECT REGISTRY:
1. `titles` (Text Overlay): Short punchy text (2-5 words). DO NOT overlap titles (they will collide).
2. `zooms` (Keyframe): Scale up video (1.0 to 1.5x) to punch-in on key moments. Use subtle (1.1) or dramatic (1.4).
3. `illustrations` (PIP/Full Overlay): Add B-roll images/videos. `mode` can be `pip` (picture-in-picture) or `full`.
4. `sounds` (Audio Track): Supported kinds: `whoosh` (for fast transitions/zooms), `impact` (for heavy titles), `chime` (for positive/insightful moments). Max 4 seconds. Max volume 2.0.

RULES:
- All cuts.start/end refer to the INPUT timeline. Cuts are kept ranges IN OUTPUT ORDER. Keep sentences coherent.
- Every effect (titles, zooms, illustrations, sounds) start/duration refers to the FINAL OUTPUT timeline (AFTER cuts).
- Use only given asset IDs for illustrations.
- Never invent spoken words, facts, or assets. Titles MUST paraphrase the transcript.
- Music is available only when a music_asset_id is supplied. Source captions are remapped automatically (don't output them).
- summary and warnings must be in Vietnamese.
'''


def chat(messages, event):
    cancelled(event)
    payload = {'model': model_name(), 'messages': messages, 'format': Direction.model_json_schema(),
               'stream': True, 'options': {'temperature': .35, 'num_ctx': 16384}, 'think': False}
    parts = []
    started = time.monotonic()
    try:
        with httpx.Client(timeout=httpx.Timeout(300, connect=10), trust_env=False) as client:
            with client.stream('POST', base_url() + '/api/chat', json=payload) as response:
                response.raise_for_status()
                for line in response.iter_lines():
                    cancelled(event)
                    if time.monotonic() - started > 600:
                        raise RuntimeError('AI vượt 10 phút. Dùng model nhỏ hơn hoặc rút ngắn video.')
                    if not line:
                        continue
                    chunk = json.loads(line)
                    if chunk.get('error'):
                        raise RuntimeError('Ollama: ' + chunk['error'])
                    parts.append(chunk.get('message', {}).get('content', ''))
                    if sum(map(len, parts)) > 150000:
                        raise ValueError('Phản hồi AI quá lớn.')
                    if chunk.get('done'):
                        break
    except httpx.HTTPError as exc:
        raise RuntimeError(f'Không gọi được Ollama/model {model_name()}. Chạy Ollama và tải model; kiểm tra OLLAMA_URL. {exc}') from exc
    cancelled(event)
    return ''.join(parts)


def apply_direction(plan, direction, music_asset_id=''):
    """Translate input timeline ranges to source clips; rebase existing manual edits."""
    p = copy.deepcopy(plan)
    selections = direction.cuts
    total = length(plan)
    cursor, clips, mapping = 0, [], []
    for cut in selections:
        if cut.end - cut.start < .04 or cut.end > total + .001:
            raise ValueError('AI chọn đoạn cắt ngoài timeline hoặc quá ngắn.')
        mapping.append((cut.start, cut.end, cursor))
        for clip in plan['video_clips']:
            start = max(cut.start, clip['timeline_start'])
            end = min(cut.end, clip['timeline_start'] + clip['duration'])
            if end - start >= .04:
                clips.append({**clip, 'id': uid(), 'source_in': clip['source_in'] + start - clip['timeline_start'],
                              'duration': end - start, 'timeline_start': cursor + start - cut.start})
        cursor += cut.end - cut.start
    if len(clips) > 100:
        raise ValueError('AI tạo quá nhiều đoạn cắt.')
    p['video_clips'] = clips
    # Normalize cut boundary slivers rather than letting generated timestamps drift.
    if abs(length(p) - cursor) > .01:
        raise ValueError('AI chọn điểm cắt quá sát ranh giới đoạn. Chọn khoảng dài hơn.')
    for key in ('text_overlays', 'effect_keyframes', 'visual_overlays', 'audio_tracks'):
        kept = []
        for item in plan.get(key, []):
            if item.get('origin') == 'auto':
                continue
            for start, end, output_start in mapping:
                lo, hi = max(start, item['timeline_start']), min(end, item['timeline_start'] + item['duration'])
                if hi - lo >= .04:
                    rebased = {**item, 'id': uid(), 'timeline_start': output_start + lo - start, 'duration': hi - lo}
                    if 'asset_id' in item:
                        rebased['source_in'] = item.get('source_in', 0) + lo - item['timeline_start']
                        if item.get('kind') == 'music' and item.get('loop', True):
                            asset = next(a for a in plan['assets'] if a['id'] == item['asset_id'])
                            rebased['source_in'] %= asset['metadata']['duration']
                    kept.append(rebased)
        p[key] = kept
    out_len = length(p)
    def timed(item):
        start = max(0.0, min(item.start, max(0.0, out_len - 0.04)))
        dur = max(0.04, min(item.duration, out_len - start))
        return {'id': uid(), 'origin': 'auto', 'timeline_start': round(start, 3), 'duration': round(dur, 3)}
    p['text_overlays'] += [{**timed(t), 'text': t.text} for t in direction.titles]
    p['effect_keyframes'] += [{**timed(z), 'scale': z.scale} for z in direction.zooms]
    p['visual_overlays'] += [{**timed(i), 'asset_id': i.asset_id, 'source_in': i.source_in,
                             'mode': i.mode, 'x': .05, 'y': .08, 'width': .38} for i in direction.illustrations]
    p['audio_tracks'] += [{**timed(s), 'kind': s.kind, 'volume': s.volume} for s in direction.sounds]
    if music_asset_id and direction.music_volume > 0:
        p['audio_tracks'].append({'id': uid(), 'origin': 'auto', 'kind': 'music', 'asset_id': music_asset_id,
                                  'timeline_start': 0, 'duration': length(p), 'source_in': 0,
                                  'volume': direction.music_volume, 'loop': True})
    p['output_settings']['source_volume'] = direction.source_volume
    p['director'] = {'engine': 'ollama', 'model': model_name(), 'summary': direction.summary,
                     'warnings': direction.warnings}
    return validate(p, plan['assets'])


def direct(plan, prompt, asset_dir, work, event, music_asset_id='', headline='', duration_policy='preserve', target_duration=0.0, visual_style='clean_expert'):
    cues, frames = analyse(plan, asset_dir, work, event)
    
    policy_desc = ''
    if duration_policy == 'preserve':
        policy_desc = 'MUST KEEP ALL ORIGINAL CONTENT (no cuts except removing silence). Output cuts that cover the entire video.'
    elif duration_policy == 'trim_silence':
        policy_desc = 'Cut ONLY silent parts/pauses. Keep all speech intact.'
    elif duration_policy == 'summarize':
        policy_desc = f'Summarize the video. Keep only the best parts. Target duration: {target_duration} seconds.'

    style_desc = ''
    if visual_style == 'dynamic_reels':
        style_desc = 'Use lots of zooms, pop-in titles, and heavy sound effects. Very fast-paced.'
    elif visual_style == 'clean_expert':
        style_desc = 'Keep it minimal, clean, professional. Use subtle zooms and gentle chimes. Minimal titles.'
    else:
        style_desc = 'Professional layout with brand colors. Balanced effects.'

    context = {'brief': prompt, 'headline': headline, 'input_duration': length(plan),
               'duration_policy': policy_desc,
               'visual_style': style_desc,
               'clips': plan['video_clips'], 'transcript': mapped_subtitles(plan),
               'assets': [{k: a.get(k) for k in ('id', 'type', 'original_name', 'keywords', 'metadata')} for a in plan['assets']],
               'music_asset_id': music_asset_id or None, 'cues': cues,
               'frame_times': [f['timeline_time'] for f in frames]}
    text = json.dumps(context, ensure_ascii=False)
    if len(text) > 45000:
        raise ValueError('Nội dung quá dài cho AI cục bộ. Chia video thành dự án ngắn hơn.')
    message = {'role': 'user', 'content': text}
    if frames:
        message['images'] = [f['data'] for f in frames]
    messages = [{'role': 'system', 'content': SYSTEM}, message]
    for attempt in range(2):
        raw = chat(messages, event)
        try:
            decision = Direction.model_validate_json(raw)
            result = apply_direction(plan, decision, music_asset_id)
            
            # Validation mạnh tay hơn với thời lượng
            if duration_policy == 'preserve' and length(result) < length(plan) * 0.9:
                raise ValueError(f"CRITICAL ERROR: 'preserve' policy requires keeping the ENTIRE video. Input is {length(plan)}s, but you output {length(result)}s. You MUST output cuts that cover the full {length(plan)}s.")
            elif duration_policy == 'trim_silence' and length(result) < length(plan) * 0.4:
                raise ValueError(f"Error: You deleted too much content. Only cut true silence. Input is {length(plan)}s, output is {length(result)}s.")
            elif length(result) < 3.0 and length(plan) > 10.0:
                raise ValueError(f"Error: Result duration is {length(result)}s. Too short! Must be at least 3 seconds.")
            
            # Kiểm tra chất lượng: Không chồng lớp chữ
            title_times = []
            for t in decision.titles:
                for start, end in title_times:
                    if not (t.start >= end or t.start + t.duration <= start):
                        raise ValueError(f"Titles overlap! '{t.text}' overlaps with another title. Prevent overlapping text.")
                title_times.append((t.start, t.start + t.duration))

            result['director']['prompt'] = prompt
            if not plan.get('subtitles'):
                result['director']['warnings'].append('Không có lời thoại nhận dạng; AI chưa hiểu đầy đủ nội dung nói. Cài Whisper hoặc nhập SRT.')
            if not frames:
                result['director']['warnings'].append('Model đang đọc lời thoại và mốc cảnh/âm thanh; chưa phân tích hình ảnh bằng model thị giác.')
            return result
        except (ValueError, KeyError, TypeError) as exc:
            if attempt:
                raise RuntimeError('AI chưa tạo được bản dựng hợp lệ sau lần sửa: ' + str(exc)) from exc
            messages += [{'role': 'assistant', 'content': raw},
                         {'role': 'user', 'content': 'Repair your JSON decision. Validation error: ' + str(exc)[:2000]}]
    raise RuntimeError('Không nhận được quyết định AI.')
