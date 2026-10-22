"""Local Ollama director: semantic decisions -> bounded, executable edit plan.

Model output is data only; it can never supply paths, filters or shell commands.
"""
import base64
import asyncio
from contextlib import contextmanager, suppress
from contextvars import ContextVar
import copy
import hashlib
import json
import math
import logging
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
    kind: str = Field(pattern='^(whoosh|impact|chime|pop|click)$')
    volume: float = Field(default=.15, ge=0, le=2.0)


class ComparisonColumn(Decision):
    badge: str = Field(default='', max_length=60)
    title: str = Field(max_length=100)
    points: list[str] = Field(default_factory=list, max_length=5)


class StoryboardScene(Decision):
    scene_id: str = Field(default_factory=uid)
    source_in: float = Field(default=0, ge=0)
    source_out: float = Field(default=0, ge=0)
    timeline_start: float = Field(default=0, ge=0)
    duration: float = Field(default=1.0, ge=.04)
    transcript_meaning: str = Field(default='', max_length=500)
    scene_type: str = Field(default='talking_head', pattern='^(talking_head|talking_head_pip|explainer_card|comparison|statistic|step_list|broll|cta)$')
    headline: str = Field(default='', max_length=80)
    subheadline: str = Field(default='', max_length=200)
    badge_text: str = Field(default='', max_length=60)
    badge_color: str = Field(default='teal', pattern='^(teal|navy|red)$')
    stat_number: str = Field(default='', max_length=30)
    stat_label: str = Field(default='', max_length=100)
    steps: list[str] = Field(default_factory=list, max_length=10)
    badges: list[str] = Field(default_factory=list, max_length=10)
    asset_query: str = Field(default='', max_length=100)
    sound_effect: str = Field(default='none', pattern='^(whoosh|impact|chime|pop|click|none)$')
    sound_volume: float = Field(default=.10, ge=0, le=1)
    animation_in: str = Field(default='pop_in', pattern='^(pop_in|slide_up|fade)$')
    animation_out: str = Field(default='fade', pattern='^(fade|none)$')
    layout_rationale: str = Field(default='', max_length=500)
    comparison_left: ComparisonColumn | None = None
    comparison_right: ComparisonColumn | None = None
    graphic_kind: str = Field(default='auto', pattern='^(auto|chat|process|network)$')
    graphic_title: str = Field(default='', max_length=60)
    graphic_items: list[str] = Field(default_factory=list, max_length=5)
    visual_asset_id: str = Field(default='', max_length=100)
    visual_source_in: float = Field(default=0, ge=0)


class Direction(Decision):
    summary: str = Field(min_length=1, max_length=2000)
    warnings: list[str] = Field(default_factory=list, max_length=20)
    cuts: list[Cut] = Field(min_length=1, max_length=100)
    titles: list[Title] = Field(default_factory=list, max_length=60)
    zooms: list[Zoom] = Field(default_factory=list, max_length=60)
    illustrations: list[Illustration] = Field(default_factory=list, max_length=60)
    sounds: list[Sound] = Field(default_factory=list, max_length=60)
    storyboard: list[StoryboardScene] = Field(default_factory=list, max_length=60)
    music_volume: float = Field(default=.12, ge=0, le=1.0)
    source_volume: float = Field(default=1, ge=0, le=2.0)


def base_url():
    return os.getenv('OLLAMA_URL', 'http://127.0.0.1:11434').rstrip('/')


def model_name():
    return os.getenv('VIDEO_AI_MODEL', 'qwen3:4b')


ANALYZER_VERSION = '2.0.0'
_ANALYSIS_MEMORY_CACHE = {}

KNOWN_VISION_MODELS = {
    'llava', 'llava-phi3', 'llava-llama3', 'llama3.2-vision',
    'qwen2.5-vl', 'qwen-vl', 'minicpm-v', 'bakllava', 'moondream',
    'gemma3', 'internvl'
}


class AnalysisResult(dict):
    """Analysis result containing cues, sampled frames, and diagnostic metadata.

    Supports tuple unpacking: cues, frames = analyse(...) for backward compatibility.
    """
    def __init__(self, cues, frames, diagnostics):
        super().__init__(cues=cues, frames=frames, diagnostics=diagnostics)
        self.cues = cues
        self.frames = frames
        self.diagnostics = diagnostics

    def __iter__(self):
        yield self.cues
        yield self.frames


def model_supports_vision(model: str = None) -> bool:
    """Check if the configured or specified model supports image inputs."""
    name = (model or model_name()).casefold()
    base = name.split(':')[0]
    if any(m in base for m in ('vision', '-vl', '_vl', 'llava', 'minicpm-v', 'moondream', 'bakllava')):
        return True
    if base in KNOWN_VISION_MODELS:
        return True
    try:
        with httpx.Client(timeout=2, trust_env=False) as client:
            resp = client.post(base_url() + '/api/show', json={'name': name})
            if resp.status_code == 200:
                data = resp.json()
                families = data.get('details', {}).get('families', [])
                if any('clip' in f.casefold() or 'vision' in f.casefold() or 'mllama' in f.casefold() for f in families):
                    return True
                arch = data.get('model_info', {}).get('general.architecture', '')
                if any(v in arch.casefold() for v in ('mllama', 'llava', 'vision', 'clip')):
                    return True
    except Exception:
        pass
    return False


def ai_health():
    curr_model = model_name()
    result = {'available': False, 'model': curr_model, 'models': [],
              'vision': os.getenv('VIDEO_AI_VISION', '0') == '1',
              'model_supports_vision': False}
    try:
        with httpx.Client(timeout=5, trust_env=False) as client:
            response = client.get(base_url() + '/api/tags')
            response.raise_for_status()
            result['models'] = [m['name'] for m in response.json().get('models', [])]
            result['available'] = curr_model in result['models'] or curr_model + ':latest' in result['models']
            result['model_supports_vision'] = model_supports_vision(curr_model)
    except (httpx.HTTPError, ValueError, KeyError):
        result['model_supports_vision'] = model_supports_vision(curr_model)
    return result


def cancelled(event):
    if event.is_set():
        raise InterruptedError('Đã hủy tác vụ AI.')


def analysis_cache_key(plan, asset_dir, vision_requested, max_frames, max_seconds, scene_threshold):
    hasher = hashlib.sha256()
    hasher.update(f"v={ANALYZER_VERSION};vis={vision_requested};mf={max_frames};ms={max_seconds};st={scene_threshold};".encode())
    assets = {a['id']: a for a in plan.get('assets', [])}
    for clip in plan.get('video_clips', []):
        aid = clip.get('asset_id', '')
        a = assets.get(aid, {})
        source = asset_dir / a.get('filename', '') if a.get('filename') else None
        stat_sig = ''
        if source and source.is_file():
            try:
                st = source.stat()
                stat_sig = f"{st.st_size}_{st.st_mtime_ns}"
            except Exception:
                pass
        hasher.update(f"clip={aid}:{clip.get('source_in', 0)}:{clip.get('duration', 0)}:{stat_sig};".encode())
    return hasher.hexdigest()


def analyse(plan, asset_dir, work, event):
    """Extract scene-change cues, silence cues, and uniformly sampled video frames.

    Returns AnalysisResult which unpacks into (cues, frames).
    """
    max_frames = max(1, min(24, int(os.getenv('VIDEO_AI_MAX_FRAMES', '6'))))
    max_seconds = max(5.0, float(os.getenv('VIDEO_AI_MAX_ANALYSE_SECONDS', '120')))
    scene_threshold = max(0.1, min(0.9, float(os.getenv('VIDEO_AI_SCENE_THRESHOLD', '0.3'))))
    vision_requested = os.getenv('VIDEO_AI_VISION', '0') == '1'
    current_model = model_name()
    has_vision_support = model_supports_vision(current_model)
    vision_used = bool(vision_requested and has_vision_support)

    warnings = []
    if vision_requested and not has_vision_support:
        warnings.append(f"Model '{current_model}' không hỗ trợ thị giác. Đã chuyển sang phân tích phi thị giác; chưa phân tích nội dung hình ảnh.")

    cache_key = analysis_cache_key(plan, asset_dir, vision_requested, max_frames, max_seconds, scene_threshold)
    if cache_key in _ANALYSIS_MEMORY_CACHE:
        cached = _ANALYSIS_MEMORY_CACHE[cache_key]
        cached_diag = {**cached['diagnostics'], 'cache_hit': True}
        return AnalysisResult(copy.deepcopy(cached['cues']), copy.deepcopy(cached['frames']), cached_diag)

    assets = {a['id']: a for a in plan.get('assets', [])}
    cues, frames = [], []
    analysed_ranges = []

    for index, clip in enumerate(plan.get('video_clips', [])):
        cancelled(event)
        a = assets.get(clip['asset_id'], {})
        filename = a.get('filename')
        source = asset_dir / filename if filename else None
        seconds = min(max_seconds, clip['duration'])
        if not source or not source.is_file():
            # If asset file is not on disk (e.g. synthetic test plan), record empty cue interval
            cues.append({
                'clip': index,
                'source_start': round(clip['source_in'], 3),
                'source_end': round(clip['source_in'] + seconds, 3),
                'timeline_start': round(clip['timeline_start'], 3),
                'timeline_end': round(clip['timeline_start'] + seconds, 3),
                'scene_changes': [],
                'silence': []
            })
            analysed_ranges.append({
                'clip': index,
                'source_start': round(clip['source_in'], 3),
                'source_end': round(clip['source_in'] + seconds, 3),
                'timeline_start': round(clip['timeline_start'], 3),
                'timeline_end': round(clip['timeline_start'] + seconds, 3)
            })
            continue

        command = ['ffmpeg', '-hide_banner', '-ss', str(clip['source_in']), '-t', str(seconds), '-i', str(source),
                   '-vf', f"select='gt(scene,{scene_threshold})',showinfo", '-an', '-f', 'null', '-']
        if a.get('metadata', {}).get('has_audio'):
            command[command.index('-an'):command.index('-an')+1] = ['-af', 'silencedetect=noise=-35dB:d=0.45']
        
        result = subprocess.run(command, capture_output=True, text=True, timeout=120)
        if result.returncode:
            raise RuntimeError('Không phân tích được video: ' + result.stderr[-1000:])

        scenes = []
        for t in re.findall(r'pts_time:([\d.]+)', result.stderr)[:60]:
            offset = float(t)
            scenes.append({
                'source_time': round(clip['source_in'] + offset, 3),
                'timeline_time': round(clip['timeline_start'] + offset, 3)
            })

        silence = []
        for kind, t in re.findall(r'silence_(start|end): ([\d.]+)', result.stderr)[:120]:
            offset = float(t)
            silence.append({
                'kind': kind,
                'source_time': round(clip['source_in'] + offset, 3),
                'timeline_time': round(clip['timeline_start'] + offset, 3)
            })

        cues.append({
            'clip': index,
            'source_start': round(clip['source_in'], 3),
            'source_end': round(clip['source_in'] + seconds, 3),
            'timeline_start': round(clip['timeline_start'], 3),
            'timeline_end': round(clip['timeline_start'] + seconds, 3),
            'scene_changes': scenes,
            'silence': silence
        })
        analysed_ranges.append({
            'clip': index,
            'source_start': round(clip['source_in'], 3),
            'source_end': round(clip['source_in'] + seconds, 3),
            'timeline_start': round(clip['timeline_start'], 3),
            'timeline_end': round(clip['timeline_start'] + seconds, 3)
        })

    # Sample video frames uniformly across analysed duration if vision is enabled and supported
    if vision_used and analysed_ranges:
        total_analysed = sum(r['timeline_end'] - r['timeline_start'] for r in analysed_ranges)
        if total_analysed > 0:
            target_count = min(max_frames, max(1, int(total_analysed / 4)))
            target_times = [(k + 0.5) * total_analysed / target_count for k in range(target_count)]
            for k, target_t in enumerate(target_times):
                cancelled(event)
                acc = 0.0
                for index, clip in enumerate(plan.get('video_clips', [])):
                    dur = min(max_seconds, clip['duration'])
                    if acc <= target_t <= acc + dur or index == len(plan['video_clips']) - 1:
                        offset = min(dur, max(0.0, target_t - acc))
                        source_time = clip['source_in'] + offset
                        timeline_time = clip['timeline_start'] + offset
                        a = assets.get(clip['asset_id'], {})
                        filename = a.get('filename')
                        source = asset_dir / filename if filename else None
                        if source and source.is_file():
                            frame_path = work / f'frame-{index}-{k}.jpg'
                            try:
                                subprocess.run(['ffmpeg', '-v', 'error', '-y', '-ss', str(source_time),
                                                '-i', str(source), '-frames:v', '1', '-vf', 'scale=384:-2', str(frame_path)],
                                               check=True, capture_output=True, timeout=15)
                                if frame_path.is_file():
                                    data = base64.b64encode(frame_path.read_bytes()).decode('ascii')
                                    frames.append({
                                        'data': data,
                                        'source_time': round(source_time, 3),
                                        'timeline_time': round(timeline_time, 3),
                                        'clip_index': index
                                    })
                            finally:
                                frame_path.unlink(missing_ok=True)
                        break
                    acc += dur

    diagnostics = {
        'vision_requested': vision_requested,
        'vision_used': vision_used,
        'model': current_model,
        'sampled_frame_count': len(frames),
        'analysed_ranges': analysed_ranges,
        'scene_cue_count': sum(len(c.get('scene_changes', [])) for c in cues),
        'silence_cue_count': sum(len(c.get('silence', [])) for c in cues),
        'cache_hit': False,
        'warnings': warnings,
    }

    _ANALYSIS_MEMORY_CACHE[cache_key] = {
        'cues': cues,
        'frames': frames,
        'diagnostics': diagnostics
    }

    return AnalysisResult(cues, frames, diagnostics)


SYSTEM = '''You are an expert, highly creative Vietnamese video editor specializing in viral Reels/TikTok videos.
Return ONLY the required JSON edit decision schema. Make the video highly engaging, dynamic, and punchy.

EFFECT REGISTRY:
1. `titles` (Text Overlay): Short punchy text (2-5 words). DO NOT overlap titles (they will collide).
2. `zooms` (Keyframe): Scale up video (1.0 to 1.2x) to punch-in on key moments.
3. `illustrations` (PIP/Full Overlay): Add B-roll images/videos. `mode` can be `pip` (picture-in-picture) or `full`.
4. `sounds` (Audio Track): Supported kinds: `whoosh` (for fast transitions/zooms), `impact` (for heavy titles), `chime` (for positive/insightful moments). Max 4 seconds. Max volume 2.0.

RULES:
- All cuts.start/end refer to the INPUT timeline. Cuts are kept ranges IN OUTPUT ORDER. Keep sentences coherent.
- Every effect (titles, zooms, illustrations, sounds) start/duration refers to the FINAL OUTPUT timeline (AFTER cuts).
- Use only given asset IDs for illustrations.
- Never invent spoken words, facts, or assets. Titles MUST paraphrase the transcript.
- Never infer or hallucinate prices, addresses, personal identities, legal terms, or business claims from video frames or uncertain visuals.
- Music is available only when a music_asset_id is supplied. Source captions are remapped automatically (don't output them).
- summary and warnings must be in Vietnamese.
- For explainer_ref, return a semantic storyboard covering the ENTIRE output timeline without gaps or overlap. Every scene needs timeline_start and explicit duration. Choose camera, graphics, comparisons or steps from meaning, not a fixed alternating schedule. Keep titles short and faithful to speech. A comparison needs comparison_left and comparison_right (title, badge, points). Never reuse businesses, statistics, phone numbers or CTA from a reference.
- APPROVED STYLE: vertical 9:16; white explainer cards; teal/navy pills; Barlow Condensed bold headings; Inter captions; preserve the speaker's voice. Use a short scene headline/badge on camera (above the face), then well-paced explainer cutaways. Do not cover every sentence with graphics. Pick scene boundaries from speech, normally 3-8 seconds. End on camera unless speech contains a real CTA.
- Use graphic_kind=chat for assistants/conversation, process for a sequence of up to 3 ideas, network for distribution/connections; graphic_title and graphic_items must paraphrase the current speech. These are conceptual illustrations, not real product screenshots. Use visual_asset_id only for supplied image/video assets. broll requires visual_asset_id. Do not add unrelated app icons or invent performance metrics.
- For explainer_ref, put camera titles in scene.headline/badge_text; do not duplicate them in titles. Supported scene animations: pop_in, slide_up, fade, with fade/none on exit. Respect requests for no zoom, no SFX, or a minimal edit.
'''


class AIError(RuntimeError):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


_AI_SESSION = ContextVar('video_ai_session', default=None)
_AI_LOG = logging.getLogger('uvicorn.error')


def ai_seconds(name, default):
    value = float(os.getenv(name, str(default)))
    if not math.isfinite(value) or value <= 0:
        raise ValueError(name + ' phải là số giây lớn hơn 0.')
    return value


@contextmanager
def ai_session(event, timeout=None):
    """One planning deadline across all repairs, scoped to this worker/job."""
    current = _AI_SESSION.get()
    if current is not None:
        yield current
        return
    started = time.monotonic()
    budget = ai_seconds('VIDEO_AI_PLANNING_TIMEOUT', 600)
    if timeout is not None:
        budget=min(budget,timeout)
    session = {'started': started, 'deadline': started + budget, 'requests': []}
    token = _AI_SESSION.set(session)
    try:
        yield session
        cancelled(event)
        if time.monotonic() >= session['deadline']:
            raise AIError('AI_TIMEOUT', 'AI đã hết tổng thời gian lập kế hoạch, bao gồm kiểm tra và tự sửa. Chưa render video.')
    finally:
        event.ai_diagnostics = {'elapsed_seconds': round(time.monotonic()-started, 3), 'requests': session['requests']}
        _AI_SESSION.reset(token)


def chat(messages, event, schema=None):
    # Preserve the existing synchronous director API; network waiting itself
    # is cancellable asyncio I/O, not a background thread left generating.
    cancelled(event)
    with ai_session(event) as session:
        return asyncio.run(_chat_stream(messages, event, schema, session))


async def _chat_stream(messages, event, schema, session):
    started = time.monotonic()
    deadline = min(session['deadline'], started + ai_seconds('VIDEO_AI_REQUEST_TIMEOUT', 600))
    if started >= deadline:
        raise AIError('AI_TIMEOUT', 'AI đã hết thời gian lập kế hoạch, bao gồm các lần tự sửa. Video gốc vẫn được giữ.')
    count = (schema or {}).get('properties', {}).get('scenes', {}).get('maxItems', 0)
    predicted_limit = max(2048, 768 + int(count)*512) if schema else 8192
    output_limit = int(os.getenv('VIDEO_AI_MAX_TOKENS', str(min(16384, predicted_limit))))
    if output_limit <= 0:
        raise ValueError('VIDEO_AI_MAX_TOKENS phải lớn hơn 0.')
    payload = {'model': model_name(), 'messages': messages, 'format': schema or Direction.model_json_schema(),
               'stream': True, 'options': {'temperature': .35, 'num_ctx': 8192 if schema else 16384, 'num_predict': output_limit},
               'think': os.getenv('VIDEO_AI_THINK', '0') == '1'}
    record = {'model': payload['model'], 'think': payload['think'], **payload['options'],
              'request_index': len(session['requests'])+1,
              'input_characters': sum(len(str(m.get('content',''))) for m in messages), 'status': 'running'}
    session['requests'].append(record)
    _AI_LOG.info('video_ai_request %s', json.dumps(record, ensure_ascii=False))
    parts = []
    async def consume():
        timeout = httpx.Timeout(ai_seconds('VIDEO_AI_READ_TIMEOUT', 300), connect=10)
        async with httpx.AsyncClient(timeout=timeout, trust_env=False) as client:
            async with client.stream('POST', base_url()+'/api/chat', json=payload) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line:
                        continue
                    record.setdefault('first_chunk_seconds', round(time.monotonic()-started, 3))
                    chunk = json.loads(line)
                    if chunk.get('error'):
                        err_str = str(chunk['error'])
                        if any(phrase in err_str.lower() for phrase in ('not found', 'pull model', 'does not exist', 'unknown model')):
                            raise AIError('MODEL_MISSING', f"Model '{model_name()}' chưa có trong Ollama: {err_str}")
                        raise AIError('AI_MODEL_ERROR', 'Ollama: '+err_str)
                    parts.append(chunk.get('message', {}).get('content', ''))
                    if sum(map(len, parts)) > 150000:
                        raise AIError('CONTEXT_LIMIT', 'Phản hồi AI quá lớn; đã dừng để giữ tác vụ trong giới hạn.')
                    if chunk.get('done'):
                        for key in ('load_duration','prompt_eval_duration','eval_duration','total_duration','prompt_eval_count','eval_count','done_reason'):
                            if key in chunk:
                                record[key] = chunk[key]
                        if chunk.get('done_reason') == 'length':
                            raise AIError('AI_OUTPUT_LIMIT', 'AI đã hết giới hạn token trước khi hoàn tất kế hoạch. Chưa render video từ phản hồi bị cụt.')
                        return ''.join(parts)
                raise AIError('AI_STREAM_INCOMPLETE', 'Kết nối AI kết thúc trước khi hoàn tất kế hoạch. Hãy thử lại.')
    task = asyncio.create_task(consume())
    try:
        while True:
            cancelled(event)
            remaining = deadline-time.monotonic()
            if remaining <= 0:
                raise AIError('AI_TIMEOUT', 'AI mất quá nhiều thời gian để lập kế hoạch. Đã dừng request; đây không phải lỗi thiếu thành phần.')
            done, _ = await asyncio.wait({task}, timeout=min(.05, remaining))
            if done:
                result = task.result()
                cancelled(event)
                record['status'] = 'succeeded'
                return result
    except httpx.TimeoutException as exc:
        code = 'AI_IDLE_TIMEOUT' if isinstance(exc, httpx.ReadTimeout) else 'AI_TIMEOUT'
        raise AIError(code, 'Kết nối AI quá thời gian chờ dữ liệu. Kiểm tra Ollama và tài nguyên máy; không có video kết quả mới.') from exc
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 404:
            raise AIError('MODEL_MISSING', f"Model '{model_name()}' chưa có trong Ollama (HTTP 404); hãy chạy ollama pull {model_name()}") from exc
        raise AIError('AI_CONNECTION', f"Không gọi được Ollama/model {model_name()}; kiểm tra OLLAMA_URL và trạng thái Ollama. {exc}") from exc
    except httpx.HTTPError as exc:
        raise AIError('AI_CONNECTION', f'Không gọi được Ollama/model {model_name()}; kiểm tra OLLAMA_URL và trạng thái Ollama. {exc}') from exc
    except json.JSONDecodeError as exc:
        raise AIError('AI_STREAM_INVALID', 'Ollama trả stream không hợp lệ; chưa tạo bản dựng.') from exc
    finally:
        if not task.done():
            task.cancel()
        # Await cleanup before releasing the worker or starting another call.
        with suppress(asyncio.CancelledError, Exception):
            await task
        if record['status'] == 'running':
            record['status'] = 'cancelled' if event.is_set() else 'failed'
        record['elapsed_seconds'] = round(time.monotonic()-started, 3)
        record['output_characters'] = sum(map(len, parts))
        _AI_LOG.info('video_ai_result %s', json.dumps(record, ensure_ascii=False))


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
    for t in direction.titles:
        if t.start + t.duration > out_len + 0.05:
            raise ValueError('AI đặt tiêu đề chữ vượt quá thời lượng video.')
    for s in direction.sounds:
        if s.duration > 4.0:
            raise ValueError('Âm thanh hiệu ứng không được dài quá 4 giây.')
        if s.start + s.duration > out_len + 0.05:
            raise ValueError('AI đặt âm thanh vượt quá thời lượng video.')
    for z in direction.zooms:
        if z.start + z.duration > out_len + 0.05:
            raise ValueError('AI đặt hiệu ứng zoom vượt quá thời lượng video.')
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

    # Build semantic storyboard matching the reference video style
    if direction.storyboard:
        p['storyboard'] = [sc.model_dump() if hasattr(sc, 'model_dump') else dict(sc) for sc in direction.storyboard]
    else:
        p['storyboard'] = build_semantic_storyboard(p, direction)

    p['director'] = {'engine': 'ollama', 'model': model_name(), 'summary': direction.summary,
                     'warnings': direction.warnings}
    return validate(p, plan['assets'])


def build_semantic_storyboard(plan, direction=None, headline=''):
    """Build a structured storyboard by speech meaning, matching the reference video style."""
    clips = plan.get('video_clips', [])
    subs = mapped_subtitles(plan)
    if not clips:
        return []

    total = length(plan)
    scenes = []
    cursor = 0.0
    sub_idx = 0
    num_subs = len(subs)
    scene_count = 0

    while cursor < total - 0.25:
        scene_start = cursor
        target_end = min(total, scene_start + 4.5)

        scene_subs = []
        while sub_idx < num_subs and subs[sub_idx]['start'] < target_end + 0.8:
            scene_subs.append(subs[sub_idx])
            target_end = subs[sub_idx]['end']
            sub_idx += 1
            if target_end - scene_start >= 3.2:
                break

        # If remaining time until total is small (< 1.5s), merge into current scene
        if total - target_end < 1.5:
            target_end = total

        target_end = min(total, max(scene_start + 0.4, target_end))
        duration = target_end - scene_start

        src_in = 0.0
        for c in clips:
            if c['timeline_start'] <= scene_start < c['timeline_start'] + c['duration']:
                src_in = c['source_in'] + (scene_start - c['timeline_start'])
                break
        src_out = src_in + duration

        text = ' '.join(s['text'] for s in scene_subs).strip()
        norm_text = text.lower()

        scene_type = 'talking_head'
        badge_text = ''
        badge_color = 'teal'
        headline = ''
        subheadline = ''
        stat_num = ''
        stat_label = ''
        sound_fx = 'pop'
        steps = []
        badges = []

        # Check for Ending CTA (last 3-5 seconds of video)
        if any(k in norm_text for k in ('lưu video', 'theo dõi', 'đăng ký kênh')):
            scene_type = 'cta'
            headline = ' '.join(text.split()[:7]).upper()
            subheadline = ''
            badge_text = 'LƯU Ý QUAN TRỌNG'
            badge_color = 'navy'
            sound_fx = 'chime'
        # Check for Number / Statistics (e.g. 90%, 30 ngày, 2 triệu, x10)
        elif re.search(r'(\d+[\s]*(%|phần trăm|ngày|triệu|k|lần|x|gấp))', norm_text):
            match = re.search(r'(\d+[\s]*(%|phần trăm|ngày|triệu|k|lần|x|gấp))', norm_text)
            scene_type = 'statistic'
            stat_num = match.group(1).upper()
            stat_label = text[:40].upper() if text else 'SỐ LIỆU ĐÁNG CHÚ Ý'
            badge_text = 'SỐ LIỆU QUAN TRỌNG'
            badge_color = 'teal'
            sound_fx = 'impact'
        # Check for Comparison
        elif any(k in norm_text for k in ('so sánh', 'nội sàn', 'ngoại sàn', 'thay vì', 'hai phần', 'khác nhau', 'hai bên')):
            scene_type = 'explainer_card'
            headline = ' '.join(text.split()[:7]).upper()
            subheadline = text[:100]
            badge_text = 'PHÂN TÍCH'
            badge_color = 'navy'
            sound_fx = 'whoosh'
        # Check for Steps / Process
        elif any(k in norm_text for k in ('bước', 'thứ nhất', 'thứ hai', 'quy trình', 'muốn bền', 'lưu ý trước')):
            scene_type = 'step_list'
            headline = 'Ý CHÍNH CẦN NẮM'
            steps = [s['text'][:100] for s in scene_subs[:3]]
            badge_text = 'CÁC BƯỚC'
            badge_color = 'teal'
            sound_fx = 'click'
        # Alternating rhythm: Explainer card vs Talking head
        elif any(k in norm_text for k in ('trợ lý', 'thương hiệu', 'thông điệp', 'giải pháp', 'ví dụ')):
            scene_type = 'explainer_card'
            headline = ' '.join(text.split()[:7]).upper() if text else 'Ý CHÍNH CẦN NẮM'
            badge_text = 'Ý CHÍNH'
            badge_color = 'teal'
            badges = []
            sound_fx = 'pop'
        else:
            scene_type = 'talking_head'
            badge_text = 'NỘI SÀN' if 'nội sàn' in norm_text else 'NGOẠI SÀN' if 'ngoại sàn' in norm_text else ''
            badge_color = 'teal'
            sound_fx = 'none'

        scenes.append({
            'scene_id': f'scene_{scene_count+1}',
            'source_in': round(src_in, 2),
            'source_out': round(src_out, 2),
            'timeline_start': round(scene_start, 2),
            'duration': round(duration, 2),
            'transcript_meaning': text or 'Nội dung chia sẻ của người nói',
            'scene_type': scene_type,
            'headline': headline,
            'subheadline': subheadline,
            'badge_text': badge_text,
            'badge_color': badge_color,
            'stat_number': stat_num,
            'stat_label': stat_label,
            'steps': steps,
            'badges': badges,
            'asset_query': text[:100],
            'sound_effect': sound_fx,
            'animation_in': 'pop_in',
            'animation_out': 'fade',
            'layout_rationale': f'Bố cục {scene_type} được chọn theo ngữ nghĩa: "{text[:50]}"'
        })

        cursor = target_end
        scene_count += 1

    return scenes


def direct(plan, prompt, asset_dir, work, event, music_asset_id='', headline='', duration_policy='preserve', target_duration=0.0, visual_style='clean_expert'):
    analysis = analyse(plan, asset_dir, work, event)
    cues, frames = analysis
    vision_diag = getattr(analysis, 'diagnostics', {})
    
    policy_desc = ''
    if duration_policy == 'preserve':
        policy_desc = 'MUST KEEP THE ENTIRE INPUT TIMELINE, IN ORIGINAL ORDER. No cuts, no trimming silence. Use cuts=[{start:0,end:input_duration}]. Only decorate the video.'
    elif duration_policy == 'trim_silence':
        policy_desc = 'Cut ONLY silent parts/pauses. Keep all speech intact.'
    elif duration_policy == 'summarize':
        policy_desc = f'Summarize the video. Keep only the best parts. Target duration: {target_duration} seconds.'

    style_desc = ''
    if visual_style == 'dynamic_reels':
        style_desc = 'Use lots of zooms, pop-in titles, and heavy sound effects. Very fast-paced.'
    elif visual_style == 'clean_expert':
        style_desc = 'Keep it minimal, clean, professional. Use subtle zooms and gentle chimes. Minimal titles.'
    elif visual_style == 'explainer_ref':
        style_desc = 'Use a semantic storyboard: camera intercut with clean white explainer cards, teal/navy badges, motion graphics, and meaning-based SFX. Storyboard is required and must cover the final output duration exactly. Use project visuals or honest conceptual illustrations. Never insert unrelated reference content.'
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
            data = json.loads(raw)
            if not isinstance(data,dict):
                raise ValueError('Quyết định AI cần một đối tượng JSON.')
            for zoom in data.get('zooms', []):
                scale = zoom.get('scale')
                if isinstance(scale,(int,float)) and not isinstance(scale,bool) and math.isfinite(scale) and scale>1.2:
                    zoom['scale']=1.2
                    data.setdefault('warnings',[]).append('Đã giảm mức zoom AI yêu cầu về 1.2 để giữ hình rõ và đúng giới hạn renderer.')
            decision = Direction.model_validate(data)
            if visual_style == 'explainer_ref' and not decision.storyboard:
                raise ValueError('explainer_ref requires a complete semantic storyboard with explicit timing; do not substitute fixed effects.')
            result = apply_direction(plan, decision, music_asset_id)
            
            in_dur = length(plan)
            res_dur = length(result)
            if duration_policy == 'preserve':
                covered = 0.0
                for cut in decision.cuts:
                    if abs(cut.start-covered) > .02:
                        raise ValueError('preserve requires all input content in original order without gaps or duplicate ranges.')
                    covered = cut.end
                if abs(covered-in_dur) > .02:
                    raise ValueError(f'preserve requires the complete {in_dur}s timeline; do not shorten it.')

            # Từ chối mọi kế hoạch làm video dài còn khoảng 1 giây ngoài yêu cầu
            if in_dur >= 5.0 and res_dur <= 1.5 and target_duration > 1.5:
                raise ValueError(f"Kế hoạch AI bị từ chối: video xuất bị cắt còn {res_dur}s (dưới 1.5 giây ngoài yêu cầu).")

            if in_dur > 5.0:
                if duration_policy == 'preserve' and res_dur < in_dur * 0.85:
                    raise ValueError(f"CRITICAL ERROR: 'preserve' policy requires keeping the ENTIRE video. Input is {in_dur}s, but you output {res_dur}s. You MUST output cuts that cover the full {in_dur}s.")
                elif duration_policy == 'trim_silence' and res_dur < in_dur * 0.4:
                    raise ValueError(f"Error: You deleted too much content. Only cut true silence. Input is {in_dur}s, output is {res_dur}s.")
                elif duration_policy == 'summarize' and target_duration > 0:
                    if abs(res_dur - target_duration) > max(5.0, target_duration * 0.3):
                        raise ValueError(f"AI cắt video chưa khớp thời lượng mục tiêu ({res_dur}s so với mục tiêu {target_duration}s).")
            elif res_dur < 1.0 and in_dur >= 2.0:
                raise ValueError(f"Thời lượng kết quả quá ngắn ({res_dur}s).")
            
            # Kiểm tra chất lượng: Không chồng lớp chữ
            title_times = []
            for t in decision.titles:
                for start, end in title_times:
                    if not (t.start >= end or t.start + t.duration <= start):
                        raise ValueError(f"Titles overlap! '{t.text}' overlaps with another title. Prevent overlapping text.")
                title_times.append((t.start, t.start + t.duration))

            result['director']['prompt'] = prompt
            result['director']['vision_diagnostics'] = vision_diag
            for w in vision_diag.get('warnings', []):
                if w not in result['director']['warnings']:
                    result['director']['warnings'].append(w)
            if not plan.get('subtitles'):
                result['director']['warnings'].append('Không có lời thoại nhận dạng; AI chưa hiểu đầy đủ nội dung nói. Cài Whisper hoặc nhập SRT.')
            if not vision_diag.get('vision_used'):
                if not any('chưa phân tích' in w.lower() for w in result['director']['warnings']):
                    result['director']['warnings'].append('Model đang đọc lời thoại và mốc cảnh/âm thanh; chưa phân tích nội dung hình ảnh.')
            return result
        except (ValueError, KeyError, TypeError) as exc:
            if attempt:
                raise RuntimeError('AI chưa tạo được bản dựng hợp lệ sau lần sửa: ' + str(exc)) from exc
            messages += [{'role': 'assistant', 'content': raw},
                         {'role': 'user', 'content': 'Repair your JSON decision. Validation error: ' + str(exc)[:2000]}]
    raise RuntimeError('Không nhận được quyết định AI.')
