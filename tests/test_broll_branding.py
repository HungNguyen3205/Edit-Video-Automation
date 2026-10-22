"""Tests reproducing and verifying B-roll branding match_score, duration splitting, and real rendering."""
import copy
import subprocess
import threading
import pytest

from test_pipeline import client, media, new_project
from video_branding import apply_visual_assets, calculate_transcript_match_score, parse_keywords
from automatic_director import fallback_direction
from editing import length, probe, validate
import main


def directed(plan):
    return fallback_direction(plan, 'Giữ nguyên lời nói', threading.Event(), 'TEST_NO_MODEL')


def test_reproduce_unbound_local_error_when_only_broll_with_keywords(media):
    """Reproduction Test 1: Selecting ONLY B-roll with keywords (no images) previously caused
    UnboundLocalError / NameError because match_score() was defined inside the images loop.
    Now it parses keywords cleanly and selects candidate without error.
    """
    p = new_project(media)['edit_plan']
    broll_asset = {
        'id': 'broll_video_1',
        'type': 'video',
        'filename': 'broll.mp4',
        'original_name': 'broll.mp4',
        'keywords': 'khu vườn, hoa cỏ',
        'metadata': {'duration': 10.0, 'width': 720, 'height': 1280, 'fps': 30}
    }
    p['assets'].append(broll_asset)
    plan = directed(p)

    # Calling with ONLY broll_asset_ids and NO image_asset_ids
    result = apply_visual_assets(
        plan,
        prompt='Giới thiệu',
        image_asset_ids=None,
        broll_asset_ids=['broll_video_1']
    )
    assert result is not None
    # Verify diagnostic recorded the keyword matching
    diag = next(d for d in result['director']['visual_diagnostics'] if d['selected_id'] == 'broll_video_1')
    assert diag['matched_terms'] == ['khu vườn', 'hoa cỏ']


def test_reproduce_broll_exceeds_duration_validation_error(media):
    """Reproduction Test 2: B-roll shorter than the scene assigned previously led to
    'B-roll vượt thời lượng tài nguyên' in editing.validate().
    Now it splits the scene cleanly, keeping total timeline intact.
    """
    p = new_project(media)['edit_plan']
    # Add a short B-roll video asset (1.0s)
    broll_short = {
        'id': 'broll_short_1',
        'type': 'video',
        'filename': 'short_broll.mp4',
        'original_name': 'short_broll.mp4',
        'keywords': '',
        'metadata': {'duration': 1.0, 'width': 720, 'height': 1280, 'fps': 30}
    }
    p['assets'].append(broll_short)
    plan = directed(p)
    original_len = length(plan)
    assert plan['storyboard'][0]['duration'] > 1.0

    result = apply_visual_assets(
        plan,
        prompt='Giới thiệu',
        broll_asset_ids=['broll_short_1']
    )
    # Validate must pass without raising 'B-roll vượt thời lượng tài nguyên'
    validate(result, result['assets'])
    # Total plan length must not change
    assert length(result) == pytest.approx(original_len)


def test_isolated_match_score_function():
    """Verify parse_keywords and calculate_transcript_match_score are independent functions."""
    assert parse_keywords('trợ lý, AI, công nghệ') == ['trợ lý', 'AI', 'công nghệ']
    assert parse_keywords('') == []
    assert parse_keywords(None) == []

    speech = 'Trợ lý AI sẽ giúp nâng cao năng suất doanh nghiệp.'
    # Exact keyword match
    score = calculate_transcript_match_score(speech, ['trợ lý', 'AI'])
    assert score > 0

    # No match
    zero_score = calculate_transcript_match_score(speech, ['bất động sản', 'du lịch'])
    assert zero_score == 0


def test_broll_with_unmatched_keywords_is_skipped_with_diagnostics(media):
    """When a B-roll has keywords but none match transcript, it is NOT assigned to scene 0.
    Instead, it records warning and fallback_reason='no_matching_transcript'.
    """
    p = new_project(media)['edit_plan']
    broll_asset = {
        'id': 'broll_unmatched',
        'type': 'video',
        'filename': 'unmatched.mp4',
        'original_name': 'unmatched.mp4',
        'keywords': 'khách sạn, du thuyền cao cấp',
        'metadata': {'duration': 4.0, 'width': 720, 'height': 1280, 'fps': 30}
    }
    p['assets'].append(broll_asset)
    plan = directed(p)

    result = apply_visual_assets(
        plan,
        prompt='Giới thiệu',
        broll_asset_ids=['broll_unmatched']
    )
    # The B-roll must NOT be assigned to any scene
    assert not any(s.get('visual_asset_id') == 'broll_unmatched' for s in result['storyboard'])
    # Warning must explain why it was skipped
    assert any('Chưa tìm thấy lời nói phù hợp' in w for w in result['director']['warnings'])
    diag = next(d for d in result['director']['visual_diagnostics'] if d['selected_id'] == 'broll_unmatched')
    assert diag['fallback_reason'] == 'no_matching_transcript'


def test_broll_one_second_in_five_second_scene_maintains_total_duration(media):
    """A 1-second B-roll applied to a 4-second scene splits into 1s B-roll + 3s talking head.
    Total duration and voice timeline remain strictly intact.
    """
    p = new_project(media)['edit_plan']
    broll_1s = {
        'id': 'broll_1s',
        'type': 'video',
        'filename': 'one_sec.mp4',
        'original_name': 'one_sec.mp4',
        'keywords': '',
        'metadata': {'duration': 1.0, 'width': 720, 'height': 1280, 'fps': 30}
    }
    p['assets'].append(broll_1s)
    plan = directed(p)
    # Set the candidate scene duration to 4.0s
    candidate_idx = 1 if len(plan['storyboard']) > 2 else 0
    plan['storyboard'][candidate_idx]['duration'] = 4.0
    plan['storyboard'][candidate_idx]['timeline_start'] = 0.0
    if len(plan['storyboard']) > candidate_idx + 1:
        plan['storyboard'][candidate_idx + 1]['timeline_start'] = 4.0

    original_length = length(plan)
    res = apply_visual_assets(plan, 'Giới thiệu', broll_asset_ids=['broll_1s'])

    # Find the B-roll scene
    broll_scene = next(s for s in res['storyboard'] if s.get('visual_asset_id') == 'broll_1s')
    assert broll_scene['duration'] == 1.0
    assert broll_scene['scene_type'] == 'broll'

    # Find the tail scene immediately following
    b_idx = res['storyboard'].index(broll_scene)
    tail_scene = res['storyboard'][b_idx + 1]
    assert tail_scene['duration'] == pytest.approx(3.0)
    assert tail_scene['scene_type'] == 'talking_head'
    assert tail_scene['timeline_start'] == broll_scene['timeline_start'] + 1.0

    # Total duration unchanged
    assert length(res) == pytest.approx(original_length)
    validate(res, res['assets'])


def test_broll_near_end_source_in_handled_safely(media):
    """When B-roll source_in is near the end of the asset, available duration is calculated correctly."""
    p = new_project(media)['edit_plan']
    # 5-second video with source_in at 4.2s -> only 0.8s available
    broll_tail = {
        'id': 'broll_tail',
        'type': 'video',
        'filename': 'tail.mp4',
        'original_name': 'tail.mp4',
        'source_in': 4.2,
        'keywords': '',
        'metadata': {'duration': 5.0, 'width': 720, 'height': 1280, 'fps': 30}
    }
    p['assets'].append(broll_tail)
    plan = directed(p)
    res = apply_visual_assets(plan, 'Giới thiệu', broll_asset_ids=['broll_tail'])

    b_scene = next(s for s in res['storyboard'] if s.get('visual_asset_id') == 'broll_tail')
    assert b_scene['visual_source_in'] == 4.2
    assert b_scene['duration'] == pytest.approx(0.8)
    # visual_source_in + duration <= metadata.duration
    assert b_scene['visual_source_in'] + b_scene['duration'] <= 5.0 + 1e-4
    validate(res, res['assets'])


def test_both_images_and_broll_do_not_cross_contaminate_keywords(media):
    """When both images and B-roll are provided with distinct keywords,
    each asset matches its own keyword domain independently.
    """
    p = new_project(media, True)['edit_plan']
    img_asset = next(a for a in p['assets'] if a['type'] == 'image')
    img_asset['keywords'] = 'khu vườn'

    broll_asset = {
        'id': 'broll_tech',
        'type': 'video',
        'filename': 'tech.mp4',
        'original_name': 'tech.mp4',
        'keywords': 'trợ lý',
        'metadata': {'duration': 10.0, 'width': 720, 'height': 1280, 'fps': 30}
    }
    p['assets'].append(broll_asset)
    plan = directed(p)

    # Provide explicit 4 scenes so interior has candidates for both
    plan['storyboard'] = [
        {'scene_id': 'sc0', 'scene_type': 'talking_head', 'timeline_start': 0.0, 'duration': 1.0, 'source_in': 0.0, 'transcript_meaning': 'Chào mừng các bạn.'},
        {'scene_id': 'sc1', 'scene_type': 'talking_head', 'timeline_start': 1.0, 'duration': 1.0, 'source_in': 1.0, 'transcript_meaning': 'Khu vườn nhà xanh mát rực rỡ.'},
        {'scene_id': 'sc2', 'scene_type': 'talking_head', 'timeline_start': 2.0, 'duration': 1.0, 'source_in': 2.0, 'transcript_meaning': 'Trợ lý AI hỗ trợ tự động hóa.'},
        {'scene_id': 'sc3', 'scene_type': 'talking_head', 'timeline_start': 3.0, 'duration': 1.0, 'source_in': 3.0, 'transcript_meaning': 'Cảm ơn và hẹn gặp lại.'},
    ]

    res = apply_visual_assets(
        plan,
        'Giới thiệu',
        image_asset_ids=[img_asset['id']],
        broll_asset_ids=['broll_tech']
    )
    # Image must be matched to garden speech
    img_scene = next(s for s in res['storyboard'] if s.get('visual_asset_id') == img_asset['id'])
    assert 'vườn' in img_scene.get('transcript_meaning', '').lower()

    # B-roll must be matched to assistant speech
    broll_scene = next(s for s in res['storyboard'] if s.get('visual_asset_id') == 'broll_tech')
    assert 'trợ lý' in broll_scene.get('transcript_meaning', '').lower()
    validate(res, res['assets'])


def test_real_mp4_render_broll_with_two_distinct_video_sources(media, tmp_path):
    """Real render test: Renders an MP4 using red source video (media[0]) and green B-roll video (media[1]).
    Verifies that the green B-roll actually appears in the rendered frames without altering voice or duration.
    """
    proj = new_project(media)
    # Upload media[1] (green video 2.0s) as B-roll asset
    green_video = media[1]
    with green_video.open('rb') as f:
        res = client.post(f'/api/projects/{proj["id"]}/upload', files={'file': ('green_broll.mp4', f)}, data={'role': 'broll', 'keywords': ''}).json()
    broll_id = res['edit_plan']['assets'][-1]['id']

    # Update transcript on scene to allow B-roll assignment
    proj = client.get(f'/api/projects/{proj["id"]}').json()
    aid = proj['video']['asset_id']
    proj['edit_plan']['subtitles'] = [{'id': 's1', 'asset_id': aid, 'start': 0, 'end': 4, 'text': 'Khám phá video thực tế.'}]
    proj['edit_plan']['recognition_subtitles'] = copy.deepcopy(proj['edit_plan']['subtitles'])
    main.save_project(proj['id'], proj)

    # Export video with B-roll selected
    resp = client.post(f'/api/projects/{proj["id"]}/make-video', json={'broll_asset_ids': [broll_id], 'style_preset': 'explainer'})
    assert resp.status_code == 200, resp.text

    result = client.get(f'/api/projects/{proj["id"]}').json()
    assert result['job']['status'] == 'succeeded', result['job']

    output_path = main.OUTPUTS_DIR / result['output_path'].split('/')[-1]
    meta = probe(output_path)
    assert meta['has_audio']
    assert meta['duration'] == pytest.approx(4.0, abs=0.1)

    # Sample video pixels using ffmpeg:
    # Source is red (media[0]), B-roll is green (media[1]).
    # We find which scene is B-roll to know when green appears.
    storyboard = result['edit_plan']['storyboard']
    b_scene = next((s for s in storyboard if s.get('scene_type') == 'broll'), None)
    assert b_scene is not None

    b_time = b_scene['timeline_start'] + b_scene['duration'] / 2.0
    # Probe frame at B-roll time: green pixels must dominate (G > 120, R < 80)
    raw_green = subprocess.run([
        'ffmpeg', '-v', 'error', '-ss', str(b_time), '-i', str(output_path),
        '-frames:v', '1', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'
    ], check=True, capture_output=True).stdout
    import numpy as np
    frame = np.frombuffer(raw_green, dtype=np.uint8).reshape((1280, 720, 3))
    # Check central area where video is shown
    center_patch = frame[400:800, 200:520]
    green_count = int(np.sum((center_patch[:, :, 1] > 100) & (center_patch[:, :, 0] < 80)))
    assert green_count > 1000, "Green B-roll video was not visible in rendered output."
