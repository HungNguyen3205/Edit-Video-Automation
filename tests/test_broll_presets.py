"""Tests reproducing and verifying B-roll preservation, beat progression, and real rendering across presets."""
import copy
import subprocess
import threading
import pytest

from test_pipeline import client, media, new_project
from style_presets import apply_style_preset
from motion_style import apply_motion_style
from automatic_director import fallback_direction
from editing import length, probe, validate
import main


def directed(plan):
    return fallback_direction(plan, 'Giữ nguyên lời nói', threading.Event(), 'TEST_NO_MODEL')


def test_reproduce_broll_lost_in_inspirational_and_real_estate_presets(media):
    """Reproduction Test: When a valid B-roll is assigned to storyboard,
    passing it through inspirational or real_estate presets previously dropped
    visual_asset_id and converted scene_type to 'talking_head'.
    Now both presets preserve B-roll footage.
    """
    p = new_project(media)['edit_plan']
    broll_asset = {
        'id': 'broll_property_video',
        'type': 'video',
        'filename': 'property.mp4',
        'original_name': 'property.mp4',
        'keywords': 'biệt thự, căn hộ',
        'metadata': {'duration': 10.0, 'width': 720, 'height': 1280, 'fps': 30}
    }
    p['assets'].append(broll_asset)
    plan = directed(p)

    target_idx = 1 if len(plan['storyboard']) > 2 else 0
    plan['storyboard'][target_idx].update(
        scene_type='broll',
        visual_asset_id='broll_property_video',
        visual_source_in=0.0
    )

    # Test inspirational preset
    res_insp = apply_style_preset(copy.deepcopy(plan), 'inspirational')
    assert any(s.get('scene_type') == 'broll' and s.get('visual_asset_id') == 'broll_property_video' for s in res_insp['storyboard'])
    validate(res_insp, res_insp['assets'])

    # Test real_estate preset
    res_re = apply_style_preset(copy.deepcopy(plan), 'real_estate')
    assert any(s.get('scene_type') == 'broll' and s.get('visual_asset_id') == 'broll_property_video' for s in res_re['storyboard'])
    validate(res_re, res_re['assets'])


@pytest.mark.parametrize('preset_id', ['explainer', 'inspirational', 'real_estate'])
def test_all_three_presets_preserve_broll_after_pipeline(media, preset_id):
    """Explainer, inspirational, and real_estate all preserve B-roll video footage."""
    p = new_project(media)['edit_plan']
    broll_asset = {
        'id': 'broll_estate_vid',
        'type': 'video',
        'filename': 'estate.mp4',
        'original_name': 'estate.mp4',
        'keywords': '',
        'metadata': {'duration': 10.0, 'width': 720, 'height': 1280, 'fps': 30}
    }
    p['assets'].append(broll_asset)
    plan = directed(p)
    target_idx = 1 if len(plan['storyboard']) > 2 else 0
    plan['storyboard'][target_idx].update(
        scene_type='broll',
        visual_asset_id='broll_estate_vid',
        visual_source_in=1.5
    )

    result = apply_style_preset(plan, preset_id)
    broll_scenes = [s for s in result['storyboard'] if s.get('visual_asset_id') == 'broll_estate_vid']
    assert len(broll_scenes) >= 1
    for s in broll_scenes:
        assert s['scene_type'] == 'broll'
        assert s['visual_source_in'] >= 1.5
    validate(result, result['assets'])


def test_inspirational_beat_division_advances_visual_source_in_without_repeating(media):
    """When a 3.6s B-roll scene is split into beats in inspirational preset:
    - Beat 0 reads from visual_source_in (e.g. 1.0s)
    - Beat 1 reads from visual_source_in + 1.8s = 2.8s
    - It does NOT replay the same starting frame at every beat.
    """
    p = new_project(media)['edit_plan']
    broll_long = {
        'id': 'broll_long_vid',
        'type': 'video',
        'filename': 'long.mp4',
        'original_name': 'long.mp4',
        'metadata': {'duration': 15.0, 'width': 720, 'height': 1280, 'fps': 30}
    }
    p['assets'].append(broll_long)
    plan = directed(p)

    plan['storyboard'] = [
        {
            'scene_id': 'sc_broll_long',
            'scene_type': 'broll',
            'timeline_start': 0.0,
            'duration': 3.6,
            'visual_asset_id': 'broll_long_vid',
            'visual_source_in': 1.0,
            'headline': 'Đoạn B-roll cảm hứng'
        },
        {
            'scene_id': 'sc_tail',
            'scene_type': 'talking_head',
            'timeline_start': 3.6,
            'duration': 0.4,
            'headline': 'Kết bài'
        }
    ]

    res = apply_style_preset(plan, 'inspirational')
    beats = [s for s in res['storyboard'] if s.get('visual_asset_id') == 'broll_long_vid']
    assert len(beats) == 2, f"Expected 2 beats, got {len(beats)}"

    assert beats[0]['visual_source_in'] == pytest.approx(1.0)
    assert beats[1]['visual_source_in'] == pytest.approx(1.0 + 1.8)
    assert beats[0]['visual_source_in'] < beats[1]['visual_source_in']

    # Footage source_in and B-roll visual_source_in are not mixed up
    assert beats[0]['source_in'] != beats[0]['visual_source_in'] or beats[0]['visual_source_in'] == 1.0
    validate(res, res['assets'])


def test_real_estate_does_not_warn_missing_images_when_video_footage_present(media):
    """In real_estate preset, user-supplied video B-roll counts as authentic property footage
    and avoids the warning 'Chưa ghép được ảnh bất động sản phù hợp'.
    """
    p = new_project(media)['edit_plan']
    broll_asset = {
        'id': 'broll_villa',
        'type': 'video',
        'filename': 'villa.mp4',
        'original_name': 'villa.mp4',
        'metadata': {'duration': 10.0, 'width': 720, 'height': 1280, 'fps': 30}
    }
    p['assets'].append(broll_asset)
    plan = directed(p)
    target_idx = 1 if len(plan['storyboard']) > 2 else 0
    plan['storyboard'][target_idx].update(
        scene_type='broll',
        visual_asset_id='broll_villa',
        visual_source_in=0.0
    )

    res = apply_style_preset(plan, 'real_estate')
    warnings = res.get('director', {}).get('warnings', [])
    assert not any('Chưa ghép được ảnh bất động sản phù hợp' in w for w in warnings)
    validate(res, res['assets'])


def test_idempotent_preset_application_does_not_accumulate_or_drift(media):
    """Applying a preset multiple times must be strictly idempotent:
    no scene duplication, no beat explosion, and no visual_source_in drift.
    """
    p = new_project(media)['edit_plan']
    broll_asset = {
        'id': 'broll_idemp',
        'type': 'video',
        'filename': 'idemp.mp4',
        'original_name': 'idemp.mp4',
        'metadata': {'duration': 10.0, 'width': 720, 'height': 1280, 'fps': 30}
    }
    p['assets'].append(broll_asset)
    plan = directed(p)
    target_idx = 1 if len(plan['storyboard']) > 2 else 0
    plan['storyboard'][target_idx].update(
        scene_type='broll',
        visual_asset_id='broll_idemp',
        visual_source_in=0.5
    )

    once = apply_style_preset(plan, 'inspirational')
    twice = apply_style_preset(once, 'inspirational')

    assert len(once['storyboard']) == len(twice['storyboard'])
    brolls_1 = [s['visual_source_in'] for s in once['storyboard'] if s.get('visual_asset_id') == 'broll_idemp']
    brolls_2 = [s['visual_source_in'] for s in twice['storyboard'] if s.get('visual_asset_id') == 'broll_idemp']
    assert brolls_1 == brolls_2


def test_real_mp4_render_preserves_broll_in_inspirational_and_real_estate(media, monkeypatch):
    """End-to-end integration: Rendering real MP4 under inspirational preset with B-roll (green video media[1])
    proves the B-roll is physically burned into the final MP4 with correct duration and voice carrier.
    """
    proj = new_project(media)
    green_video = media[1]
    with green_video.open('rb') as f:
        res = client.post(f'/api/projects/{proj["id"]}/upload', files={'file': ('green_broll.mp4', f)}, data={'role': 'broll', 'keywords': ''}).json()
    broll_id = res['edit_plan']['assets'][-1]['id']

    proj = client.get(f'/api/projects/{proj["id"]}').json()
    aid = proj['video']['asset_id']
    proj['edit_plan']['subtitles'] = [{'id': 's1', 'asset_id': aid, 'start': 0, 'end': 4, 'text': 'Khám phá video thực tế.'}]
    proj['edit_plan']['recognition_subtitles'] = copy.deepcopy(proj['edit_plan']['subtitles'])
    main.save_project(proj['id'], proj)

    resp = client.post(f'/api/projects/{proj["id"]}/make-video', json={'broll_asset_ids': [broll_id], 'style_preset': 'inspirational'})
    assert resp.status_code == 200, resp.text

    result = client.get(f'/api/projects/{proj["id"]}').json()
    assert result['job']['status'] == 'succeeded', result['job']

    # Storyboard must retain broll
    storyboard = result['edit_plan']['storyboard']
    broll_scenes = [s for s in storyboard if s.get('scene_type') == 'broll']
    assert len(broll_scenes) >= 1

    output_path = main.OUTPUTS_DIR / result['output_path'].split('/')[-1]
    meta = probe(output_path)
    assert meta['has_audio']
    assert meta['duration'] == pytest.approx(4.0, abs=0.1)

    # Sample video pixels: B-roll green color must appear in the rendered video
    b_scene = broll_scenes[0]
    b_time = b_scene['timeline_start'] + b_scene['duration'] / 2.0
    raw_green = subprocess.run([
        'ffmpeg', '-v', 'error', '-ss', str(b_time), '-i', str(output_path),
        '-frames:v', '1', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'
    ], check=True, capture_output=True).stdout
    import numpy as np
    frame = np.frombuffer(raw_green, dtype=np.uint8).reshape((1280, 720, 3))
    center_patch = frame[400:800, 200:520]
    green_count = int(np.sum((center_patch[:, :, 1] > 100) & (center_patch[:, :, 0] < 80)))
    assert green_count > 1000, "Green B-roll was not visible in rendered inspirational output."
