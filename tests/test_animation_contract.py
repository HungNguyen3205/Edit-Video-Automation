"""Tests verifying the animation contract across presets, schema, validator, and motion."""
import copy
import subprocess
import threading
import pytest

from test_pipeline import client, media, new_project
from style_presets import apply_style_preset, apply_user_overrides
from motion_style import apply_motion_style
import automatic_director
from automatic_director import fallback_direction, SceneChoice
from ai_director import StoryboardScene
from editing import length, probe, validate
import main


def directed(plan):
    return fallback_direction(plan, 'Giữ nguyên lời nói', threading.Event(), 'TEST_NO_MODEL')


def test_reproduce_no_effects_passes_validation(media):
    """Reproduction test: applying 'Không hiệu ứng' sets animation_in='none'.
    Before the fix, editing.validate() rejected animation_in='none' with
    'Chuyển động cảnh không hợp lệ.' Now it must pass validate().
    """
    p = directed(new_project(media)['edit_plan'])
    r = apply_style_preset(p, 'inspirational', 'Không hiệu ứng')
    assert any(s.get('animation_in') == 'none' for s in r['storyboard'])
    validated = validate(r, r['assets'])
    assert validated is not None


def test_schemas_accept_animation_in_none():
    """Ensure SceneChoice and StoryboardScene schemas accept 'none' alongside pop_in, slide_up, fade."""
    sc_auto = SceneChoice(
        scene_index=0,
        scene_type='explainer_card',
        headline='TIÊU ĐỀ',
        badge_text='MINH HỌA',
        graphic_kind='chat',
        graphic_title='TIÊU ĐỀ THẺ',
        graphic_items=['Ý 1', 'Ý 2'],
        sound_effect='none',
        caption_text='Lời nói',
        animation_in='none',
        zoom_scale=1.0,
    )
    assert sc_auto.animation_in == 'none'

    sc_ai = StoryboardScene(
        scene_id='scene_1',
        scene_type='explainer_card',
        timeline_start=0.0,
        duration=3.0,
        headline='TIÊU ĐỀ AI',
        animation_in='none',
        animation_out='none',
    )
    assert sc_ai.animation_in == 'none'
    assert sc_ai.animation_out == 'none'


def test_no_effects_disables_motion_without_losing_source_media_or_speech(media):
    """Opting out of effects turns off zoom, animation, photo zoom, and transitions,
    while preserving original video clips, speech/subtitles, and chosen image assets.
    """
    proj = new_project(media, True)
    plan = directed(proj['edit_plan'])
    image_asset = next(a for a in plan['assets'] if a['type'] == 'image')
    # Assign an authentic photo to one scene
    plan['storyboard'][0]['visual_asset_id'] = image_asset['id']

    original_clips = copy.deepcopy(plan['video_clips'])
    original_subs = copy.deepcopy(plan['subtitles'])
    original_speech = [s.get('transcript_meaning') for s in plan['storyboard']]

    r = apply_style_preset(plan, 'inspirational', 'Không hiệu ứng')

    # Source clips, subtitles, and speech remain intact
    assert r['video_clips'] == original_clips
    assert r['subtitles'] == original_subs
    for i, sc in enumerate(r['storyboard']):
        if original_speech[i]:
            assert sc.get('transcript_meaning') == original_speech[i]

    # The chosen image asset is NOT deleted by 'no effects'
    assert r['storyboard'][0].get('visual_asset_id') == image_asset['id']

    # Effects are cleanly disabled
    assert r['effect_keyframes'] == []
    for sc in r['storyboard']:
        assert sc['animation_in'] == 'none'
        assert sc['animation_out'] == 'none'
        assert sc['sound_effect'] == 'none'
        assert sc['sound_volume'] == 0
        motion = sc.get('motion', {})
        assert motion.get('animate') is False
        assert motion.get('photo_zoom') == 0
        assert motion.get('transition_seconds') == 0
        assert motion.get('stagger') is False

    validate(r, r['assets'])


def test_no_zoom_distinguished_from_no_effects(media):
    """'Không zoom' must only suppress camera/photo zooms without disabling
    animations, sound effects, or motion.animate.
    """
    p = directed(new_project(media)['edit_plan'])
    r_zoom = apply_style_preset(p, 'inspirational', 'Không zoom')

    # Zooms are suppressed
    assert not any(e.get('scale', 1.0) != 1.0 or 'zoom' in str(e.get('id', '')) for e in r_zoom['effect_keyframes'])
    for sc in r_zoom['storyboard']:
        if 'motion' in sc:
            assert sc['motion'].get('photo_zoom') == 0

    # BUT animation and sound effects remain active
    assert any(s.get('animation_in') != 'none' for s in r_zoom['storyboard'])
    assert any(s.get('sound_effect') != 'none' for s in r_zoom['storyboard'])
    assert any(s.get('motion', {}).get('animate') is True for s in r_zoom['storyboard'])

    validate(r_zoom, r_zoom['assets'])


@pytest.mark.parametrize('preset_id', ['explainer', 'inspirational', 'real_estate'])
def test_all_three_presets_handle_no_effects_consistently(media, preset_id):
    """All three presets must produce valid plans with animation_in='none' when 'không hiệu ứng' is requested."""
    p = directed(new_project(media)['edit_plan'])
    r = apply_style_preset(p, preset_id, 'Không hiệu ứng')
    assert all(s.get('animation_in') == 'none' for s in r['storyboard'])
    assert all(s.get('motion', {}).get('animate') is False for s in r['storyboard'])
    assert r['effect_keyframes'] == []
    validate(r, r['assets'])


@pytest.mark.parametrize('motion_preset', ['clean', 'dynamic_explainer'])
def test_motion_styles_handle_no_effects_consistently(media, motion_preset):
    """Both clean and dynamic_explainer motion styles must set animation_in='none' and animate=False."""
    p = directed(new_project(media)['edit_plan'])
    r = apply_motion_style(p, motion_preset, 'Không hiệu ứng')
    assert all(s.get('animation_in') == 'none' for s in r['storyboard'])
    assert all(s.get('motion', {}).get('animate') is False for s in r['storyboard'])
    validate(r, r['assets'])


def test_idempotency_of_normalization(media):
    """Running normalization multiple times must produce identical results."""
    p = directed(new_project(media)['edit_plan'])
    once = apply_user_overrides(p, 'Không hiệu ứng, không zoom')
    twice = apply_user_overrides(once, 'Không hiệu ứng, không zoom')
    assert once == twice

    preset_once = apply_style_preset(p, 'real_estate', 'Không hiệu ứng')
    preset_twice = apply_style_preset(preset_once, 'real_estate', 'Không hiệu ứng')
    assert preset_once == preset_twice


def test_make_video_with_no_effects_renders_real_mp4(media, monkeypatch):
    """End-to-end integration: make-video with 'Không hiệu ứng' exports a real MP4 with valid video and audio."""
    p = new_project(media)
    aid = p['video']['asset_id']
    p['edit_plan']['subtitles'] = [{'id': 'speech', 'asset_id': aid, 'start': 0, 'end': 4, 'text': 'Giới thiệu căn nhà vườn.'}]
    p['edit_plan']['recognition_subtitles'] = copy.deepcopy(p['edit_plan']['subtitles'])
    main.save_project(p['id'], p)

    monkeypatch.setattr(main, 'recognition_engine', lambda: 'faster_whisper')
    monkeypatch.setattr(main, 'transcribe', lambda *args: copy.deepcopy(p['edit_plan']['subtitles']))
    monkeypatch.setattr(automatic_director, 'chat', lambda *args: (_ for _ in ()).throw(main.AIError('AI_CONNECTION', 'Test fallback')))

    response = client.post(f'/api/projects/{p["id"]}/make-video', json={'style_preset': 'inspirational', 'prompt': 'Không hiệu ứng'})
    assert response.status_code == 200, response.text

    result = client.get(f'/api/projects/{p["id"]}').json()
    assert result['job']['status'] == 'succeeded', result['job']

    # Check edit_plan storyboard animation properties
    storyboard = result['edit_plan']['storyboard']
    assert all(s.get('animation_in') == 'none' for s in storyboard)

    # Check output MP4 file with ffmpeg probe
    output = main.OUTPUTS_DIR / result['output_path'].split('/')[-1]
    meta = probe(output)
    assert (meta['width'], meta['height']) == (720, 1280)
    assert meta['has_audio']
    assert meta['duration'] == pytest.approx(4, abs=0.1)

    # Validate file integrity with ffmpeg
    subprocess.run(['ffmpeg', '-v', 'error', '-xerror', '-i', str(output), '-f', 'null', '-'], check=True, capture_output=True)
