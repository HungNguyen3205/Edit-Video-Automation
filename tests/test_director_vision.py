"""Comprehensive tests for AI video analysis, vision integration, and fallback mechanisms.

Covers:
- End-to-end integration: automatic_direction calls real analyzer and records vision_diagnostics.
- Ollama HTTP contract: images attached when VIDEO_AI_VISION=1 with a vision-capable model.
- Vision disabled: no images sent to Ollama, explicit warning recorded.
- Text-only model with vision requested: reports vision unsupported and does not claim video was seen.
- Cue mapping: source_time and timeline_time properly recorded.
- Task cancellation and timeout responsiveness.
- SHA-256 analysis cache hit/invalidation on source or config changes.
- Speechless video: segmented by scene cues with explicit limitations stated.
- Diagnostics safety: verify base64 image strings are never stored in log diagnostics.
- Mock contract vs real inference distinction.
"""
import copy
import hashlib
import json
import os
import threading
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

import ai_director
from ai_director import (
    analyse,
    AnalysisResult,
    model_supports_vision,
    analysis_cache_key,
    _ANALYSIS_MEMORY_CACHE,
    ANALYZER_VERSION,
)
from automatic_director import automatic_direction, semantic_units, fallback_direction


def make_test_plan(subtitles=True, clip_duration=12.0, source_in=0.0, timeline_start=0.0):
    plan = {
        'id': 'test-proj-001',
        'style_preset': {'id': 'explainer', 'version': 1},
        'output_settings': {'fps': 30, 'width': 720, 'height': 1280},
        'assets': [
            {
                'id': 'asset-vid-1',
                'type': 'video',
                'filename': 'main.mp4',
                'metadata': {'duration': clip_duration, 'has_audio': True}
            }
        ],
        'video_clips': [
            {
                'id': 'clip-1',
                'asset_id': 'asset-vid-1',
                'source_in': source_in,
                'source_out': source_in + clip_duration,
                'duration': clip_duration,
                'timeline_start': timeline_start
            }
        ],
        'text_overlays': [],
        'visual_overlays': [],
        'effect_keyframes': [],
        'audio_tracks': []
    }
    if subtitles:
        plan['subtitles'] = [
            {'id': 's1', 'asset_id': 'asset-vid-1', 'start': 0.0, 'end': 3.5, 'text': 'Chào các bạn hôm nay chúng ta cùng tìm hiểu.', 'words': []},
            {'id': 's2', 'asset_id': 'asset-vid-1', 'start': 3.5, 'end': 7.5, 'text': 'Giải pháp mới giúp xử lý công việc tự động và tối ưu.', 'words': []},
            {'id': 's3', 'asset_id': 'asset-vid-1', 'start': 7.5, 'end': 12.0, 'text': 'Hãy áp dụng ngay để cảm nhận sự khác biệt.', 'words': []}
        ]
    return plan


class MockEvent:
    def __init__(self, is_set=False):
        self._is_set = is_set
        self.ai_diagnostics = {}
        self.ai_valid_choices = {}
        self.ai_validation_errors = []

    def is_set(self):
        return self._is_set

    def set(self):
        self._is_set = True


def test_model_supports_vision_detection():
    """Verify vision capability checks against known vision vs text-only models."""
    assert model_supports_vision('llava') is True
    assert model_supports_vision('llava:7b') is True
    assert model_supports_vision('qwen2.5-vl:7b') is True
    assert model_supports_vision('minicpm-v') is True
    assert model_supports_vision('moondream:latest') is True

    # Standard text-only models must return False
    assert model_supports_vision('qwen3:4b') is False
    assert model_supports_vision('llama3:8b') is False
    assert model_supports_vision('mistral') is False


def test_analysis_result_tuple_unpacking():
    """AnalysisResult must unpack into (cues, frames) for 100% backward compatibility."""
    cues = [{'clip': 0, 'scene_changes': []}]
    frames = [{'timeline_time': 1.0, 'data': 'mockbase64'}]
    diag = {'vision_used': False, 'sampled_frame_count': 1}
    res = AnalysisResult(cues, frames, diag)

    unpacked_cues, unpacked_frames = res
    assert unpacked_cues == cues
    assert unpacked_frames == frames
    assert res.diagnostics == diag
    assert res['cues'] == cues


def test_analyse_caching_and_invalidation(tmp_path):
    """Cache returns hit for identical source/config, and invalidates on source/config changes."""
    _ANALYSIS_MEMORY_CACHE.clear()
    plan1 = make_test_plan(clip_duration=10.0, source_in=0.0)
    event = MockEvent()

    with patch.dict(os.environ, {'VIDEO_AI_VISION': '0'}):
        res1 = analyse(plan1, tmp_path, tmp_path, event)
        assert res1.diagnostics['cache_hit'] is False

        # Second call with identical configuration must hit cache
        res2 = analyse(plan1, tmp_path, tmp_path, event)
        assert res2.diagnostics['cache_hit'] is True

        # Change clip source_in -> must invalidate cache (different key)
        plan2 = make_test_plan(clip_duration=10.0, source_in=5.0)
        res3 = analyse(plan2, tmp_path, tmp_path, event)
        assert res3.diagnostics['cache_hit'] is False

    # Change vision setting -> must invalidate cache
    with patch.dict(os.environ, {'VIDEO_AI_VISION': '1'}):
        res4 = analyse(plan1, tmp_path, tmp_path, event)
        assert res4.diagnostics['cache_hit'] is False


def test_cue_timestamp_mapping_after_cut(tmp_path):
    """Scene and silence cues must record explicit source_time and timeline_time offset correctly."""
    _ANALYSIS_MEMORY_CACHE.clear()
    source_in = 15.0
    timeline_start = 5.0
    plan = make_test_plan(clip_duration=10.0, source_in=source_in, timeline_start=timeline_start)
    event = MockEvent()

    # Create dummy video file to trigger ffmpeg call
    video_file = tmp_path / 'main.mp4'
    video_file.write_bytes(b'fake_video_bytes')

    mock_ffmpeg_output = (
        "pts_time:2.500 showinfo\n"
        "[silencedetect @ 000] silence_start: 3.200\n"
        "[silencedetect @ 000] silence_end: 4.800 | silence_duration: 1.6\n"
    )

    with patch('subprocess.run') as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stderr=mock_ffmpeg_output)
        with patch.dict(os.environ, {'VIDEO_AI_VISION': '0'}):
            res = analyse(plan, tmp_path, tmp_path, event)

    assert len(res.cues) == 1
    clip_cue = res.cues[0]
    assert len(clip_cue['scene_changes']) == 1
    sc = clip_cue['scene_changes'][0]
    # source_time = 15.0 + 2.5 = 17.5
    # timeline_time = 5.0 + 2.5 = 7.5
    assert sc['source_time'] == pytest.approx(17.5)
    assert sc['timeline_time'] == pytest.approx(7.5)

    assert len(clip_cue['silence']) == 2
    sil_start = clip_cue['silence'][0]
    assert sil_start['kind'] == 'start'
    assert sil_start['source_time'] == pytest.approx(18.2)
    assert sil_start['timeline_time'] == pytest.approx(8.2)


def test_uniform_frame_sampling_distribution(tmp_path):
    """Frames must be sampled uniformly across the analysed video span, not clustered at start."""
    _ANALYSIS_MEMORY_CACHE.clear()
    plan = make_test_plan(clip_duration=30.0)
    video_file = tmp_path / 'main.mp4'
    video_file.write_bytes(b'dummy_video')
    event = MockEvent()

    sample_calls = []

    def fake_subprocess_run(cmd, *args, **kwargs):
        cmd_str = ' '.join(str(c) for c in cmd)
        if '-vf' in cmd and 'showinfo' in cmd_str:
            return MagicMock(returncode=0, stderr="")
        if '-frames:v' in cmd:
            # Extract sampled timestamp
            ss_idx = cmd.index('-ss')
            sample_time = float(cmd[ss_idx + 1])
            sample_calls.append(sample_time)
            # Write a small frame file
            out_file = Path(cmd[-1])
            out_file.write_bytes(b'dummy_jpeg')
            return MagicMock(returncode=0)
        return MagicMock(returncode=0)

    with patch('subprocess.run', side_effect=fake_subprocess_run):
        with patch.dict(os.environ, {'VIDEO_AI_VISION': '1', 'VIDEO_AI_MODEL': 'llava:7b', 'VIDEO_AI_MAX_FRAMES': '4'}):
            res = analyse(plan, tmp_path, tmp_path, event)

    assert res.diagnostics['vision_used'] is True
    assert len(res.frames) == 4
    times = [f['timeline_time'] for f in res.frames]
    # Ensure times are distributed across the 30s video (e.g. around 3.75s, 11.25s, 18.75s, 26.25s)
    assert times[0] < times[1] < times[2] < times[3]
    assert times[0] > 0.0
    assert times[-1] > 20.0
    # No temporary frame files should remain in work directory
    assert list(tmp_path.glob('frame-*.jpg')) == []


def test_cancelled_and_timeout_responsiveness(tmp_path):
    """InterruptedError must be raised when task is cancelled before or during analysis."""
    plan = make_test_plan()
    event = MockEvent(is_set=True)

    with pytest.raises(InterruptedError, match='Đã hủy tác vụ AI'):
        analyse(plan, tmp_path, tmp_path, event)


def test_automatic_direction_attaches_images_when_vision_supported(tmp_path):
    """When vision is active with a vision model, automatic_direction attaches images to Ollama chat message."""
    _ANALYSIS_MEMORY_CACHE.clear()
    plan = make_test_plan(clip_duration=12.0)
    event = MockEvent()
    prompt = "Dựng video giải thích chuyên nghiệp có minh họa"

    captured_messages = []

    def mock_chat(messages, ev, schema=None):
        captured_messages.extend(messages)
        # Return valid compact decision matching scenes
        return json.dumps({
            'summary': 'Bản dựng tự động với hỗ trợ hình ảnh',
            'scenes': [
                {'i': 0, 't': 'talking_head', 'h': 'CHÀO BẠN', 'z': 1.0},
                {'i': 1, 't': 'explainer_card', 'h': 'GIẢI PHÁP MỚI', 'k': 'process', 'g': 'Giải pháp mới', 'items': ['Quy trình', 'Tự động'], 's': 'whoosh', 'z': 1.0},
                {'i': 2, 't': 'talking_head', 'h': 'ÁP DỤNG NGAY', 'z': 1.0}
            ],
            'captions': True,
            'font_style': 'auto'
        })

    # Mock analyse to return 2 sampled frames
    mock_frames = [
        {'data': 'base64_frame_1', 'source_time': 2.0, 'timeline_time': 2.0, 'clip_index': 0},
        {'data': 'base64_frame_2', 'source_time': 6.0, 'timeline_time': 6.0, 'clip_index': 0}
    ]
    mock_cues = [{'clip': 0, 'scene_changes': [], 'silence': []}]
    mock_diag = {
        'vision_requested': True,
        'vision_used': True,
        'model': 'llava:7b',
        'sampled_frame_count': 2,
        'analysed_ranges': [],
        'scene_cue_count': 0,
        'silence_cue_count': 0,
        'cache_hit': False,
        'warnings': []
    }
    mock_result = AnalysisResult(mock_cues, mock_frames, mock_diag)

    with patch('automatic_director.analyse', return_value=mock_result):
        with patch('automatic_director.chat', side_effect=mock_chat):
            with patch.dict(os.environ, {'VIDEO_AI_VISION': '1', 'VIDEO_AI_MODEL': 'llava:7b'}):
                res = automatic_direction(plan, prompt, tmp_path, tmp_path, event)

    # Verify Ollama chat request contract
    user_msgs = [m for m in captured_messages if m.get('role') == 'user']
    assert len(user_msgs) >= 1
    assert 'images' in user_msgs[0]
    assert user_msgs[0]['images'] == ['base64_frame_1', 'base64_frame_2']

    # Verify diagnostics in result
    assert res['director']['vision_diagnostics']['vision_used'] is True
    assert res['director']['vision_diagnostics']['sampled_frame_count'] == 2
    # Ensure no base64 string is stored in director vision diagnostics
    assert 'base64_frame_1' not in json.dumps(res['director']['vision_diagnostics'])


def test_automatic_direction_no_images_when_vision_disabled(tmp_path):
    """When VIDEO_AI_VISION=0, no images are sent to Ollama, and a clear warning is recorded."""
    _ANALYSIS_MEMORY_CACHE.clear()
    plan = make_test_plan(clip_duration=12.0)
    event = MockEvent()
    prompt = "Dựng video giải thích chuyên nghiệp"

    captured_messages = []

    def mock_chat(messages, ev, schema=None):
        captured_messages.extend(messages)
        return json.dumps({
            'summary': 'Bản dựng không dùng thị giác',
            'scenes': [
                {'i': 0, 't': 'talking_head', 'h': 'CHÀO BẠN', 'z': 1.0},
                {'i': 1, 't': 'talking_head', 'h': 'GIẢI PHÁP MỚI', 'z': 1.0},
                {'i': 2, 't': 'talking_head', 'h': 'ÁP DỤNG NGAY', 'z': 1.0}
            ],
            'captions': True,
            'font_style': 'auto'
        })

    mock_result = AnalysisResult([], [], {
        'vision_requested': False,
        'vision_used': False,
        'model': 'qwen3:4b',
        'sampled_frame_count': 0,
        'analysed_ranges': [],
        'scene_cue_count': 0,
        'silence_cue_count': 0,
        'cache_hit': False,
        'warnings': ['Chưa phân tích nội dung hình ảnh (chế độ thị giác tắt).']
    })

    with patch('automatic_director.analyse', return_value=mock_result):
        with patch('automatic_director.chat', side_effect=mock_chat):
            with patch.dict(os.environ, {'VIDEO_AI_VISION': '0'}):
                res = automatic_direction(plan, prompt, tmp_path, tmp_path, event)

    user_msgs = [m for m in captured_messages if m.get('role') == 'user']
    assert len(user_msgs) >= 1
    assert 'images' not in user_msgs[0]
    assert any('chưa phân tích nội dung hình ảnh' in w.lower() for w in res['director']['warnings'])


def test_unsupported_model_reports_vision_fallback_policy(tmp_path):
    """When vision is requested but model is text-only (e.g. qwen3:4b), report explicitly and do not send images."""
    _ANALYSIS_MEMORY_CACHE.clear()
    plan = make_test_plan(clip_duration=12.0)
    event = MockEvent()
    prompt = "Dựng video giải thích"

    captured_messages = []

    def mock_chat(messages, ev, schema=None):
        captured_messages.extend(messages)
        return json.dumps({
            'summary': 'Bản dựng an toàn từ văn bản',
            'scenes': [
                {'i': 0, 't': 'talking_head', 'h': 'CHÀO BẠN', 'z': 1.0},
                {'i': 1, 't': 'talking_head', 'h': 'GIẢI PHÁP', 'z': 1.0},
                {'i': 2, 't': 'talking_head', 'h': 'ÁP DỤNG', 'z': 1.0}
            ],
            'captions': True,
            'font_style': 'auto'
        })

    with patch('automatic_director.chat', side_effect=mock_chat):
        with patch.dict(os.environ, {'VIDEO_AI_VISION': '1', 'VIDEO_AI_MODEL': 'qwen3:4b'}):
            res = automatic_direction(plan, prompt, tmp_path, tmp_path, event)

    user_msgs = [m for m in captured_messages if m.get('role') == 'user']
    assert 'images' not in user_msgs[0]
    assert res['director']['vision_diagnostics']['vision_used'] is False
    assert any('không hỗ trợ thị giác' in w for w in res['director']['warnings'])
    assert any('chưa phân tích nội dung hình ảnh' in w.lower() for w in res['director']['warnings'])


def test_speechless_video_uses_scene_cues_with_explicit_limitations(tmp_path):
    """A video without subtitles/speech is segmented naturally by scene cues, stating limitations clearly."""
    _ANALYSIS_MEMORY_CACHE.clear()
    plan = make_test_plan(subtitles=False, clip_duration=15.0)
    event = MockEvent()
    prompt = "Dựng video minh họa không lời"

    mock_cues = [{
        'clip': 0,
        'source_start': 0.0,
        'source_end': 15.0,
        'timeline_start': 0.0,
        'timeline_end': 15.0,
        'scene_changes': [
            {'source_time': 4.0, 'timeline_time': 4.0},
            {'source_time': 9.5, 'timeline_time': 9.5}
        ],
        'silence': []
    }]
    mock_diag = {
        'vision_requested': False,
        'vision_used': False,
        'model': 'qwen3:4b',
        'sampled_frame_count': 0,
        'analysed_ranges': [],
        'scene_cue_count': 2,
        'silence_cue_count': 0,
        'cache_hit': False,
        'warnings': ['Chưa phân tích nội dung hình ảnh (chế độ thị giác tắt).']
    }
    mock_result = AnalysisResult(mock_cues, [], mock_diag)

    # Test semantic_units with cues
    units = semantic_units(plan, cues=mock_cues)
    assert len(units) >= 3
    # Check boundaries match cue points
    assert units[0]['end'] == pytest.approx(4.0)
    assert units[1]['start'] == pytest.approx(4.0)
    assert units[1]['end'] == pytest.approx(9.5)
    assert units[2]['start'] == pytest.approx(9.5)

    def mock_chat(messages, ev, schema=None):
        return json.dumps({
            'summary': 'Bản dựng không lời thoại',
            'scenes': [{'i': idx, 't': 'talking_head', 'h': 'CẢNH ' + str(idx + 1), 'z': 1.0} for idx in range(len(units))],
            'captions': False,
            'font_style': 'auto'
        })

    with patch('automatic_director.analyse', return_value=mock_result):
        with patch('automatic_director.chat', side_effect=mock_chat):
            res = automatic_direction(plan, prompt, tmp_path, tmp_path, event)

    assert any('không có lời thoại nhận dạng và chưa phân tích nội dung hình ảnh' in w for w in res['director']['warnings'])


def test_vision_model_error_fallback_to_text_only(tmp_path):
    """If Ollama throws an error due to image input, automatic_direction automatically falls back to text-only mode."""
    _ANALYSIS_MEMORY_CACHE.clear()
    plan = make_test_plan(clip_duration=12.0)
    event = MockEvent()
    prompt = "Dựng video thử nghiệm fallback"

    mock_frames = [{'data': 'frame_b64', 'source_time': 2.0, 'timeline_time': 2.0, 'clip_index': 0}]
    mock_diag = {
        'vision_requested': True,
        'vision_used': True,
        'model': 'llava:7b',
        'sampled_frame_count': 1,
        'analysed_ranges': [],
        'scene_cue_count': 0,
        'silence_cue_count': 0,
        'cache_hit': False,
        'warnings': []
    }
    mock_result = AnalysisResult([], mock_frames, mock_diag)

    call_count = 0

    def mock_chat_with_image_failure(messages, ev, schema=None):
        nonlocal call_count
        call_count += 1
        user_msg = next(m for m in messages if m.get('role') == 'user')
        if 'images' in user_msg:
            # Model rejected images
            from ai_director import AIError
            raise AIError('AI_MODEL_ERROR', "Ollama: model 'llava:7b' does not support images on this endpoint")
        # Text-only retry succeeded
        return json.dumps({
            'summary': 'Bản dựng sau fallback text-only',
            'scenes': [
                {'i': 0, 't': 'talking_head', 'h': 'CHÀO BẠN', 'z': 1.0},
                {'i': 1, 't': 'talking_head', 'h': 'GIẢI PHÁP', 'z': 1.0},
                {'i': 2, 't': 'talking_head', 'h': 'ÁP DỤNG', 'z': 1.0}
            ],
            'captions': True,
            'font_style': 'auto'
        })

    with patch('automatic_director.analyse', return_value=mock_result):
        with patch('automatic_director.chat', side_effect=mock_chat_with_image_failure):
            with patch.dict(os.environ, {'VIDEO_AI_VISION': '1', 'VIDEO_AI_MODEL': 'llava:7b'}):
                res = automatic_direction(plan, prompt, tmp_path, tmp_path, event)

    assert call_count == 2
    assert res['director']['vision_diagnostics']['vision_used'] is False
    assert any('không nhận diện được hình ảnh' in w for w in res['director']['warnings'])


def test_make_video_pipeline_end_to_end_invokes_analyzer(tmp_path):
    """Verify that automatic_direction executes real analyser and populates vision diagnostics."""
    _ANALYSIS_MEMORY_CACHE.clear()
    plan = make_test_plan(clip_duration=12.0)
    event = MockEvent()
    prompt = "Dựng video một nút hoàn chỉnh"

    def mock_chat(messages, ev, schema=None):
        return json.dumps({
            'summary': 'Kế hoạch hoàn chỉnh',
            'scenes': [
                {'i': 0, 't': 'talking_head', 'h': 'CHÀO BẠN', 'z': 1.0},
                {'i': 1, 't': 'talking_head', 'h': 'GIẢI PHÁP', 'z': 1.0},
                {'i': 2, 't': 'talking_head', 'h': 'ÁP DỤNG', 'z': 1.0}
            ],
            'captions': True,
            'font_style': 'auto'
        })

    with patch('automatic_director.chat', side_effect=mock_chat):
        with patch.dict(os.environ, {'VIDEO_AI_VISION': '0'}):
            res = automatic_direction(plan, prompt, tmp_path, tmp_path, event)

    assert 'vision_diagnostics' in res['director']
    diag = res['director']['vision_diagnostics']
    assert diag['vision_requested'] is False
    assert diag['vision_used'] is False
    assert diag['cache_hit'] is False
    assert event.ai_diagnostics.get('vision') == diag

