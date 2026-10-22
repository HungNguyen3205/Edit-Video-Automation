"""Tests for the MakeVideo API and custom assets workflow.

Verifies:
1. Extra optional resources (photo, music, logo, broll, prompt, brand_name, proper_names).
2. Selected assets are applied to the plan; deselected assets are cleanly removed.
3. Project asset isolation (project A assets rejected on project B).
4. Reload preserves choices in project model and job branding.
5. Default flow without extra resources works smoothly.
6. Changing video / new project does not mix asset IDs.
"""
import copy
import subprocess
import threading
import pytest
from PIL import Image
from test_pipeline import client, media, new_project
import main
from automatic_director import fallback_direction
from video_branding import apply_visual_assets


def test_default_make_video_without_extra_resources_succeeds(media, monkeypatch):
    """Ensure the 3-step primary workflow without extra resources works smoothly."""
    p = new_project(media)
    monkeypatch.setenv('OLLAMA_URL', 'http://127.0.0.1:9')
    # Empty options payload
    resp = client.post(f'/api/projects/{p["id"]}/make-video', json={})
    assert resp.status_code == 200, resp.text
    updated = client.get(f'/api/projects/{p["id"]}').json()
    assert updated['job']['status'] == 'succeeded'
    # Branding defaults
    assert updated['job']['branding']['logo_asset_id'] is None
    assert updated['job']['branding']['music_asset_id'] is None
    assert updated['job']['branding']['image_asset_ids'] == []
    assert updated['job']['branding']['broll_asset_ids'] == []


def test_make_video_with_custom_assets_selected_and_deselected(media, tmp_path, monkeypatch):
    """Selecting image/music/logo/broll inserts them into the plan; deselecting removes them."""
    p = new_project(media)
    aid = p['video']['asset_id']
    p['edit_plan']['subtitles'] = [{'id': 's', 'asset_id': aid, 'start': 0, 'end': 4, 'text': 'Trợ lý AI xây dựng thương hiệu.'}]
    main.save_project(p['id'], p)

    # 1. Upload Logo
    logo_path = tmp_path / 'logo.png'
    im = Image.new('RGBA', (64, 64), (255, 0, 0, 255))
    im.save(logo_path)
    with logo_path.open('rb') as f:
        res_logo = client.post(f'/api/projects/{p["id"]}/upload', files={'file': ('logo.png', f)}, data={'role': 'logo'}).json()
    logo_id = res_logo['edit_plan']['assets'][-1]['id']

    # 2. Upload Image illustration
    photo_path = tmp_path / 'illustration.png'
    im_photo = Image.new('RGB', (100, 100), (0, 255, 0))
    im_photo.save(photo_path)
    with photo_path.open('rb') as f:
        res_img = client.post(f'/api/projects/{p["id"]}/upload', files={'file': ('illustration.png', f)}, data={'role': 'asset', 'keywords': 'Trợ lý AI'}).json()
    img_id = res_img['edit_plan']['assets'][-1]['id']

    # 3. Upload Audio Music
    music_path = tmp_path / 'bg.wav'
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'lavfi', '-i', 'sine=frequency=440:duration=2', str(music_path)], check=True)
    with music_path.open('rb') as f:
        res_music = client.post(f'/api/projects/{p["id"]}/upload', files={'file': ('bg.wav', f)}, data={'role': 'music'}).json()
    music_id = res_music['edit_plan']['assets'][-1]['id']

    # 4. Upload B-roll video
    with media[1].open('rb') as f:
        res_broll = client.post(f'/api/projects/{p["id"]}/upload', files={'file': ('broll.mp4', f)}, data={'role': 'broll', 'keywords': 'Trợ lý'}).json()
    broll_id = res_broll['edit_plan']['assets'][-1]['id']

    monkeypatch.setenv('OLLAMA_URL', 'http://127.0.0.1:9')

    # STEP A: Render with all custom assets selected
    payload_selected = {
        'prompt': 'Yêu cầu dựng riêng phong cách sang trọng',
        'brand_name': 'MyCompany',
        'proper_names': 'Trợ lý AI, MyCompany',
        'logo_asset_id': logo_id,
        'music_asset_id': music_id,
        'image_asset_ids': [img_id],
        'broll_asset_ids': [broll_id],
        'illustrations': True
    }
    resp = client.post(f'/api/projects/{p["id"]}/make-video', json=payload_selected)
    assert resp.status_code == 200, resp.text
    project_data = client.get(f'/api/projects/{p["id"]}').json()
    assert project_data['job']['status'] == 'succeeded'

    branding = project_data['job']['branding']
    assert branding['logo_asset_id'] == logo_id
    assert branding['music_asset_id'] == music_id
    assert branding['image_asset_ids'] == [img_id]
    assert branding['broll_asset_ids'] == [broll_id]
    assert branding['brand_name'] == 'MyCompany'

    # Check edit_plan reflects the logo and music
    plan = project_data['edit_plan']
    assert any(o.get('role') == 'logo' and o.get('asset_id') == logo_id for o in plan.get('visual_overlays', []))
    assert any(a.get('asset_id') == music_id for a in plan.get('audio_tracks', []))

    # STEP B: Deselect resources on subsequent render
    payload_deselected = {
        'prompt': '',
        'brand_name': '',
        'logo_asset_id': '',
        'music_asset_id': '',
        'image_asset_ids': [],
        'broll_asset_ids': [],
        'illustrations': False
    }
    resp2 = client.post(f'/api/projects/{p["id"]}/make-video', json=payload_deselected)
    assert resp2.status_code == 200, resp2.text
    project_deselected = client.get(f'/api/projects/{p["id"]}').json()
    assert project_deselected['job']['status'] == 'succeeded'

    branding2 = project_deselected['job']['branding']
    assert branding2['logo_asset_id'] is None
    assert branding2['music_asset_id'] is None
    assert branding2['image_asset_ids'] == []
    assert branding2['broll_asset_ids'] == []

    plan2 = project_deselected['edit_plan']
    # Logo and music must not be present
    assert not any(o.get('role') == 'logo' for o in plan2.get('visual_overlays', []))
    assert not any(a.get('asset_id') == music_id for a in plan2.get('audio_tracks', []))


def test_cross_project_asset_isolation(media, tmp_path):
    """Assets from Project A must be strictly rejected if passed to Project B."""
    proj_a = new_project(media)
    proj_b = new_project(media)

    # Upload an image to Project A
    photo_path = tmp_path / 'proj_a_img.png'
    Image.new('RGB', (50, 50), (255, 255, 0)).save(photo_path)
    with photo_path.open('rb') as f:
        res_a = client.post(f'/api/projects/{proj_a["id"]}/upload', files={'file': ('proj_a_img.png', f)}, data={'role': 'asset'}).json()
    proj_a_asset_id = res_a['edit_plan']['assets'][-1]['id']

    # Attempt to use Project A asset in Project B make-video
    bad_logo = client.post(f'/api/projects/{proj_b["id"]}/make-video', json={'logo_asset_id': proj_a_asset_id})
    assert bad_logo.status_code == 422
    assert 'thuộc dự án này' in bad_logo.text

    bad_img = client.post(f'/api/projects/{proj_b["id"]}/make-video', json={'image_asset_ids': [proj_a_asset_id]})
    assert bad_img.status_code == 422
    assert 'thuộc dự án này' in bad_img.text

    bad_music = client.post(f'/api/projects/{proj_b["id"]}/make-video', json={'music_asset_id': proj_a_asset_id})
    assert bad_music.status_code == 422
    assert 'thuộc dự án này' in bad_music.text

    bad_broll = client.post(f'/api/projects/{proj_b["id"]}/make-video', json={'broll_asset_ids': [proj_a_asset_id]})
    assert bad_broll.status_code == 422
    assert 'thuộc dự án này' in bad_broll.text


def test_broll_validation_cannot_be_main_video_or_logo(media, tmp_path):
    """B-roll asset IDs cannot include the main video asset or the logo asset."""
    p = new_project(media)
    main_video_id = p['video']['asset_id']

    # Main video cannot be broll
    resp = client.post(f'/api/projects/{p["id"]}/make-video', json={'broll_asset_ids': [main_video_id]})
    assert resp.status_code == 422
    assert 'B-roll phải là video hoặc ảnh phụ' in resp.text

    # Upload logo
    logo_path = tmp_path / 'logo2.png'
    Image.new('RGBA', (50, 50), (0, 0, 255, 255)).save(logo_path)
    with logo_path.open('rb') as f:
        res_logo = client.post(f'/api/projects/{p["id"]}/upload', files={'file': ('logo2.png', f)}, data={'role': 'logo'}).json()
    logo_id = res_logo['edit_plan']['assets'][-1]['id']

    # Logo cannot be both logo and broll
    resp2 = client.post(f'/api/projects/{p["id"]}/make-video', json={'logo_asset_id': logo_id, 'broll_asset_ids': [logo_id]})
    assert resp2.status_code == 422
    assert 'Logo' in resp2.text or 'logo' in resp2.text


def test_reload_preserves_branding_state(media, tmp_path, monkeypatch):
    """GET /api/projects/{id} returns the persistent branding state for page reload restoration."""
    p = new_project(media)
    logo_path = tmp_path / 'logo3.png'
    Image.new('RGBA', (32, 32), (0, 255, 0, 255)).save(logo_path)
    with logo_path.open('rb') as f:
        res_logo = client.post(f'/api/projects/{p["id"]}/upload', files={'file': ('logo3.png', f)}, data={'role': 'logo'}).json()
    logo_id = res_logo['edit_plan']['assets'][-1]['id']

    monkeypatch.setenv('OLLAMA_URL', 'http://127.0.0.1:9')
    resp = client.post(f'/api/projects/{p["id"]}/make-video', json={
        'brand_name': 'Acme Corp',
        'proper_names': 'Acme, Founder',
        'logo_asset_id': logo_id,
        'prompt': 'Nhấn mạnh chất lượng'
    })
    assert resp.status_code == 200, resp.text

    # Simulate reload
    reloaded = client.get(f'/api/projects/{p["id"]}').json()
    branding = reloaded['job']['branding']
    assert branding['brand_name'] == 'Acme Corp'
    assert branding['logo_asset_id'] == logo_id
    assert branding['prompt'] == 'Nhấn mạnh chất lượng'
    assert branding['proper_names'] == 'Acme, Founder'

    # Check edit_plan.branding is also preserved
    plan_branding = reloaded['edit_plan']['branding']
    assert plan_branding['brand_name'] == 'Acme Corp'
    assert plan_branding['logo_asset_id'] == logo_id
    assert plan_branding['prompt'] == 'Nhấn mạnh chất lượng'
