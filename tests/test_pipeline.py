import copy
import os
import subprocess
import tempfile
from pathlib import Path

os.environ['VIDEO_DATA_DIR'] = tempfile.mkdtemp(prefix='studio-tests-')
import pytest
from fastapi.testclient import TestClient
import main
from editing import auto_plan, mapped_subtitles, probe

client = TestClient(main.app)

@pytest.fixture(scope='module')
def media(tmp_path_factory):
    root = tmp_path_factory.mktemp('media')
    source = root / 'source.mp4'
    silent = root / 'silent.mp4'
    image = root / 'blue.png'
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'lavfi', '-i', 'color=red:s=240x320:r=30:d=4', '-f', 'lavfi', '-i', 'sine=frequency=440:duration=4', '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-c:a', 'aac', str(source)], check=True)
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'lavfi', '-i', 'color=green:s=320x240:r=30:d=2', '-c:v', 'libx264', '-pix_fmt', 'yuv420p', str(silent)], check=True)
    from PIL import Image
    Image.new('RGB', (100, 100), 'blue').save(image)
    return source, silent, image


def new_project(media, include_image=False):
    p = client.post('/api/projects', data={'name': 'Kiểm thử'}).json()
    for file in [media[0]] + ([media[2]] if include_image else []):
        with file.open('rb') as f:
            response = client.post(f'/api/projects/{p["id"]}/upload', files={'file': (file.name, f)}, data={'role': 'main' if file == media[0] else 'asset'})
            assert response.status_code == 200, response.text
            p = response.json()
    return p


def save(p, plan):
    res = client.post(f'/api/projects/{p["id"]}/edit_plan', json={'revision': p['revision'], 'plan': plan})
    assert res.status_code == 200, res.text
    return res.json()


def get_result(p, endpoint='export', **options):
    response = client.post(f'/api/projects/{p["id"]}/{endpoint}', json=options)
    assert response.status_code == 200, response.text
    latest = client.get(f'/api/projects/{p["id"]}').json()
    assert latest['job']['status'] == 'succeeded', latest['job']
    return latest, main.OUTPUTS_DIR / Path(latest['preview_path' if options.get('preview') else 'output_path']).name


def rgb_at(path, seconds, x, y):
    data = subprocess.run(['ffmpeg', '-v', 'error', '-ss', str(seconds), '-i', str(path), '-frames:v', '1', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'], capture_output=True, check=True).stdout
    w = probe(path)['width']
    return tuple(data[(y*w+x)*3:(y*w+x)*3+3])


def test_video_only_auto_edit_no_image_requirement(media):
    p = new_project(media)
    result, output = get_result(p, 'auto-edit', transcribe=False, headline='DANAVA – Câu chuyện của bạn')
    meta = probe(output)
    assert (meta['width'], meta['height']) == (240, 320)
    assert meta['has_audio'] and abs(meta['duration'] - 4) < .1
    assert result['edit_plan']['effect_keyframes']
    assert result['edit_plan']['text_overlays'][0]['text'].startswith('DANAVA')
    assert result['job']['warnings']  # truthful missing-caption limitation
    # Actual burnt title changes source pixels in upper region.
    pixel = rgb_at(output, 1, 120, 52)
    assert pixel != (253, 0, 0)


def test_timed_image_overlay_is_absent_before_and_after(media):
    p = new_project(media, True)
    plan = p['edit_plan']
    image = next(a for a in plan['assets'] if a['type'] == 'image')
    plan['visual_overlays'] = [{'id': 'ov', 'asset_id': image['id'], 'timeline_start': 1, 'duration': 1, 'x': 0, 'y': 0, 'width': .5, 'mode': 'pip'}]
    p = save(p, plan)
    _, output = get_result(p)
    before, during, after = [rgb_at(output, t, 10, 10) for t in (.5, 1.5, 2.5)]
    assert before[0] > 200 and before[2] < 20
    assert during[2] > 200 and during[0] < 20
    assert after[0] > 200 and after[2] < 20


def test_multiclip_concat_and_silent_audio(media):
    p = new_project(media)
    with media[1].open('rb') as f:
        p = client.post(f'/api/projects/{p["id"]}/upload', files={'file': ('silent.mp4', f)}, data={'role': 'asset'}).json()
    plan = p['edit_plan']
    plan['video_clips'][0]['duration'] = 1
    a = plan['assets'][-1]
    plan['video_clips'].append({'id': 'second', 'asset_id': a['id'], 'source_in': 0, 'duration': 1, 'timeline_start': 99})
    p = save(p, plan)
    assert p['edit_plan']['video_clips'][1]['timeline_start'] == 1
    _, output = get_result(p)
    assert abs(probe(output)['duration'] - 2) < .1
    assert rgb_at(output, .5, 120, 160)[0] > 200
    assert rgb_at(output, 1.5, 120, 160)[1] > 90


def test_subtitles_remap_after_trim(media):
    p = new_project(media)
    plan = p['edit_plan']
    plan['video_clips'][0].update(source_in=1, duration=2)
    plan['subtitles'] = [{'id': 'sub', 'start': .5, 'end': 2, 'text': 'Tiếng Việt đúng dấu', 'asset_id': p['video']['asset_id']}]
    p = save(p, plan)
    mapped = mapped_subtitles(p['edit_plan'])
    assert mapped[0]['start'] == 0 and mapped[0]['end'] == 1
    _, output = get_result(p)
    assert abs(probe(output)['duration'] - 2) < .1
    srt = client.get(f'/api/projects/{p["id"]}/subtitles.srt').text
    assert '00:00:00,000 --> 00:00:01,000' in srt
    # Caption box and text affect bottom pixels only during its mapped interval.
    assert rgb_at(output, .5, 120, 290) != rgb_at(output, 1.5, 120, 290)


def test_video_overlay_shifted_to_timeline_start(media):
    p = new_project(media)
    with media[1].open('rb') as f:
        p = client.post(f'/api/projects/{p["id"]}/upload', files={'file': ('silent.mp4', f)}, data={'role': 'asset'}).json()
    plan = p['edit_plan']
    plan['visual_overlays'] = [{'id': 'ov', 'asset_id': plan['assets'][-1]['id'], 'timeline_start': 2, 'duration': 1, 'source_in': .2, 'mode': 'full'}]
    p = save(p, plan)
    _, output = get_result(p)
    assert rgb_at(output, 1, 120, 160)[0] > 200
    assert rgb_at(output, 2.5, 120, 160)[1] > 90
    assert rgb_at(output, 3.5, 120, 160)[0] > 200


def test_reject_invalid_trim_unowned_assets_and_stale_revision(media):
    p = new_project(media)
    plan = copy.deepcopy(p['edit_plan'])
    plan['video_clips'][0]['duration'] = 10
    assert client.post(f'/api/projects/{p["id"]}/edit_plan', json={'plan': plan, 'revision': p['revision']}).status_code == 422
    plan = copy.deepcopy(p['edit_plan'])
    plan['assets'][0]['filename'] = '../../etc/passwd'
    saved = save(p, plan)
    assert saved['edit_plan']['assets'][0]['filename'] != '../../etc/passwd'
    assert client.post(f'/api/projects/{p["id"]}/edit_plan', json={'plan': plan, 'revision': p['revision']}).status_code == 409


def test_srt_import_and_preview(media):
    p = new_project(media)
    response = client.post(f'/api/projects/{p["id"]}/subtitles/import', files={'file': ('demo.srt', '1\n00:00:00,000 --> 00:00:02,000\nXin chào Đà Nẵng\n'.encode('utf-8'))})
    assert response.status_code == 200, response.text
    p = response.json()
    _, output = get_result(p, preview=True)
    assert output.exists() and probe(output)['duration'] > 0


def test_auto_rerun_keeps_manual_and_uses_keywords(media):
    p = new_project(media, True)
    plan = p['edit_plan']
    plan['text_overlays'] = [{'id': 'manual', 'origin': 'manual', 'text': 'Giữ tôi', 'timeline_start': 0, 'duration': 1}]
    plan['assets'][-1]['keywords'] = 'ứng dụng'
    plan['subtitles'] = [{'id': 's', 'start': 1, 'end': 3, 'text': 'Đây là ứng dụng DANAVA', 'asset_id': p['video']['asset_id']}]
    first = auto_plan(plan)
    second = auto_plan(first)
    assert len(first['effect_keyframes']) == len(second['effect_keyframes'])
    assert next(t for t in second['text_overlays'] if t['id'] == 'manual')['text'] == 'Giữ tôi'
    assert second['visual_overlays'][0]['timeline_start'] == 1


def test_missing_whisper_reports_actionable_error(media, monkeypatch):
    p = new_project(media)
    original = main.importlib.util.find_spec
    monkeypatch.setattr(main.importlib.util, 'find_spec', lambda name: None if name == 'whisper' else original(name))
    result = client.post(f'/api/projects/{p["id"]}/auto-edit', json={'transcribe': True})
    assert result.status_code == 422 and 'requirements-ai' in result.json()['detail']


def test_upload_validation(media):
    p = new_project(media)
    assert client.post(f'/api/projects/{p["id"]}/upload', files={'file': ('broken.mp4', b'not a video')}).status_code == 422
    assert client.get('/api/projects/not-a-uuid').status_code == 400


def test_trim_after_auto_edit_clamps_generated_effects(media):
    p = new_project(media)
    p, _ = get_result(p, 'auto-edit', transcribe=False, headline='Tiêu đề')
    plan = p['edit_plan']
    plan['video_clips'][0]['duration'] = 1.5
    p = save(p, plan)
    assert all(x['timeline_start'] + x['duration'] <= 1.5 for key in ('effect_keyframes', 'text_overlays') for x in p['edit_plan'][key])
    _, output = get_result(p)
    assert abs(probe(output)['duration'] - 1.5) < .1


def test_original_mvp_project_migrates_without_losing_source(media):
    p = new_project(media, True)
    old = copy.deepcopy(p)
    old['edit_plan']['schema_version'] = 1
    for a in old['edit_plan']['assets']:
        del a['metadata']
    old['edit_plan']['visual_overlays'] = [{'id': 'legacy', 'asset_id': old['edit_plan']['assets'][-1]['id'], 'timeline_start': 0, 'duration': 1, 'x': 50, 'y': 50}]
    main.save_project(p['id'], old)
    restored = client.get(f'/api/projects/{p["id"]}').json()
    assert restored['edit_plan']['schema_version'] == 2
    assert restored['video']['asset_id'] == p['video']['asset_id']
    assert restored['edit_plan']['assets'][0]['metadata']['has_audio']
    assert 0 <= restored['edit_plan']['visual_overlays'][0]['x'] <= 1
    _, output = get_result(restored)
    assert output.exists()
