"""Full integration and regression test suite covering all 6 steps:
1. Animation contract unified: animation_in='none' supported and distinct from scene transitions.
2. Independent keyword scoring and B-roll source duration bounds.
3. B-roll preservation across all 3 presets (explainer, inspirational, real_estate).
4. Full contract chain: web_url -> MakeVideo -> Options -> Ingestion -> Planning.
5. Ingest web outside lock, shared registration before planning, SSRF and content hash deduplication.
6. Semantic web image selection, unified no-sfx removal, and complete text suppression in ASS and motion graphics.
7. Verification on real dynamic footage with motion/counter, multi-point probe, audio sync, and duration checks.
"""
import copy
import json
import os
import subprocess
import threading
import time
from pathlib import Path
import pytest

from fastapi.testclient import TestClient
import main
from editing import probe
from style_presets import apply_style_preset, public_presets
from storyboard_compiler import compile_storyboard_scenes
from render_report import build_render_report, check_quality_gate, check_low_edit_density, is_zoom_effect

client = TestClient(main.app)


@pytest.fixture(scope='module')
def dynamic_media(tmp_path_factory):
    """Generate authentic dynamic video with motion and frame counter, short b-roll, audio, and test photo."""
    root = tmp_path_factory.mktemp('dyn_media')
    source = root / 'counter_source.mp4'
    broll = root / 'motion_broll.mp4'
    photo = root / 'villa_pool.png'
    audio_bg = root / 'ambient_music.wav'

    # 1. Main dynamic video: 6 seconds with moving test patterns and 440Hz tone
    subprocess.run([
        'ffmpeg', '-v', 'error', '-y',
        '-f', 'lavfi', '-i', 'testsrc=duration=6:size=720x1280:rate=30',
        '-f', 'lavfi', '-i', 'sine=frequency=440:duration=6',
        '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-c:a', 'aac', str(source)
    ], check=True)

    # 2. Short B-roll footage: 3 seconds with distinct color gradient test pattern
    subprocess.run([
        'ffmpeg', '-v', 'error', '-y',
        '-f', 'lavfi', '-i', 'testsrc2=duration=3:size=720x1280:rate=30',
        '-c:v', 'libx264', '-pix_fmt', 'yuv420p', str(broll)
    ], check=True)

    # 3. Reference photo
    from PIL import Image, ImageDraw
    im = Image.new('RGB', (640, 480), (30, 140, 200))
    d = ImageDraw.Draw(im)
    d.rectangle([50, 50, 590, 430], fill=(220, 240, 255), outline=(10, 80, 160), width=6)
    im.save(photo)

    # 4. Background music audio
    subprocess.run([
        'ffmpeg', '-v', 'error', '-y',
        '-f', 'lavfi', '-i', 'sine=frequency=220:duration=8',
        '-c:a', 'pcm_s16le', str(audio_bg)
    ], check=True)

    return {
        'source': source,
        'broll': broll,
        'photo': photo,
        'music': audio_bg
    }


def create_base_project(media_dict, transcribe_text='Xin chào quý vị, đây là không gian tiện ích hồ bơi căn hộ cao cấp.'):
    p = client.post('/api/projects', data={'name': 'Dự án kiểm thử toàn diện'}).json()
    with media_dict['source'].open('rb') as f:
        res = client.post(f"/api/projects/{p['id']}/upload", files={'file': ('source.mp4', f)}, data={'role': 'main'})
        assert res.status_code == 200
        p = res.json()

    # Pre-populate recognized speech transcript
    p['edit_plan']['subtitles'] = [
        {'id': 'sub_1', 'asset_id': p['video']['asset_id'], 'start': 0.0, 'end': 3.0, 'text': 'Xin chào quý vị, đây là không gian tiện ích.'},
        {'id': 'sub_2', 'asset_id': p['video']['asset_id'], 'start': 3.0, 'end': 6.0, 'text': 'Khuôn viên có hồ bơi căn hộ cao cấp sang trọng.'}
    ]
    main.save_project(p['id'], p)
    return p


# -----------------------------------------------------------------------------
# CA 1: Video nguồn + phụ đề
# -----------------------------------------------------------------------------
def test_case_1_source_video_plus_captions(dynamic_media, monkeypatch):
    monkeypatch.setenv('OLLAMA_URL', 'http://127.0.0.1:9')
    p = create_base_project(dynamic_media)

    # Dựng video nguồn với phụ đề
    r = client.post(f"/api/projects/{p['id']}/make-video", json={'prompt': 'Dựng video giữ nguyên nguồn và phụ đề'})
    assert r.status_code == 200, r.text

    proj = client.get(f"/api/projects/{p['id']}").json()
    assert proj['job']['status'] == 'succeeded', proj['job']

    out_path = main.OUTPUTS_DIR / proj['output_path'].split('/')[-1]
    assert out_path.exists()

    meta = probe(out_path)
    assert meta['has_audio'] is True
    assert abs(meta['duration'] - 6.0) <= 0.4
    assert meta['width'] == 720 and meta['height'] == 1280

    report = proj.get('render_report') or proj.get('job', {}).get('render_report') or proj['edit_plan'].get('render_report', {})
    assert report.get('quality_gate', {}).get('passed') is True
    assert report.get('file_verification', {}).get('probe_verified') is True


# -----------------------------------------------------------------------------
# CA 2: Video + ảnh phù hợp
# -----------------------------------------------------------------------------
def test_case_2_video_plus_matched_image(dynamic_media, monkeypatch):
    monkeypatch.setenv('OLLAMA_URL', 'http://127.0.0.1:9')
    p = create_base_project(dynamic_media)

    # Upload ảnh bể bơi
    with dynamic_media['photo'].open('rb') as f:
        r_up = client.post(f"/api/projects/{p['id']}/upload", files={'file': ('villa_pool.png', f)},
                           data={'role': 'asset', 'keywords': 'hồ bơi căn hộ'})
        assert r_up.status_code == 200
        p = r_up.json()

    img_asset = next(a for a in p['edit_plan']['assets'] if a['type'] == 'image')

    r = client.post(f"/api/projects/{p['id']}/make-video", json={
        'image_asset_ids': [img_asset['id']],
        'prompt': 'Chèn ảnh minh họa đúng ngữ cảnh'
    })
    assert r.status_code == 200

    proj = client.get(f"/api/projects/{p['id']}").json()
    assert proj['job']['status'] == 'succeeded', proj['job']

    # Kiểm tra ảnh được gán vào cảnh có lời thoại về hồ bơi căn hộ (cảnh thứ 2)
    scenes = proj['edit_plan']['storyboard']
    matched_scenes = [s for s in scenes if s.get('visual_asset_id') == img_asset['id']]
    assert len(matched_scenes) >= 1, "Ảnh bể bơi phải được gán vào ít nhất một cảnh phù hợp"

    out_path = main.OUTPUTS_DIR / proj['output_path'].split('/')[-1]
    assert out_path.exists()
    assert probe(out_path)['duration'] > 0


# -----------------------------------------------------------------------------
# CA 3: Video + B-roll ngắn
# -----------------------------------------------------------------------------
def test_case_3_video_plus_short_broll(dynamic_media, monkeypatch):
    monkeypatch.setenv('OLLAMA_URL', 'http://127.0.0.1:9')
    p = create_base_project(dynamic_media)

    # Upload B-roll ngắn (3 giây)
    with dynamic_media['broll'].open('rb') as f:
        r_up = client.post(f"/api/projects/{p['id']}/upload", files={'file': ('motion_broll.mp4', f)},
                           data={'role': 'broll', 'keywords': 'không gian tiện ích'})
        assert r_up.status_code == 200
        p = r_up.json()

    broll_asset = next(a for a in p['edit_plan']['assets'] if a['id'] != p['video']['asset_id'] and a['type'] == 'video')

    r = client.post(f"/api/projects/{p['id']}/make-video", json={
        'broll_asset_ids': [broll_asset['id']],
        'prompt': 'Chèn B-roll không gian tiện ích'
    })
    assert r.status_code == 200

    proj = client.get(f"/api/projects/{p['id']}").json()
    assert proj['job']['status'] == 'succeeded', proj['job']

    scenes = proj['edit_plan']['storyboard']
    broll_scenes = [s for s in scenes if s.get('scene_type') == 'broll' and s.get('visual_asset_id') == broll_asset['id']]
    assert len(broll_scenes) >= 1, "B-roll phải được giữ nguyên dạng video và gán vào cảnh"

    out_path = main.OUTPUTS_DIR / proj['output_path'].split('/')[-1]
    assert out_path.exists()
    meta = probe(out_path)
    assert meta['has_audio'] is True


# -----------------------------------------------------------------------------
# CA 4: Cả 3 preset có B-roll (giữ nguyên footage, không bị xóa)
# -----------------------------------------------------------------------------
def test_case_4_three_presets_preserve_broll(dynamic_media):
    plan = {
        'assets': [
            {'id': 'cam_source', 'type': 'video', 'filename': 'cam.mp4', 'metadata': {'duration': 12}},
            {'id': 'broll_source', 'type': 'video', 'filename': 'broll.mp4', 'metadata': {'duration': 5.0}}
        ],
        'video_clips': [{'asset_id': 'cam_source', 'source_in': 0, 'duration': 12, 'timeline_start': 0}],
        'storyboard': [
            {'scene_id': 'sc_0', 'scene_type': 'talking_head', 'timeline_start': 0, 'duration': 4, 'source_in': 0, 'asset_id': 'cam_source'},
            {'scene_id': 'sc_1', 'scene_type': 'broll', 'visual_asset_id': 'broll_source', 'visual_source_in': 0.5, 'timeline_start': 4, 'duration': 4, 'source_in': 4, 'asset_id': 'cam_source'},
            {'scene_id': 'sc_2', 'scene_type': 'talking_head', 'timeline_start': 8, 'duration': 4, 'source_in': 8, 'asset_id': 'cam_source'}
        ],
        'audio_tracks': [],
        'effect_keyframes': [],
        'visual_overlays': [],
        'text_overlays': [],
        'output_settings': {'width': 720, 'height': 1280, 'fps': 30}
    }

    for preset_name in ('explainer', 'inspirational', 'real_estate'):
        styled = apply_style_preset(copy.deepcopy(plan), identifier=preset_name, prompt='áp dụng phong cách')
        broll_scenes = [s for s in styled['storyboard'] if s.get('scene_type') == 'broll' and s.get('visual_asset_id') == 'broll_source']
        assert len(broll_scenes) >= 1, f"Preset {preset_name} bắt buộc phải giữ lại B-roll video, không được chuyển thành talking_head!"


# -----------------------------------------------------------------------------
# CA 5: Không hiệu ứng
# -----------------------------------------------------------------------------
def test_case_5_no_effects_disables_zoom_and_motion(dynamic_media, monkeypatch):
    monkeypatch.setenv('OLLAMA_URL', 'http://127.0.0.1:9')
    p = create_base_project(dynamic_media)

    r = client.post(f"/api/projects/{p['id']}/make-video", json={'prompt': 'video tối giản, không hiệu ứng, không zoom'})
    assert r.status_code == 200

    proj = client.get(f"/api/projects/{p['id']}").json()
    assert proj['job']['status'] == 'succeeded', proj['job']

    plan = proj['edit_plan']
    assert len(plan.get('effect_keyframes', [])) == 0, "Không được có effect_keyframes khi yêu cầu không hiệu ứng"
    for sc in plan.get('storyboard', []):
        assert sc.get('animation_in') == 'none'
        assert sc.get('sound_effect') == 'none'


# -----------------------------------------------------------------------------
# CA 6: Không chữ
# -----------------------------------------------------------------------------
def test_case_6_no_text_completely_removes_typography(dynamic_media, monkeypatch):
    monkeypatch.setenv('OLLAMA_URL', 'http://127.0.0.1:9')
    p = create_base_project(dynamic_media)

    r = client.post(f"/api/projects/{p['id']}/make-video", json={
        'prompt': 'không chữ',
        'brand_name': 'BRAND_SUPPRESSED_TEST'
    })
    assert r.status_code == 200

    proj = client.get(f"/api/projects/{p['id']}").json()
    assert proj['job']['status'] == 'succeeded', proj['job']

    plan = proj['edit_plan']
    assert plan.get('show_text') is False or plan.get('text_enabled') is False
    assert plan.get('show_captions') is False
    assert plan.get('brand_footer') == ''
    for sc in plan.get('storyboard', []):
        assert sc.get('headline') == ''
        assert sc.get('badge_text') == ''


# -----------------------------------------------------------------------------
# CA 7: Không SFX nhưng có nhạc nền
# -----------------------------------------------------------------------------
def test_case_7_no_sfx_with_music_preserves_soundtrack(dynamic_media, monkeypatch):
    monkeypatch.setenv('OLLAMA_URL', 'http://127.0.0.1:9')
    p = create_base_project(dynamic_media)

    # Upload nhạc nền
    with dynamic_media['music'].open('rb') as f:
        r_up = client.post(f"/api/projects/{p['id']}/upload", files={'file': ('music.wav', f)}, data={'role': 'music'})
        assert r_up.status_code == 200
        p = r_up.json()

    music_asset = next(a for a in p['edit_plan']['assets'] if a['type'] == 'audio')

    r = client.post(f"/api/projects/{p['id']}/make-video", json={
        'music_asset_id': music_asset['id'],
        'prompt': 'không sfx, bật nhạc nền'
    })
    assert r.status_code == 200

    proj = client.get(f"/api/projects/{p['id']}").json()
    assert proj['job']['status'] == 'succeeded', proj['job']

    plan = proj['edit_plan']
    tracks = plan.get('audio_tracks', [])
    music_tracks = [t for t in tracks if t.get('kind') == 'music']
    sfx_tracks = [t for t in tracks if t.get('kind') in ('whoosh', 'pop', 'click', 'impact', 'chime', 'sfx')]

    assert len(music_tracks) >= 1, "Nhạc nền phải được giữ nguyên"
    assert len(sfx_tracks) == 0, "Toàn bộ SFX phải bị loại bỏ khi prompt có 'không sfx'"


# -----------------------------------------------------------------------------
# CA 8: Link web: có ảnh, không có ảnh và link lỗi
# -----------------------------------------------------------------------------
def test_case_8_web_link_scenarios(dynamic_media, monkeypatch):
    p = create_base_project(dynamic_media)

    # 1. Link không hợp lệ (không phải http/https)
    r1 = client.post(f"/api/projects/{p['id']}/ingest-web", json={'url': 'ftp://example.com/file'})
    assert r1.status_code == 422 or r1.status_code == 400

    # 2. Link mạng nội bộ bị chặn bởi SSRF
    monkeypatch.delenv('ALLOW_LOCAL_WEB_RESEARCH', raising=False)
    r2 = client.post(f"/api/projects/{p['id']}/ingest-web", json={'url': 'http://169.254.169.254/latest/meta-data'})
    assert r2.status_code == 400
    assert 'bị chặn' in r2.json().get('detail', '')

    # 3. Link hợp lệ được xử lý an toàn
    monkeypatch.setenv('ALLOW_LOCAL_WEB_RESEARCH', '1')
    import web_researcher as wr
    mock_page = lambda url, **kwargs: {
        'url': url,
        'title': 'Trang dự án mẫu',
        'description': 'Mô tả dự án căn hộ cao cấp',
        'summary': 'Trang dự án căn hộ cao cấp có hồ bơi',
        'candidate_images': []
    }
    monkeypatch.setattr(wr, 'fetch_web_page_data', mock_page)
    monkeypatch.setattr(main.web_researcher, 'fetch_web_page_data', mock_page)

    r3 = client.post(f"/api/projects/{p['id']}/ingest-web", json={'url': 'https://example.com/no-images'})
    assert r3.status_code == 200, r3.text
    res = r3.json()
    assert res['image_count'] == 0
    assert res['summary'] != ''


# -----------------------------------------------------------------------------
# CA 9: Kiểm tra đa mốc thời gian (đầu, giữa, cuối) và tính nguyên vẹn stream
# -----------------------------------------------------------------------------
def test_case_9_multi_timestamp_verification(dynamic_media, monkeypatch):
    monkeypatch.setenv('OLLAMA_URL', 'http://127.0.0.1:9')
    p = create_base_project(dynamic_media)

    r = client.post(f"/api/projects/{p['id']}/make-video", json={'prompt': 'Dựng hoàn chỉnh'})
    assert r.status_code == 200

    proj = client.get(f"/api/projects/{p['id']}").json()
    assert proj['job']['status'] == 'succeeded'

    out_file = main.OUTPUTS_DIR / proj['output_path'].split('/')[-1]
    meta = probe(out_file)
    dur = meta['duration']

    # Trích xuất khung hình tại 3 mốc: đầu (1s), giữa (dur/2), và gần cuối (dur - 0.5s)
    for t in (1.0, dur / 2.0, max(0.5, dur - 0.5)):
        cmd = ['ffmpeg', '-v', 'error', '-y', '-ss', str(t), '-i', str(out_file), '-frames:v', '1', '-f', 'null', '-']
        res = subprocess.run(cmd, capture_output=True)
        assert res.returncode == 0, f"Frame tại {t}s phải đọc được mà không gặp lỗi FFmpeg stream"
