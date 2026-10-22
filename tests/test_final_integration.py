"""Integration tests validating user opt-out matrix, preset preservation, idempotency, and real moving MP4 render."""
import copy
import json
import subprocess
import threading
from pathlib import Path
import pytest

from editing import probe, validate, length
from motion_style import apply_motion_style
from style_presets import apply_style_preset, apply_user_overrides
from scene_transitions import transition_frames
import main
from test_pipeline import client, media, new_project


def make_sample_plan():
    text = "Hệ thống tự động nhận dạng khuôn mặt và xử lý đồ họa thông minh."
    words = []
    for i, w in enumerate(text.split()):
        words.append({'word': w, 'start': i * 0.4, 'end': (i + 1) * 0.4})
    duration = round(len(words) * 0.4, 2)
    return {
        'assets': [
            {'id': 'cam_source', 'type': 'video', 'filename': 'cam.mp4', 'metadata': {'duration': duration, 'width': 720, 'height': 1280, 'fps': 25, 'has_audio': True}},
            {'id': 'bg_music', 'type': 'audio', 'filename': 'music.wav', 'metadata': {'duration': duration, 'has_audio': True}}
        ],
        'video_clips': [{'id': 'clip_0', 'asset_id': 'cam_source', 'source_in': 0, 'duration': duration, 'timeline_start': 0}],
        'subtitles': [{'id': 'sub_0', 'asset_id': 'cam_source', 'start': 0, 'end': duration, 'text': text, 'words': words}],
        'audio_tracks': [{'id': 'track_music', 'origin': 'style_preset', 'kind': 'music', 'asset_id': 'bg_music', 'timeline_start': 0, 'duration': duration, 'volume': 0.1}],
        'effect_keyframes': [{'id': 'zoom_1', 'origin': 'style_preset', 'timeline_start': 0, 'duration': duration, 'scale': 1.15}],
        'storyboard': [
            {
                'scene_id': 'sc_0',
                'scene_type': 'explainer_card',
                'timeline_start': 0,
                'duration': duration / 2,
                'source_in': 0,
                'asset_id': 'cam_source',
                'headline': 'TỰ ĐỘNG NHẬN DẠNG',
                'graphic_kind': 'process',
                'graphic_title': 'Nhận dạng',
                'graphic_items': ['nhận dạng khuôn mặt', 'xử lý đồ họa'],
                'transcript_meaning': text,
                'sound_effect': 'whoosh',
                'sound_volume': 0.15,
                'motion': {'animate': True, 'stagger': True, 'photo_zoom': 0.05, 'transition_seconds': 0.2}
            },
            {
                'scene_id': 'sc_1',
                'scene_type': 'talking_head',
                'timeline_start': duration / 2,
                'duration': duration / 2,
                'source_in': duration / 2,
                'asset_id': 'cam_source',
                'headline': 'ĐỒ HỌA THÔNG MINH',
                'transcript_meaning': text,
                'sound_effect': 'pop',
                'sound_volume': 0.1,
                'motion': {'animate': True, 'stagger': False, 'photo_zoom': 0.0, 'transition_seconds': 0.2}
            }
        ],
        'director': {'warnings': []},
        'text_overlays': [{'id': 'txt_0', 'timeline_start': 0, 'duration': 2, 'text': 'TIÊU ĐỀ ĐOẠN'}],
        'show_captions': True,
        'output_settings': {'fps': 25, 'width': 720, 'height': 1280}
    }


@pytest.mark.parametrize("preset", ["explainer", "inspirational", "real_estate"])
@pytest.mark.parametrize("motion", ["clean", "dynamic_explainer"])
def test_matrix_presets_and_motion_preserves_grounded_graphics(preset, motion):
    base = make_sample_plan()
    p1 = apply_motion_style(base, motion)
    p2 = apply_style_preset(p1, preset)
    p_final = apply_user_overrides(p2)
    # The first scene has grounded items: 'nhận dạng khuôn mặt', 'xử lý đồ họa' both in speech text
    first_scene = p_final['storyboard'][0]
    assert first_scene['scene_type'] == 'explainer_card'
    assert 'nhận dạng khuôn mặt' in first_scene['graphic_items']
    assert first_scene['graphic_title'] == 'Nhận dạng'


@pytest.mark.parametrize("opt_out,check_fn", [
    ("không chữ", lambda p: not p.get('show_captions', True) and not p.get('text_overlays') and all(not s.get('headline') and not s.get('graphic_items') for s in p['storyboard'])),
    ("không phụ đề", lambda p: not p.get('show_captions', True) and bool(p['storyboard'][1].get('headline'))),
    ("không zoom", lambda p: not any(e.get('scale', 1.0) != 1.0 or 'zoom' in str(e.get('id', '')) for e in p.get('effect_keyframes', [])) and all(s.get('motion', {}).get('photo_zoom', 0) == 0 for s in p['storyboard'])),
    ("không hiệu ứng", lambda p: p.get('effect_keyframes') == [] and all(not s.get('motion', {}).get('animate', True) and s.get('sound_effect') == 'none' for s in p['storyboard'])),
    ("không sfx", lambda p: all(s.get('sound_effect') == 'none' and s.get('sound_volume') == 0 for s in p['storyboard']) and not any(t.get('kind') == 'sfx' for t in p.get('audio_tracks', [])) and any(t.get('kind') == 'music' for t in p.get('audio_tracks', []))),
    ("không nhạc", lambda p: not any(t.get('kind') == 'music' for t in p.get('audio_tracks', []))),
    ("không âm thanh", lambda p: p.get('audio_tracks') == [] and all(s.get('sound_effect') == 'none' for s in p['storyboard'])),
    ("không minh họa", lambda p: all(not s.get('library_visual_id') and not s.get('source_cutaway') for s in p['storyboard'])),
])
def test_matrix_individual_opt_outs(opt_out, check_fn):
    base = make_sample_plan()
    p = apply_motion_style(base, 'dynamic_explainer', opt_out)
    p = apply_style_preset(p, 'inspirational', opt_out, music_asset_id='bg_music')
    p = apply_user_overrides(p, opt_out)
    assert check_fn(p)


def test_idempotency_double_run_produces_identical_plan():
    base = make_sample_plan()
    r1 = apply_motion_style(base, 'dynamic_explainer', 'không zoom')
    r1 = apply_style_preset(r1, 'inspirational', 'không zoom', music_asset_id='bg_music')
    r1 = apply_user_overrides(r1, 'không zoom')

    # Run again on the result
    r2 = apply_motion_style(r1, 'dynamic_explainer', 'không zoom')
    r2 = apply_style_preset(r2, 'inspirational', 'không zoom', music_asset_id='bg_music')
    r2 = apply_user_overrides(r2, 'không zoom')

    assert r1 == r2
    assert len(r1['storyboard']) == len(r2['storyboard'])
    assert len(r1['audio_tracks']) == len(r2['audio_tracks'])
    assert len(r1['effect_keyframes']) == len(r2['effect_keyframes'])


def test_camera_transition_intent_and_continuous_speech():
    prev_scene = {'scene_type': 'talking_head', 'duration': 4.0, 'motion': {'animate': True, 'transition_seconds': 0.2}}
    # 1. No intent: hard cut (0 frames)
    curr_default = {'scene_type': 'talking_head', 'duration': 4.0, 'motion': {'animate': True, 'transition_seconds': 0.2}}
    assert transition_frames(prev_scene, curr_default, 25) == 0

    # 2. Intent present (transition='fade') and speech not continuous -> transition frames > 0
    curr_fade = {'scene_type': 'talking_head', 'duration': 4.0, 'transition': 'fade', 'motion': {'animate': True, 'transition_seconds': 0.2}}
    assert transition_frames(prev_scene, curr_fade, 25) == 5  # 0.2 * 25 = 5 frames

    # 3. Intent present but continuous speech flag set -> suppress transition to protect voice continuity
    curr_continuous = {'scene_type': 'talking_head', 'duration': 4.0, 'transition': 'fade', 'is_continuous_speech': True, 'motion': {'animate': True, 'transition_seconds': 0.2}}
    assert transition_frames(prev_scene, curr_continuous, 25) == 0


def test_accurate_source_in_mapping_when_scenes_divided():
    base = make_sample_plan()
    base['storyboard'] = [{
        'scene_id': 'sc_long',
        'scene_type': 'talking_head',
        'timeline_start': 0,
        'duration': 5.0,
        'source_in': 10.0,
        'asset_id': 'cam_source',
        'transcript_meaning': 'Học hơi thở chậm và giữ vai thả lỏng hàng ngày.'
    }]
    # Inspirational splits scene into beats
    res = apply_style_preset(base, 'inspirational')
    scenes = res['storyboard']
    assert len(scenes) >= 2
    # Verify chronological timeline and source_in ordering
    for i in range(len(scenes) - 1):
        assert scenes[i]['timeline_start'] + scenes[i]['duration'] == pytest.approx(scenes[i+1]['timeline_start'])
        assert scenes[i]['source_in'] < scenes[i+1]['source_in']
        assert scenes[i+1]['source_in'] == pytest.approx(scenes[i]['source_in'] + scenes[i]['duration'])


def test_real_moving_video_render(tmp_path):
    """Render a real moving video (testsrc with moving counter and colors) to verify temporal visuals."""
    moving_video = tmp_path / 'moving_source.mp4'
    # Generate 3 seconds of moving video (testsrc draws a moving square and clock) with audio
    subprocess.run([
        'ffmpeg', '-v', 'error', '-y',
        '-f', 'lavfi', '-i', 'testsrc=duration=3:size=720x1280:rate=25',
        '-f', 'lavfi', '-i', 'sine=frequency=440:duration=3',
        '-c:v', 'libx264', '-preset', 'ultrafast', '-pix_fmt', 'yuv420p',
        '-c:a', 'aac', str(moving_video)
    ], check=True)

    meta = probe(moving_video)
    assert meta['has_audio']
    assert meta['duration'] == pytest.approx(3.0, abs=0.1)

    plan = {
        'assets': [{'id': 'mv_source', 'type': 'video', 'filename': str(moving_video.name), 'metadata': meta}],
        'video_clips': [{'id': 'c0', 'asset_id': 'mv_source', 'source_in': 0, 'duration': 3.0, 'timeline_start': 0}],
        'subtitles': [{'id': 's0', 'asset_id': 'mv_source', 'start': 0, 'end': 3.0, 'text': 'Video chuyển động thử nghiệm.', 'words': [{'word': 'Video', 'start': 0, 'end': 1}, {'word': 'chuyển', 'start': 1, 'end': 2}, {'word': 'động', 'start': 2, 'end': 3}]}],
        'audio_tracks': [],
        'effect_keyframes': [],
        'storyboard': [
            {'scene_id': 'sc0', 'scene_type': 'talking_head', 'timeline_start': 0, 'duration': 1.5, 'source_in': 0, 'asset_id': 'mv_source', 'headline': 'CẢNH MỘT'},
            {'scene_id': 'sc1', 'scene_type': 'talking_head', 'timeline_start': 1.5, 'duration': 1.5, 'source_in': 1.5, 'asset_id': 'mv_source', 'headline': 'CẢNH HAI'}
        ],
        'director': {'warnings': []},
        'text_overlays': [],
        'show_captions': True,
        'output_settings': {'fps': 25, 'width': 720, 'height': 1280}
    }

    output = tmp_path / 'final_moving_output.mp4'
    from storyboard_compiler import compile_storyboard_scenes
    total = compile_storyboard_scenes(plan, tmp_path, tmp_path / 'work', output)
    assert output.exists()
    assert total == pytest.approx(3.0, abs=0.1)

    out_meta = probe(output)
    assert out_meta['width'] == 720 and out_meta['height'] == 1280
    assert out_meta['has_audio']
    assert out_meta['duration'] == pytest.approx(3.0, abs=0.1)

    # Verify temporal difference between frame at 0.5s and 2.5s to prove non-static moving video
    import numpy as np
    f1 = subprocess.run(['ffmpeg', '-v', 'error', '-ss', '0.5', '-i', str(output), '-frames:v', '1', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'], capture_output=True, check=True).stdout
    f2 = subprocess.run(['ffmpeg', '-v', 'error', '-ss', '2.5', '-i', str(output), '-frames:v', '1', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'], capture_output=True, check=True).stdout
    arr1 = np.frombuffer(f1, dtype=np.uint8)
    arr2 = np.frombuffer(f2, dtype=np.uint8)
    # The moving test pattern ensures frames are distinctly different over time
    diff = np.abs(arr1.astype(float) - arr2.astype(float)).sum()
    assert diff > 100000, "Frames at different times must show motion and change"
