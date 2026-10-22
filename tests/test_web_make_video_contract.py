"""HTTP Contract & Integration tests for MakeVideo web_url and pipeline integration."""
import io
import time
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from PIL import Image
import pytest
from test_pipeline import client, media, new_project
import main
from main import MakeVideo, Options
import web_researcher


def test_reproduce_make_video_model_missing_web_url_field():
    """Reproduce the bug:
    MakeVideo must declare web_url so FastAPI/Pydantic parses it,
    and make_video endpoint must pass web_url to Options.
    """
    payload = {
        'style_preset': 'explainer',
        'prompt': 'Tạo video ngắn',
        'web_url': 'https://dantri.com.vn/bat-dong-san/can-ho.htm'
    }
    obj = MakeVideo(**payload)
    assert hasattr(obj, 'web_url'), "MakeVideo model is missing 'web_url' field"
    assert obj.web_url == 'https://dantri.com.vn/bat-dong-san/can-ho.htm'


def test_make_video_endpoint_passes_web_url_to_options(media, monkeypatch):
    """Reproduce the bug:
    When client posts web_url to /api/projects/{id}/make-video,
    the generated Options object must contain the web_url.
    """
    p = new_project(media)
    pid = p['id']

    captured_options = []
    orig_enqueue = main.enqueue

    def mock_enqueue(proj_id, bg, options, mode):
        captured_options.append(options)
        return orig_enqueue(proj_id, bg, options, mode)

    monkeypatch.setattr(main, 'enqueue', mock_enqueue)

    test_url = 'https://vnexpress.net/thoi-su/bai-viet-123.html'
    resp = client.post(f'/api/projects/{pid}/make-video', json={
        'style_preset': 'explainer',
        'prompt': 'Dựng đẹp',
        'web_url': test_url
    })
    assert resp.status_code == 200, resp.text
    assert len(captured_options) == 1
    assert captured_options[0].web_url == test_url, "make_video endpoint did not pass web_url to Options"

    # Verify project branding persists web_url for reload
    saved_proj = client.get(f'/api/projects/{pid}').json()
    assert saved_proj['edit_plan']['branding']['web_url'] == test_url


def test_url_validation_rejects_invalid_urls_and_long_strings(media):
    """URL validation must be consistent and reject non-http/https, malformed, or >1500 chars."""
    p = new_project(media)
    pid = p['id']

    # 1. Non-http/https URL
    r1 = client.post(f'/api/projects/{pid}/make-video', json={'web_url': 'javascript:alert(1)'})
    assert r1.status_code == 422

    r2 = client.post(f'/api/projects/{pid}/make-video', json={'web_url': 'not_a_url'})
    assert r2.status_code == 422

    # 2. Exceeding 1500 characters
    long_url = 'https://example.com/' + 'a' * 1550
    r3 = client.post(f'/api/projects/{pid}/make-video', json={'web_url': long_url})
    assert r3.status_code == 422

    # 3. Empty or whitespace is allowed (treated as no web source)
    r4 = client.post(f'/api/projects/{pid}/make-video', json={'web_url': '   '})
    assert r4.status_code == 200


def test_ssrf_protection_blocks_internal_and_private_ips(media, monkeypatch):
    """SSRF Protection: Private, loopback, and cloud metadata IPs must be rejected."""
    monkeypatch.delenv('ALLOW_LOCAL_WEB_RESEARCH', raising=False)

    # 1. Direct unit test of security helper
    assert not web_researcher.is_safe_web_url('http://127.0.0.1:8000/test')
    assert not web_researcher.is_safe_web_url('http://localhost:8000/test')
    assert not web_researcher.is_safe_web_url('http://169.254.169.254/latest/meta-data')
    assert not web_researcher.is_safe_web_url('http://192.168.1.1/admin')

    # 2. Ingest endpoint rejects internal IPs
    p = new_project(media)
    pid = p['id']
    resp = client.post(f'/api/projects/{pid}/ingest-web', json={'url': 'http://127.0.0.1:9999/private'})
    assert resp.status_code == 400
    assert 'địa chỉ mạng nội bộ' in resp.text


def test_run_job_does_not_call_web_researcher_when_no_url(media, monkeypatch):
    """When web_url is empty, web_researcher must NOT be called."""
    p = new_project(media)
    pid = p['id']

    called = []
    monkeypatch.setattr(web_researcher, 'ingest_web_reference', lambda *args, **kwargs: called.append(True))

    resp = client.post(f'/api/projects/{pid}/make-video', json={'web_url': ''})
    assert resp.status_code == 200
    res = client.get(f'/api/projects/{pid}').json()
    assert res['job']['status'] == 'succeeded'
    assert len(called) == 0, "ingest_web_reference should NOT have been called"


def test_run_job_calls_web_researcher_and_adds_assets_and_context(media, monkeypatch):
    """When a new web_url is provided, web_researcher is called, images are added to assets,
    and reference context is created while keeping user_prompt clean.
    """
    p = new_project(media)
    pid = p['id']

    fake_asset = {
        'id': 'web_img_ocean1',
        'type': 'image',
        'filename': 'web_ocean1.jpg',
        'original_name': 'Biệt thự biển',
        'source': 'web_reference',
        'metadata': {'width': 800, 'height': 600, 'source_url': 'https://example.com/ocean.jpg', 'content_hash': 'hash_ocean_1'}
    }
    (main.ASSETS_DIR / 'web_ocean1.jpg').write_bytes(b'fake')

    calls = []
    def mock_ingest(url, asset_dir, max_images=5, **kwargs):
        calls.append(url)
        return {
            'url': url,
            'title': 'Biệt thự biển cao cấp',
            'summary': 'Tiêu đề: Biệt thự biển cao cấp | Tóm tắt: Không gian nghỉ dưỡng đẳng cấp.',
            'assets': [fake_asset],
            'image_count': 1
        }

    monkeypatch.setattr(web_researcher, 'ingest_web_reference', mock_ingest)

    target_url = 'https://resort.vn/biet-thu'
    original_prompt = 'Tập trung vào phòng khách và khuôn viên'
    resp = client.post(f'/api/projects/{pid}/make-video', json={
        'style_preset': 'explainer',
        'prompt': original_prompt,
        'web_url': target_url
    })
    assert resp.status_code == 200
    res = client.get(f'/api/projects/{pid}').json()
    assert res['job']['status'] == 'succeeded', res['job'].get('error')

    assert len(calls) == 1
    assert calls[0] == target_url

    # Asset registered
    plan = res['edit_plan']
    assert any(a['id'] == 'web_img_ocean1' for a in plan['assets'])

    # Web reference and cache state recorded
    assert plan['web_reference']['url'] == target_url
    assert plan['web_reference']['status'] == 'success'
    assert 'web_img_ocean1' in plan['web_reference']['asset_ids']

    # User prompt is strictly preserved without web summary pollution
    director_prompt = res.get('director', {}).get('user_prompt') or plan.get('branding', {}).get('prompt')
    assert director_prompt == original_prompt
    assert 'DỮ LIỆU THAM KHẢO TỪ WEB' not in director_prompt


def test_caching_prevents_duplicate_scrape_and_duplicate_assets(media, monkeypatch):
    """When a project already fetched a web_url (e.g. via ingest-web or previous render),
    making video with the same web_url uses the cached reference without re-downloading.
    """
    p = new_project(media)
    pid = p['id']

    fake_asset = {
        'id': 'web_img_cache99',
        'type': 'image',
        'filename': 'web_cache99.jpg',
        'original_name': 'Ảnh đã lưu cache',
        'source': 'web_reference',
        'metadata': {'width': 800, 'height': 600, 'content_hash': 'hash_cache_99'}
    }
    (main.ASSETS_DIR / 'web_cache99.jpg').write_bytes(b'cached_content')

    target_url = 'https://danang.gov.vn/du-lich'

    # Seed the project with cached web reference
    proj_data = client.get(f'/api/projects/{pid}').json()
    proj_data['edit_plan']['assets'].append(fake_asset)
    proj_data['edit_plan']['web_reference'] = {
        'url': target_url,
        'fetched_at': 1729600000.0,
        'title': 'Du lịch Đà Nẵng',
        'summary': 'Thành phố biển đáng sống',
        'asset_ids': ['web_img_cache99'],
        'image_count': 1,
        'status': 'success'
    }
    main.save_project(pid, proj_data)

    call_count = [0]
    def mock_ingest(url, asset_dir, max_images=5, **kwargs):
        call_count[0] += 1
        raise AssertionError("ingest_web_reference must NOT be called when valid cache exists!")

    monkeypatch.setattr(web_researcher, 'ingest_web_reference', mock_ingest)

    # 1. Calling /ingest-web with same URL returns cached data
    r_ingest = client.post(f'/api/projects/{pid}/ingest-web', json={'url': target_url})
    assert r_ingest.status_code == 200
    assert r_ingest.json().get('cached') is True
    assert call_count[0] == 0

    # 2. Calling /make-video uses cache without calling ingest_web_reference
    r_make = client.post(f'/api/projects/{pid}/make-video', json={'web_url': target_url})
    assert r_make.status_code == 200
    res = client.get(f'/api/projects/{pid}').json()
    assert res['job']['status'] == 'succeeded'
    assert call_count[0] == 0
    # No duplicate assets created
    assets = [a['id'] for a in res['edit_plan']['assets'] if a['id'] == 'web_img_cache99']
    assert len(assets) == 1


def test_web_failure_continues_pipeline_with_warning_unless_mandatory(media, monkeypatch):
    """If web scraping fails (network timeout, 404, etc.):
    - Normal request: continues editing pipeline using existing assets, logs a warning.
    - Mandatory request ('bắt buộc nguồn web'): fails with clear error.
    """
    p = new_project(media)
    pid = p['id']

    def mock_failing_ingest(url, asset_dir, max_images=5, **kwargs):
        raise ConnectionError("Máy chủ web đích từ chối kết nối (HTTP 503).")

    monkeypatch.setattr(web_researcher, 'ingest_web_reference', mock_failing_ingest)

    # 1. Normal prompt with failing URL -> continues with warning
    resp = client.post(f'/api/projects/{pid}/make-video', json={
        'style_preset': 'explainer',
        'prompt': 'Dựng bình thường',
        'web_url': 'https://failing-site.com/broken'
    })
    assert resp.status_code == 200
    res = client.get(f'/api/projects/{pid}').json()
    assert res['job']['status'] == 'succeeded'
    warnings = res['job'].get('warnings', [])
    assert any('Không thể lấy dữ liệu từ link web tham khảo' in w for w in warnings)

    # 2. User explicitly demands mandatory web source -> fails gracefully
    p2 = new_project(media)
    pid2 = p2['id']
    resp2 = client.post(f'/api/projects/{pid2}/make-video', json={
        'style_preset': 'explainer',
        'prompt': 'Yêu cầu nguồn web phải có đầy đủ',
        'web_url': 'https://failing-site.com/broken'
    })
    assert resp2.status_code == 200
    res2 = client.get(f'/api/projects/{pid2}').json()
    assert res2['job']['status'] == 'failed'
    assert 'Yêu cầu bắt buộc nguồn web thất bại' in res2['job']['error']


def test_ingest_web_rejects_with_409_when_project_is_rendering(media):
    """Cannot ingest web assets while a project is actively rendering."""
    p = new_project(media)
    pid = p['id']

    # Set project to running state
    p_data = client.get(f'/api/projects/{pid}').json()
    p_data['job'] = {'id': 'running_job', 'status': 'running', 'phase': 'Đang render…'}
    main.save_project(pid, p_data)

    resp = client.post(f'/api/projects/{pid}/ingest-web', json={'url': 'https://example.com/test'})
    assert resp.status_code == 409
    assert 'đang trong quá trình dựng video' in resp.text


def test_ingest_web_outside_lock_allows_concurrent_status_checks(media, monkeypatch):
    """Network download happens OUTSIDE lock: concurrent status checks are not blocked."""
    p = new_project(media)
    pid = p['id']

    slow_fetch_started = threading.Event()
    allow_fetch_to_finish = threading.Event()

    def slow_mock_ingest(url, asset_dir, max_images=5, **kwargs):
        slow_fetch_started.set()
        allow_fetch_to_finish.wait(timeout=5.0)
        return {
            'url': url,
            'title': 'Trang chậm',
            'summary': 'Tóm tắt',
            'assets': [],
            'image_count': 0
        }

    monkeypatch.setattr(web_researcher, 'ingest_web_reference', slow_mock_ingest)

    ingest_thread = threading.Thread(
        target=lambda: client.post(f'/api/projects/{pid}/ingest-web', json={'url': 'https://slow-site.com/test'})
    )
    ingest_thread.start()

    # Wait until network fetch is inside the slow function (outside lock)
    assert slow_fetch_started.wait(timeout=3.0)

    # Status check must respond IMMEDIATELY without waiting for the slow fetch!
    t0 = time.monotonic()
    status_resp = client.get(f'/api/projects/{pid}/status')
    t1 = time.monotonic()
    assert status_resp.status_code == 200
    assert (t1 - t0) < 1.0, "Status check was blocked by LOCK during web network fetch!"

    # Release the slow fetch
    allow_fetch_to_finish.set()
    ingest_thread.join(timeout=3.0)


def test_content_hash_deduplication_prevents_duplicate_assets_for_same_image(tmp_path):
    """Images with identical content hash across different URLs are deduplicated."""
    img_data = io.BytesIO()
    Image.new('RGB', (300, 300), color='blue').save(img_data, format='JPEG')
    content = img_data.getvalue()

    class DupHandler(BaseHTTPRequestHandler):
        def log_message(self, *args): pass
        def do_GET(self):
            self.send_response(200)
            self.send_header('Content-Type', 'image/jpeg')
            self.send_header('Content-Length', str(len(content)))
            self.end_headers()
            self.wfile.write(content)

    server = ThreadingHTTPServer(('127.0.0.1', 0), DupHandler)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    port = server.server_port

    try:
        candidates = [
            {'url': f'http://127.0.0.1:{port}/image_a.jpg', 'alt': 'Ảnh A'},
            {'url': f'http://127.0.0.1:{port}/image_b.jpg', 'alt': 'Ảnh B'}
        ]
        asset_dir = tmp_path / 'assets'
        assets = web_researcher.download_and_register_web_images(candidates, asset_dir, max_images=5, allow_local=True)
        # Even though 2 different URLs were fetched, since content hash is identical, only 1 asset is saved
        assert len(assets) == 1
        assert assets[0]['source'] == 'web_reference'
        assert 'content_hash' in assets[0]['metadata']
    finally:
        server.shutdown()
        server.server_close()


def test_real_local_http_server_web_research_integration(media, tmp_path, monkeypatch):
    """End-to-end test with a REAL local HTTP server (live socket connection):
    Simulates actual HTTP GET, HTML parsing, image download, and Pillow validation.
    No mocks used for network or image parsing.
    """
    monkeypatch.setenv('ALLOW_LOCAL_WEB_RESEARCH', '1')

    img_io = io.BytesIO()
    Image.new('RGB', (400, 300), color=(10, 150, 80)).save(img_io, format='JPEG')
    real_img_bytes = img_io.getvalue()

    class LiveWebHandler(BaseHTTPRequestHandler):
        def log_message(self, *args): pass
        def do_GET(self):
            if self.path == '/article':
                html = f"""
                <!DOCTYPE html>
                <html>
                  <head>
                    <title>Khám phá Đà Nẵng 2026</title>
                    <meta property="og:description" content="Kinh nghiệm du lịch Đà Nẵng trọn gói từ A đến Z.">
                  </head>
                  <body>
                    <h1>Điểm đến hấp dẫn</h1>
                    <p>Bán đảo Sơn Trà và Bà Nà Hills là những điểm đến không thể bỏ qua khi tới đây.</p>
                    <img src="http://127.0.0.1:{self.server.server_port}/photo.jpg" alt="Toàn cảnh bán đảo">
                  </body>
                </html>
                """
                self.send_response(200)
                self.send_header('Content-Type', 'text/html; charset=utf-8')
                self.end_headers()
                self.wfile.write(html.encode('utf-8'))
            elif self.path == '/photo.jpg':
                self.send_response(200)
                self.send_header('Content-Type', 'image/jpeg')
                self.send_header('Content-Length', str(len(real_img_bytes)))
                self.end_headers()
                self.wfile.write(real_img_bytes)
            else:
                self.send_response(404)
                self.end_headers()

    server = ThreadingHTTPServer(('127.0.0.1', 0), LiveWebHandler)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    port = server.server_port

    try:
        live_url = f'http://127.0.0.1:{port}/article'
        p = new_project(media)
        pid = p['id']

        resp = client.post(f'/api/projects/{pid}/make-video', json={
            'style_preset': 'explainer',
            'prompt': 'Giới thiệu du lịch',
            'web_url': live_url
        })
        assert resp.status_code == 200, resp.text
        res = client.get(f'/api/projects/{pid}').json()
        assert res['job']['status'] == 'succeeded', res['job']

        plan = res['edit_plan']
        # An actual image must have been scraped, saved to disk, and registered in assets
        web_assets = [a for a in plan['assets'] if a['id'].startswith('web_img_')]
        assert len(web_assets) >= 1
        assert web_assets[0]['source'] == 'web_reference'
        assert 'content_hash' in web_assets[0]['metadata']

        created_file = main.ASSETS_DIR / web_assets[0]['filename']
        assert created_file.exists()
        assert created_file.stat().st_size > 0

        # Cached reference recorded
        assert plan['web_reference']['title'] == 'Khám phá Đà Nẵng 2026'
        assert plan['web_reference']['status'] == 'success'
    finally:
        server.shutdown()
        server.server_close()
