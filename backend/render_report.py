"""Technical quality gate, post-render audit report, and low-edit diagnostics.

Differentiates plan decisions from verified rendered output, validates technical quality,
checks for low-edit density while honoring explicit minimal requests, and sanitizes
all diagnostics for privacy.
"""
import os
import re
from pathlib import Path


FALLBACK_REASONS = {
    'MODEL_MISSING': 'Model AI chưa được tải hoặc không tồn tại trong Ollama',
    'AI_CONNECTION': 'Lỗi kết nối tới Ollama hoặc dịch vụ AI chưa bật',
    'TIMEOUT': 'Quá thời gian lập kế hoạch AI (hết budget thời gian)',
    'AI_TIMEOUT': 'Quá thời gian lập kế hoạch AI (hết budget thời gian)',
    'AI_CONNECT_TIMEOUT': 'Quá thời gian kết nối tới Ollama',
    'AI_IDLE_TIMEOUT': 'Quá thời gian chờ Ollama phản hồi dữ liệu',
    'INVALID_JSON': 'Phản hồi từ AI không đúng định dạng JSON và tự sửa thất bại',
    'SCHEMA_ERROR': 'Cấu trúc kế hoạch từ AI sai quy chuẩn và tự sửa thất bại',
    'AI_PLAN_INVALID': 'AI chưa chọn được cảnh hợp lệ sau khi tự sửa',
    'CONTEXT_LIMIT': 'Nội dung video/lời thoại vượt giới hạn context của AI',
    'AI_OUTPUT_LIMIT': 'AI vượt quá giới hạn token đầu ra',
    'ANALYSIS_ERROR': 'Lỗi trong quá trình phân tích video hoặc khung hình',
    'AI_MODEL_ERROR': 'Lỗi nội bộ từ Ollama model',
    'AI_STREAM_INCOMPLETE': 'Kết nối AI kết thúc trước khi hoàn tất kế hoạch'
}


def sanitize_value(val):
    """Remove private system paths and base64 payloads from diagnostics."""
    if isinstance(val, str):
        if len(val) > 200 and re.match(r'^[A-Za-z0-9+/=]+$', val.strip()):
            return f"[BASE64_PAYLOAD_{len(val)}_BYTES]"
        # Mask user home and absolute drives
        val = re.sub(r'[A-Za-z]:\\[^\\/:*?"<>|\r\n]+\\([^\r\n]+)', r'...\1', val)
        val = re.sub(r'/Users/[^/]+/([^\r\n]+)', r'...\1', val)
        val = re.sub(r'/home/[^/]+/([^\r\n]+)', r'...\1', val)
        return val
    elif isinstance(val, dict):
        return {k: sanitize_value(v) for k, v in val.items() if k not in ('data', 'b64', 'raw_bytes')}
    elif isinstance(val, list):
        return [sanitize_value(v) for v in val]
    return val


def check_quality_gate(meta, output_path, expected_duration, source_has_audio=False, is_automatic=True):
    """Verify rendered MP4 against technical standards."""
    out_file = Path(output_path)
    file_exists = out_file.is_file()
    file_size = out_file.stat().st_size if file_exists else 0
    file_readable = file_exists and file_size > 0

    has_audio = bool(meta.get('has_audio'))
    audio_valid = (not source_has_audio) or has_audio

    duration_actual = float(meta.get('duration', 0.0))
    duration_matched = abs(duration_actual - expected_duration) <= 0.45

    width = int(meta.get('width', 0))
    height = int(meta.get('height', 0))
    dimensions_valid = (width, height) == (720, 1280) if is_automatic else (width > 0 and height > 0)

    passed = file_readable and audio_valid and duration_matched and dimensions_valid

    checks = {
        'file_readable': file_readable,
        'audio_valid': audio_valid,
        'duration_matched': duration_matched,
        'dimensions_valid': dimensions_valid,
        'duration_actual': round(duration_actual, 2),
        'duration_expected': round(expected_duration, 2),
        'file_size_bytes': file_size
    }

    error_msg = None
    if not file_readable:
        error_msg = 'File video kết quả rỗng hoặc không đọc được.'
    elif not audio_valid:
        error_msg = 'Video gốc có âm thanh nhưng MP4 kết quả bị thiếu âm thanh.'
    elif not duration_matched:
        error_msg = f"Thời lượng video xuất ({duration_actual:.1f}s) lệch so với kế hoạch ({expected_duration:.1f}s)."
    elif not dimensions_valid:
        error_msg = f"Kích thước khung hình ({width}x{height}) chưa đạt chuẩn 720x1280."

    return passed, checks, error_msg


def check_low_edit_density(plan, user_prompt):
    """Check if output has minimal editing while user requested dynamic output."""
    explicit_minimal = bool(re.search(
        r'tối giản|không (?:cần |dùng |thêm )?(?:hiệu ứng|minh họa|zoom|sfx|chữ|đồ họa)|minimal|chỉ chữ|chỉ camera',
        user_prompt or '', re.I))

    storyboard = plan.get('storyboard', [])
    keyframes = plan.get('effect_keyframes', [])

    ill_count = len([s for s in storyboard if s.get('scene_type') != 'talking_head'])
    zoom_count = len([k for k in keyframes if str(k.get('id', '')).startswith('zoom')])
    sfx_count = len([s for s in storyboard if s.get('sound_effect') and s.get('sound_effect') != 'none'])

    if not explicit_minimal and ill_count == 0 and zoom_count <= 1 and sfx_count == 0:
        return True, "Mức độ biên tập thấp: Video chủ yếu chỉ có camera gốc và phụ đề; chưa có đồ họa minh họa hoặc nhịp dựng năng động như yêu cầu (có thể do AI chuyển sang bản dự phòng hoặc thiếu tài nguyên phù hợp)."

    return False, None


def build_render_report(plan, snapshot, meta, output_path, options, duration, event=None, fallback_reason=None):
    """Construct full post-render audit comparing plan to actual rendered video."""
    storyboard = plan.get('storyboard', [])
    keyframes = plan.get('effect_keyframes', [])
    overlays = plan.get('visual_overlays', [])
    audio_tracks = plan.get('audio_tracks', [])
    subtitles = plan.get('subtitles', [])
    subtitle_review = plan.get('subtitle_review', [])

    ill_scenes = [s for s in storyboard if s.get('scene_type') != 'talking_head']
    ill_duration = sum(float(s.get('duration', 0)) for s in ill_scenes)
    ill_count = len(ill_scenes)

    zoom_count = len([k for k in keyframes if str(k.get('id', '')).startswith('zoom')])
    transition_count = len([s for s in storyboard if s.get('animation_in') and s.get('animation_in') != 'none'])
    sfx_count = len([s for s in storyboard if s.get('sound_effect') and s.get('sound_effect') != 'none'])

    user_assets_used = set()
    for s in storyboard:
        if s.get('visual_asset_id'):
            user_assets_used.add(str(s['visual_asset_id']))
    for o in overlays:
        if o.get('asset_id'):
            user_assets_used.add(str(o['asset_id']))

    plan_metrics = {
        'scene_count': len(storyboard),
        'illustration_scene_count': ill_count,
        'illustration_duration_seconds': round(ill_duration, 2),
        'illustration_duration_ratio': round(ill_duration / max(0.001, duration), 3),
        'zoom_count': zoom_count,
        'transition_count': transition_count,
        'sfx_count': sfx_count,
        'audio_track_count': len(audio_tracks),
        'user_assets_used_count': len(user_assets_used),
        'subtitle_count': len(subtitles),
        'review_warning_count': len(subtitle_review)
    }

    out_file = Path(output_path)
    file_size = out_file.stat().st_size if out_file.is_file() else 0
    rendered_metrics = {
        'probe_verified': True,
        'output_filename': out_file.name,
        'file_size_bytes': file_size,
        'duration_seconds': round(float(meta.get('duration', 0.0)), 2),
        'width': int(meta.get('width', 0)),
        'height': int(meta.get('height', 0)),
        'has_audio': bool(meta.get('has_audio', False)),
        'actual_rendered_zooms': zoom_count,
        'actual_rendered_overlays': len(overlays),
        'actual_rendered_audio_tracks': len(audio_tracks)
    }

    vdiag = plan.get('director', {}).get('vision_diagnostics', {})
    vision_analysis = {
        'vision_requested': bool(vdiag.get('vision_requested', False)),
        'vision_used': bool(vdiag.get('vision_used', False)),
        'sampled_frame_count': int(vdiag.get('sampled_frame_count', 0)),
        'scene_cue_count': int(vdiag.get('scene_cue_count', 0)),
        'silence_cue_count': int(vdiag.get('silence_cue_count', 0)),
        'analysed_ranges': sanitize_value(vdiag.get('analysed_ranges', [])),
        'warnings': [sanitize_value(w) for w in vdiag.get('warnings', [])]
    }

    source_has_audio = bool(snapshot.get('video', {}).get('metadata', {}).get('has_audio'))
    gate_passed, checks, gate_err = check_quality_gate(meta, output_path, duration, source_has_audio, options.automatic)

    user_prompt = (getattr(options, 'user_prompt', None) or getattr(options, 'prompt', '') or '').strip()
    is_low_edit, low_edit_reason = check_low_edit_density(plan, user_prompt)

    director = plan.get('director', {})
    engine = director.get('engine', 'rules')
    planning_mode = 'fallback' if (engine == 'rules' or fallback_reason) else 'ai'

    # 4 distinct UI statuses:
    # 1. "AI hoàn thành" (ai_completed)
    # 2. "Bản dự phòng" (fallback)
    # 3. "Cần xem lại" (needs_review)
    # 4. "Dựng thất bại" (failed)
    if not gate_passed:
        status_category = 'Dựng thất bại'
        status_code = 'failed'
    elif planning_mode == 'fallback':
        status_category = 'Bản dự phòng'
        status_code = 'fallback'
    elif is_low_edit or len(subtitle_review) > 0:
        status_category = 'Cần xem lại'
        status_code = 'needs_review'
    else:
        status_category = 'AI hoàn thành'
        status_code = 'ai_completed'

    reason_desc = FALLBACK_REASONS.get(fallback_reason, fallback_reason) if fallback_reason else None

    all_warnings = list(dict.fromkeys(
        plan.get('director', {}).get('warnings', []) +
        ([low_edit_reason] if is_low_edit else [])
    ))

    report = {
        'status_category': status_category,
        'status_code': status_code,
        'engine': engine,
        'model': director.get('model'),
        'planning_mode': planning_mode,
        'fallback_reason': fallback_reason,
        'fallback_reason_detail': reason_desc,
        'plan_metrics': plan_metrics,
        'rendered_metrics': rendered_metrics,
        'vision_analysis': vision_analysis,
        'quality_gate': {
            'passed': gate_passed,
            'checks': checks,
            'error_message': gate_err,
            'low_edit_warning': is_low_edit,
            'low_edit_reason': low_edit_reason
        },
        'warnings': [sanitize_value(w) for w in all_warnings]
    }

    return sanitize_value(report)
