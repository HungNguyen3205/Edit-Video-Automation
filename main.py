"""Local-first video studio: validated plans, offline automation, serialized workers."""
import copy
import importlib.util
import json
import os
import shutil
import subprocess
import tempfile
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

from fastapi import BackgroundTasks, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from editing import auto_plan, compile_render, mapped_subtitles, parse_srt, probe, probe_audio, srt_content, uid, validate

from ai_director import direct, ai_health

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = Path(os.getenv('VIDEO_DATA_DIR', BASE_DIR / 'data')).resolve()
PROJECTS_DIR, ASSETS_DIR, OUTPUTS_DIR = [DATA_DIR / name for name in ('projects', 'assets', 'outputs')]
for directory in (PROJECTS_DIR, ASSETS_DIR, OUTPUTS_DIR):
    directory.mkdir(parents=True, exist_ok=True)
app = FastAPI(title='DANAVA Video Studio')
app.mount('/frontend', StaticFiles(directory=BASE_DIR / 'frontend'), name='frontend')
app.mount('/assets', StaticFiles(directory=ASSETS_DIR), name='assets')
app.mount('/outputs', StaticFiles(directory=OUTPUTS_DIR), name='outputs')
LOCK = threading.RLock()
WORKER = threading.Semaphore(1)
CANCEL = {}
MODEL = None
MODEL_LOCK = threading.Lock()
MAX_UPLOAD = int(os.getenv('MAX_UPLOAD_MB', '500')) * 1024 * 1024


def stamp():
    return datetime.now(timezone.utc).isoformat()


def project_path(project_id):
    try:
        import uuid
        if str(uuid.UUID(project_id)) != project_id:
            raise ValueError()
    except (ValueError, TypeError):
        raise HTTPException(400, 'ID dự án không hợp lệ.')
    return PROJECTS_DIR / f'{project_id}.json'


def save_project(project_id, data):
    with LOCK:
        path = project_path(project_id)
        data['updated_at'] = stamp()
        temp = path.with_suffix('.tmp')
        temp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
        temp.replace(path)


def load_project(project_id):
    with LOCK:
        path = project_path(project_id)
        if not path.exists():
            raise HTTPException(404, 'Không tìm thấy dự án.')
        data = json.loads(path.read_text(encoding='utf-8'))
        if data.get('edit_plan', {}).get('schema_version', 1) < 2:
            data = migrate_legacy(data)
            save_project(project_id, data)
        return data


def patch(project_id, **changes):
    with LOCK:
        p = load_project(project_id)
        p.update(changes)
        save_project(project_id, p)


def check_plan(plan, assets):
    try:
        return validate(plan, assets)
    except (ValueError, KeyError, TypeError) as exc:
        raise HTTPException(422, str(exc)) from exc


def empty_plan():
    return {'schema_version': 2, 'assets': [], 'video_clips': [], 'audio_tracks': [], 'subtitles': [], 'text_overlays': [], 'visual_overlays': [], 'effect_keyframes': [], 'output_settings': {'width': 1280, 'height': 720, 'fps': 30, 'fit': 'contain'}}


def migrate_legacy(project):
    """Keep existing local projects from the original MVP readable."""
    plan = project['edit_plan']
    for key in ('subtitles', 'text_overlays', 'visual_overlays', 'effect_keyframes'):
        plan.setdefault(key, [])
    for asset in plan.get('assets', []):
        filename = asset.get('filename', '')
        if Path(filename).name != filename:
            raise HTTPException(422, 'Đường dẫn tài nguyên cũ không hợp lệ.')
        if 'metadata' not in asset and (ASSETS_DIR / filename).exists():
            try:
                asset['metadata'] = probe(ASSETS_DIR / filename)
            except ValueError:
                pass
        if Path(filename).suffix.lower() in ('.mp4', '.mov', '.webm', '.mkv'):
            asset['type'] = 'video'
        asset.setdefault('keywords', '')
    main = project.get('video')
    if main:
        asset = next((a for a in plan['assets'] if a['id'] == main['asset_id']), None)
        if asset and asset.get('metadata'):
            main['metadata'] = asset['metadata']
        for sub in plan['subtitles']:
            sub.setdefault('asset_id', main['asset_id'])
    settings = plan.setdefault('output_settings', {'width': 1280, 'height': 720, 'fps': 30})
    for overlay in plan['visual_overlays']:
        # Original MVP stored x/y in pixels, unlike normalized v2 geometry.
        overlay['x'] = max(0, min(1, overlay.get('x', 0) / settings['width']))
        overlay['y'] = max(0, min(1, overlay.get('y', 0) / settings['height']))
        overlay.setdefault('width', .38)
        overlay.setdefault('mode', 'pip')
        overlay.setdefault('source_in', 0)
    plan['schema_version'] = 2
    settings.setdefault('fit', 'contain')
    project.setdefault('revision', 0)
    project.setdefault('job', None)
    return project


# Interrupted jobs must not appear to run forever after a server restart.
for path in PROJECTS_DIR.glob('*.json'):
    try:
        p = json.loads(path.read_text(encoding='utf-8'))
        if p.get('job', {}).get('status') in ('queued', 'running'):
            p['job'].update(status='failed', phase='Tác vụ bị gián đoạn; hãy thử lại.', error='Ứng dụng đã khởi động lại.')
            p['export_status'] = 'failed'
            save_project(p['id'], p)
    except (ValueError, KeyError):
        pass


@app.get('/')
def root():
    return RedirectResponse('/frontend/index.html')


@app.get('/api/health')
def health():
    return {'ffmpeg': bool(shutil.which('ffmpeg')), 'ffprobe': bool(shutil.which('ffprobe')), 'whisper': importlib.util.find_spec('whisper') is not None, 'model': os.getenv('WHISPER_MODEL', 'base'), 'font_file': bool(os.getenv('VIDEO_FONT_FILE')), 'ai': ai_health()}


@app.get('/api/projects')
def projects():
    result = []
    for path in PROJECTS_DIR.glob('*.json'):
        p = load_project(path.stem)
        result.append({k: p.get(k) for k in ('id', 'name', 'updated_at', 'video', 'export_status')})
    return sorted(result, key=lambda p: p.get('updated_at') or '', reverse=True)


@app.post('/api/projects')
def create_project(name: str = Form(...)):
    p = {'id': uid(), 'name': name.strip()[:120] or 'Video mới', 'video': None, 'revision': 0, 'export_status': 'none', 'transcribe_status': 'none', 'output_path': None, 'preview_path': None, 'edit_plan': empty_plan(), 'job': None}
    save_project(p['id'], p)
    return p


@app.get('/api/projects/{project_id}')
def project(project_id: str):
    return load_project(project_id)


@app.post('/api/projects/{project_id}/upload')
def upload(project_id: str, file: UploadFile = File(...), role: str = Form('auto')):
    p = load_project(project_id)
    ext = Path(file.filename or '').suffix.lower()
    videos = {'.mp4', '.mov', '.webm', '.mkv'}
    images = {'.png', '.jpg', '.jpeg', '.webp'}
    audio = {'.mp3', '.wav', '.m4a', '.aac', '.ogg', '.flac'}
    if ext not in videos | images | audio:
        raise HTTPException(415, 'Hỗ trợ video MP4/MOV/WEBM/MKV, ảnh PNG/JPG/WEBP và nhạc MP3/WAV/M4A/AAC/OGG/FLAC.')
    if role == 'main' and (p.get('video') or ext not in videos):
        raise HTTPException(409, 'Video chính đã có hoặc file không phải video. Hãy tạo dự án mới để thay nguồn.')
    identifier = uid()
    path = ASSETS_DIR / f'{identifier}{ext}'
    try:
        size = 0
        with path.open('wb') as target:
            while chunk := file.file.read(1024 * 1024):
                size += len(chunk)
                if size > MAX_UPLOAD:
                    raise HTTPException(413, 'File vượt giới hạn dung lượng upload.')
                target.write(chunk)
        meta = probe_audio(path) if ext in audio else probe(path)
        if ext in videos and meta['duration'] <= 0:
            raise ValueError('Không xác định được thời lượng video.')
    except Exception as exc:
        path.unlink(missing_ok=True)
        if isinstance(exc, HTTPException):
            raise
        raise HTTPException(422, str(exc)) from exc
    thumbnail = None
    if ext in videos and shutil.which('ffmpeg'):
        thumb = ASSETS_DIR / f'{identifier}_thumb.jpg'
        result = subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', str(path), '-frames:v', '1', '-vf', 'scale=480:-2', str(thumb)], capture_output=True, timeout=30)
        if result.returncode == 0:
            thumbnail = thumb.name
    asset = {'thumbnail': thumbnail, 'id': identifier, 'filename': path.name, 'original_name': file.filename, 'type': 'video' if ext in videos else 'audio' if ext in audio else 'image', 'metadata': meta, 'keywords': ''}
    with LOCK:
        p = load_project(project_id)
        if role != 'asset' and not p.get('video') and ext in videos:
            p['video'] = {'asset_id': identifier, 'filename': path.name, 'original_name': file.filename, 'metadata': meta, 'thumbnail': thumbnail}
            p['edit_plan']['video_clips'] = [{'id': uid(), 'asset_id': identifier, 'source_in': 0, 'source_out': meta['duration'], 'duration': meta['duration'], 'timeline_start': 0}]
            # Default preserves aspect, caps 1080, never upscales.
            ratio = min(1, 1080 / max(meta['width'], meta['height']))
            p['edit_plan']['output_settings'].update(width=max(120, int(meta['width']*ratio)//2*2), height=max(120, int(meta['height']*ratio)//2*2))
        p['edit_plan']['assets'].append(asset)
        p['revision'] = p.get('revision', 0) + 1
        save_project(project_id, p)
    return p


@app.post('/api/projects/{project_id}/edit_plan')
def save_plan(project_id: str, body: dict):
    with LOCK:
        p = load_project(project_id)
        # Revision check prevents silent overwrites from stale editors.
        if 'plan' in body:
            if body.get('revision') != p.get('revision', 0):
                raise HTTPException(409, 'Dự án đã thay đổi. Hãy tải lại trước khi lưu.')
            plan = body['plan']
        else:
            plan = body  # compatibility with original API
        trusted = p['edit_plan']['assets']
        incoming = {a.get('id'): a for a in plan.get('assets', [])}
        trusted = [{**a, 'keywords': str(incoming.get(a['id'], {}).get('keywords', a.get('keywords', '')))[:300]} for a in trusted]
        # Trimming invalidates generated timing; clamp/remove generated items only.
        if plan.get('video_clips') != p['edit_plan'].get('video_clips'):
            total = sum(float(c.get('duration', 0)) for c in plan.get('video_clips', []))
            plan = copy.deepcopy(plan)
            for key in ('effect_keyframes', 'text_overlays', 'visual_overlays', 'audio_tracks'):
                kept = []
                for item in plan.get(key, []):
                    if item.get('origin') == 'auto':
                        if item.get('timeline_start', 0) >= total - .04:
                            continue
                        item['duration'] = min(item['duration'], total - item['timeline_start'])
                    kept.append(item)
                plan[key] = kept
        p['edit_plan'] = check_plan(plan, trusted)
        p['revision'] = p.get('revision', 0) + 1
        save_project(project_id, p)
    return p


@app.post('/api/projects/{project_id}/subtitles/import')
def import_subtitles(project_id: str, file: UploadFile = File(...)):
    content = file.file.read(2 * 1024 * 1024 + 1)
    if len(content) > 2 * 1024 * 1024:
        raise HTTPException(413, 'SRT quá lớn.')
    with LOCK:
        p = load_project(project_id)
        if not p.get('video'):
            raise HTTPException(400, 'Tải video chính trước.')
        try:
            subs = parse_srt(content.decode('utf-8-sig'), p['video']['asset_id'])
        except (UnicodeError, ValueError) as exc:
            raise HTTPException(422, str(exc)) from exc
        plan = copy.deepcopy(p['edit_plan'])
        plan['subtitles'] = subs
        p['edit_plan'] = check_plan(plan, plan['assets'])
        p['revision'] = p.get('revision', 0) + 1
        p['transcribe_status'] = 'succeeded'
        save_project(project_id, p)
    return p


@app.get('/api/projects/{project_id}/subtitles.srt')
def download_srt(project_id: str):
    p = load_project(project_id)
    return Response(srt_content(mapped_subtitles(p['edit_plan'])), media_type='text/plain; charset=utf-8', headers={'Content-Disposition': 'attachment; filename="captions.srt"'})


class Options(BaseModel):
    prompt: str = Field('', max_length=4000)
    planner: str = Field('rules', pattern='^(rules|ai)$')
    music_asset_id: str = Field('', max_length=100)
    intensity: str = 'balanced'
    headline: str = Field('', max_length=120)
    transcribe: bool = True
    preview: bool = False


def job_update(project_id, **changes):
    with LOCK:
        p = load_project(project_id)
        p['job'].update(changes)
        save_project(project_id, p)


def transcribe(plan, work_dir, project_id):
    global MODEL
    if importlib.util.find_spec('whisper') is None:
        raise RuntimeError('Chưa cài Whisper. Cài requirements-ai.txt hoặc nhập SRT; có thể tắt phụ đề tự động để dựng hình trước.')
    asset = next(a for a in plan['assets'] if a['id'] == plan['video_clips'][0]['asset_id'])
    if not asset['metadata'].get('has_audio'):
        raise RuntimeError('Video không có tiếng để nhận dạng. Tắt phụ đề tự động hoặc nhập SRT.')
    audio = work_dir / 'audio.wav'
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', str(ASSETS_DIR / asset['filename']), '-vn', '-ar', '16000', '-ac', '1', str(audio)], check=True, capture_output=True)
    job_update(project_id, phase='Đang tải model/nhận dạng tiếng Việt trên CPU…')
    import whisper
    with MODEL_LOCK:
        if MODEL is None:
            MODEL = whisper.load_model(os.getenv('WHISPER_MODEL', 'base'), device='cpu')
    result = MODEL.transcribe(str(audio), language='vi', fp16=False)
    return [{'id': uid(), 'asset_id': asset['id'], 'start': float(s['start']), 'end': float(s['end']), 'text': s['text'].strip()} for s in result['segments'] if s['text'].strip() and s['end'] > s['start']]


def run_job(project_id, job_id, snapshot, options, mode):
    event = CANCEL[job_id]
    try:
        with WORKER:
            if event.is_set():
                raise InterruptedError('Đã hủy tác vụ.')
            job_update(project_id, status='running', phase='Chuẩn bị bản dựng', progress=None)
            with tempfile.TemporaryDirectory(prefix='render-', dir=OUTPUTS_DIR) as temporary:
                work = Path(temporary)
                plan = snapshot['edit_plan']
                warnings = []
                if mode in ('auto', 'transcribe'):
                    if mode == 'transcribe' or (options.transcribe and not plan.get('subtitles')):
                        plan['subtitles'] = transcribe(plan, work, project_id)
                    if event.is_set():
                        raise InterruptedError('Đã hủy tác vụ.')
                    if mode == 'auto':
                        if options.planner == 'ai':
                            job_update(project_id, phase='AI đang phân tích nội dung và lập kế hoạch theo prompt…')
                            plan = direct(plan, options.prompt, ASSETS_DIR, work, event, options.music_asset_id, options.headline)
                            warnings.extend(plan['director']['warnings'])
                        else:
                            job_update(project_id, phase='Tạo nhịp zoom, chữ và minh họa theo quy tắc')
                            plan = auto_plan(plan, options.intensity, options.headline)
                        if options.planner != 'ai' and not plan['subtitles']:
                            warnings.append('Chưa có phụ đề: bản dựng dùng nhịp theo thời gian, chưa ghép minh họa theo lời nói.')
                    with LOCK:
                        latest = load_project(project_id)
                        if latest.get('revision', 0) != snapshot.get('revision', 0):
                            raise RuntimeError('Bạn đã sửa dự án trong lúc phân tích. Hãy chạy lại để giữ chỉnh sửa mới.')
                        plan = check_plan(plan, latest['edit_plan']['assets'])
                        latest['edit_plan'] = plan
                        latest['revision'] = latest.get('revision', 0) + 1
                        snapshot['revision'] = latest['revision']
                        latest['transcribe_status'] = 'succeeded' if plan['subtitles'] else 'none'
                        save_project(project_id, latest)
                    if mode == 'transcribe':
                        job_update(project_id, status='succeeded', phase='Phụ đề sẵn sàng để chỉnh', progress=100)
                        return
                if event.is_set():
                    raise InterruptedError('Đã hủy tác vụ.')
                filename = f'{project_id}_{job_id}.mp4'
                output = OUTPUTS_DIR / filename
                cmd, duration = compile_render(plan, ASSETS_DIR, work, output, options.preview)
                job_update(project_id, phase='Đang render bản xem thử' if options.preview else 'Đang render MP4', progress=0, warnings=warnings)
                log_path = work / 'ffmpeg.log'
                with log_path.open('w+', encoding='utf-8') as log:
                    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=log, text=True)
                    def stop_when_cancelled():
                        while process.poll() is None:
                            if event.wait(.2):
                                process.terminate()
                                try:
                                    process.wait(timeout=3)
                                except subprocess.TimeoutExpired:
                                    process.kill()
                                return
                    watcher = threading.Thread(target=stop_when_cancelled, daemon=True)
                    watcher.start()
                    last = 0
                    for line in process.stdout:
                        if line.startswith('out_time_us=') and time.monotonic() - last > .4:
                            try:
                                progress = min(99, max(0, int(float(line.split('=')[1]) / 1000000 / duration * 100)))
                                job_update(project_id, progress=progress)
                                last = time.monotonic()
                            except ValueError:
                                pass
                    process.wait()
                    watcher.join(timeout=4)
                    if event.is_set():
                        output.unlink(missing_ok=True)
                        raise InterruptedError('Đã hủy tác vụ.')
                    if process.returncode:
                        log.seek(0)
                        details = log.read()[-6000:]
                        output.unlink(missing_ok=True)
                        raise RuntimeError('FFmpeg không xuất được video: ' + details)
                meta = probe(output)
                if abs(meta['duration'] - duration) > .2:
                    output.unlink(missing_ok=True)
                    raise RuntimeError('Thời lượng kết quả không đúng bản dựng.')
                with LOCK:
                    latest = load_project(project_id)
                    field = 'preview_path' if options.preview else 'output_path'
                    latest[field] = '/outputs/' + filename
                    latest['preview_revision' if options.preview else 'output_revision'] = snapshot['revision']
                    latest['export_status'] = 'succeeded'
                    latest['job'].update(status='succeeded', phase='Bản xem thử đã sẵn sàng' if options.preview else 'Video hoàn chỉnh đã sẵn sàng', progress=100, warnings=warnings)
                    save_project(project_id, latest)
    except Exception as exc:
        cancelled = isinstance(exc, InterruptedError)
        job_update(project_id, status='cancelled' if cancelled else 'failed', phase='Đã hủy' if cancelled else 'Cần xử lý lỗi', error=str(exc))
        patch(project_id, export_status='cancelled' if cancelled else 'failed', transcribe_status='failed' if mode == 'transcribe' else load_project(project_id).get('transcribe_status', 'none'))
    finally:
        CANCEL.pop(job_id, None)


def enqueue(project_id, background_tasks, options, mode):
    if not shutil.which('ffmpeg') or not shutil.which('ffprobe'):
        raise HTTPException(503, 'Cài FFmpeg và FFprobe vào PATH trước khi dựng.')
    if mode == 'auto' and options.planner == 'ai':
        if not options.prompt.strip():
            raise HTTPException(422, 'Nhập yêu cầu dựng video cho AI.')
        ai = ai_health()
        if not ai['available']:
            raise HTTPException(422, 'Chưa có Ollama/model. Cài Ollama và chạy ollama pull ' + ai['model'])
    with LOCK:
        p = load_project(project_id)
        if options.music_asset_id and not any(a['id'] == options.music_asset_id and a['type'] == 'audio' for a in p['edit_plan']['assets']):
            raise HTTPException(422, 'Chọn file nhạc nền thuộc dự án.')
        if p.get('job') and p['job']['status'] in ('queued', 'running'):
            raise HTTPException(409, 'Dự án đang có tác vụ; hãy đợi hoặc hủy.')
        p['edit_plan'] = check_plan(p['edit_plan'], p['edit_plan']['assets'])
        if mode in ('auto', 'transcribe') and (mode == 'transcribe' or options.transcribe) and not p['edit_plan']['subtitles']:
            if importlib.util.find_spec('whisper') is None:
                raise HTTPException(422, 'Chưa cài Whisper. Cài requirements-ai.txt, nhập SRT hoặc tắt phụ đề tự động.')
        identifier = uid()
        p['job'] = {'id': identifier, 'status': 'queued', 'phase': 'Đang chờ worker', 'progress': None, 'error': None, 'warnings': [], 'mode': mode, 'preview': options.preview}
        p['export_status'] = 'queued'
        if mode == 'transcribe':
            p['transcribe_status'] = 'running'
        save_project(project_id, p)
        CANCEL[identifier] = threading.Event()
        snapshot = copy.deepcopy(p)
    background_tasks.add_task(run_job, project_id, identifier, snapshot, options, mode)
    return p


@app.post('/api/projects/{project_id}/auto-edit')
def automate(project_id: str, options: Options, background_tasks: BackgroundTasks):
    return enqueue(project_id, background_tasks, options, 'auto')


@app.post('/api/projects/{project_id}/export')
def export(project_id: str, background_tasks: BackgroundTasks, options: Options = Options()):
    return enqueue(project_id, background_tasks, options, 'render')


@app.post('/api/projects/{project_id}/transcribe')
def recognize(project_id: str, background_tasks: BackgroundTasks):
    return enqueue(project_id, background_tasks, Options(), 'transcribe')


@app.post('/api/projects/{project_id}/cancel')
def cancel(project_id: str):
    p = load_project(project_id)
    event = CANCEL.get((p.get('job') or {}).get('id'))
    if event:
        event.set()
    return {'status': 'requested', 'note': 'Nhận dạng đang chạy sẽ dừng ở bước kế tiếp; render được dừng trực tiếp.'}


@app.get('/api/projects/{project_id}/status')
def status(project_id: str):
    p = load_project(project_id)
    return {'status': p.get('export_status'), 'transcribe_status': p.get('transcribe_status'), 'job': p.get('job')}


if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host='127.0.0.1', port=8000)
