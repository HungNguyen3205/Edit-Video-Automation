"""Tests for post-render audit report, technical quality gate, low-edit warnings,
Ollama failure classification, and privacy sanitization.
"""
import copy
import json
import threading
import pytest
from test_pipeline import client, media, new_project
import main
from ai_director import AIError
from automatic_director import fallback_direction, PlanningError, automatic_direction
from editing import probe
from render_report import build_render_report, check_quality_gate, check_low_edit_density, sanitize_value


def speech_project(media):
    p = new_project(media)
    aid = p['video']['asset_id']
    words = [{'word': ' Xin', 'start': 0.2, 'end': 0.8}, {'word': ' chào.', 'start': 0.8, 'end': 1.5}]
    p['edit_plan']['subtitles'] = [{'id': 's1', 'asset_id': aid, 'start': 0.2, 'end': 1.5, 'text': 'Xin chào.', 'words': words}]
    main.save_project(p['id'], p)
    return p


def test_ai_completion_report_structure(media, monkeypatch):
    """When AI planning completes, report indicates AI completion with plan vs rendered metrics."""
    p = speech_project(media)
    monkeypatch.setattr(main, 'ai_health', lambda: {'available': True, 'model': 'mock-ai'})

    raw_ai = {
        'summary': 'Video sinh động',
        'captions': True,
        'font_style': 'auto',
        'scenes': [
            {'i': 0, 't': 'talking_head', 'h': 'MỞ ĐẦU', 'z': 1.05}
        ]
    }
    monkeypatch.setattr(main, 'automatic_direction', lambda plan, prompt, *args, **kwargs:
        fallback_direction(plan, prompt, threading.Event(), None))

    resp = client.post(f'/api/projects/{p["id"]}/make-video', json={'prompt': 'Dựng sinh động'})
    assert resp.status_code == 200
    res = client.get(f'/api/projects/{p["id"]}').json()
    assert res['job']['status'] == 'succeeded'

    report = res.get('render_report') or res['job'].get('render_report')
    assert report is not None
    assert 'plan_metrics' in report
    assert 'rendered_metrics' in report
    assert 'quality_gate' in report
    assert report['quality_gate']['passed'] is True
    assert report['rendered_metrics']['probe_verified'] is True
    assert report['rendered_metrics']['duration_seconds'] == pytest.approx(4, abs=0.1)


def test_ai_timeout_fallback_report(media, monkeypatch):
    """AI timeout produces fallback video with TIMEOUT code and 'Bản dự phòng' status."""
    p = speech_project(media)
    def timeout_error(*args, **kwargs):
        raise AIError('TIMEOUT', 'AI đã hết tổng thời gian lập kế hoạch')

    monkeypatch.setattr(main, 'automatic_direction', timeout_error)

    resp = client.post(f'/api/projects/{p["id"]}/make-video', json={'prompt': 'Dựng nhanh'})
    assert resp.status_code == 200
    res = client.get(f'/api/projects/{p["id"]}').json()
    assert res['job']['status'] == 'succeeded'
    assert res['job']['planning_mode'] == 'fallback'
    assert res['job']['fallback_reason'] == 'TIMEOUT'

    report = res.get('render_report') or res['job'].get('render_report')
    assert report is not None
    assert report['status_category'] == 'Bản dự phòng'
    assert report['status_code'] == 'fallback'
    assert 'TIMEOUT' in report['fallback_reason']
    assert report['fallback_reason_detail'] is not None


def test_model_missing_fallback(media, monkeypatch):
    """When model is missing in Ollama, error code is MODEL_MISSING."""
    p = speech_project(media)
    def missing_model(*args, **kwargs):
        raise AIError('MODEL_MISSING', "Model 'qwen2.5:7b' chưa có trong Ollama")

    monkeypatch.setattr(main, 'automatic_direction', missing_model)

    resp = client.post(f'/api/projects/{p["id"]}/make-video', json={})
    assert resp.status_code == 200
    res = client.get(f'/api/projects/{p["id"]}').json()
    assert res['job']['fallback_reason'] == 'MODEL_MISSING'
    report = res.get('render_report') or res['job'].get('render_report')
    assert 'MODEL_MISSING' in report['fallback_reason']
    assert 'chưa được tải' in report['fallback_reason_detail'] or 'chưa có' in report['fallback_reason_detail']


def test_invalid_json_repair_failure_fallback(media, monkeypatch):
    """When AI emits malformed JSON and repair fails, error code is INVALID_JSON."""
    p = speech_project(media)
    def bad_json_error(*args, **kwargs):
        raise PlanningError('AI trả dữ liệu không phải JSON hợp lệ', code='INVALID_JSON')

    monkeypatch.setattr(main, 'automatic_direction', bad_json_error)

    resp = client.post(f'/api/projects/{p["id"]}/make-video', json={})
    assert resp.status_code == 200
    res = client.get(f'/api/projects/{p["id"]}').json()
    assert res['job']['fallback_reason'] == 'INVALID_JSON'
    report = res.get('render_report') or res['job'].get('render_report')
    assert report['fallback_reason'] == 'INVALID_JSON'


def test_user_cancellation_never_renders_or_falls_back(media, monkeypatch):
    """Cancellation terminates task as cancelled; never marks as fallback success."""
    p = speech_project(media)
    def cancel_task(*args, **kwargs):
        args[4].set()  # event.set()
        raise InterruptedError('Đã hủy tác vụ.')

    monkeypatch.setattr(main, 'automatic_direction', cancel_task)
    monkeypatch.setattr(main, 'fallback_direction', lambda *args, **kwargs: pytest.fail('Must not run fallback on cancel'))

    client.post(f'/api/projects/{p["id"]}/make-video', json={})
    res = client.get(f'/api/projects/{p["id"]}').json()
    assert res['job']['status'] == 'cancelled'
    assert res['job']['status_category'] == 'Đã hủy'
    assert not res.get('output_path')


def test_renderer_failure_is_not_fallback_success(media, monkeypatch):
    """A failure during compiling or ffmpeg rendering must be marked as failed, NOT fallback success."""
    p = speech_project(media)
    def broken_ffmpeg(*args, **kwargs):
        raise RuntimeError('FFmpeg process crashed with code 1')

    monkeypatch.setattr(main, 'run_render_command', broken_ffmpeg)

    client.post(f'/api/projects/{p["id"]}/make-video', json={})
    res = client.get(f'/api/projects/{p["id"]}').json()
    assert res['job']['status'] == 'failed'
    assert res['job']['status_category'] == 'Dựng thất bại'
    assert res['job']['status_code'] == 'failed'
    assert not res.get('output_path')


def test_silent_video_quality_gate(media, monkeypatch):
    """Silent video without audio stream in source passes quality gate without audio failure."""
    p = client.post('/api/projects', data={'name': 'Silent'}).json()
    with media[1].open('rb') as f:
        p = client.post(f'/api/projects/{p["id"]}/upload', files={'file': ('silent.mp4', f)}, data={'role': 'main'}).json()

    monkeypatch.setenv('OLLAMA_URL', 'http://127.0.0.1:9')
    resp = client.post(f'/api/projects/{p["id"]}/make-video', json={'prompt': 'Giữ im lặng'})
    assert resp.status_code == 200
    res = client.get(f'/api/projects/{p["id"]}').json()
    assert res['job']['status'] == 'succeeded'
    report = res.get('render_report') or res['job'].get('render_report')
    assert report['quality_gate']['passed'] is True
    assert report['quality_gate']['checks']['audio_valid'] is True


def test_explicit_minimal_edit_no_low_edit_warning(media):
    """When user explicitly requests a minimal edit, low-edit warning is NOT triggered."""
    p = speech_project(media)
    plan = p['edit_plan']
    # Talking head only, no zooms, no sfx
    plan['storyboard'] = [{'scene_id': 's0', 'scene_type': 'talking_head', 'duration': 4.0}]
    plan['effect_keyframes'] = []

    is_low, reason = check_low_edit_density(plan, user_prompt='Yêu cầu dựng tối giản, chỉ chữ, không hiệu ứng')
    assert is_low is False
    assert reason is None


def test_low_edit_warning_when_dynamic_requested_but_minimal_output(media):
    """When user requests dynamic edit but output is camera+subtitles only, warning is flagged."""
    p = speech_project(media)
    plan = p['edit_plan']
    plan['storyboard'] = [{'scene_id': 's0', 'scene_type': 'talking_head', 'duration': 4.0}]
    plan['effect_keyframes'] = []

    is_low, reason = check_low_edit_density(plan, user_prompt='Dựng video thật sinh động, năng động, nhiều hiệu ứng')
    assert is_low is True
    assert 'Mức độ biên tập thấp' in reason


def test_privacy_sanitization_in_diagnostics():
    """Sensitive local system paths and raw base64 payloads are sanitized."""
    raw_diag = {
        'model': 'qwen2.5:7b',
        'raw_local_path': r'C:\Users\Surface\AppData\Local\Temp\my_private_video.mp4',
        'linux_path': '/home/username/secret_video.mp4',
        'frames': [
            {'time': 1.0, 'data': 'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==' * 10}
        ]
    }
    sanitized = sanitize_value(raw_diag)
    assert 'Users\\Surface' not in str(sanitized)
    assert '/home/username' not in str(sanitized)
    assert 'BASE64_PAYLOAD' in str(sanitized) or 'data' not in sanitized['frames'][0]
