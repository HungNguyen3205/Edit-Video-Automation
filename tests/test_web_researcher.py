"""Tests for web researcher, metadata parsing, and image asset ingestion."""
import io
import json
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import threading
import pytest
from PIL import Image

from web_researcher import is_valid_http_url, WebContentParser, download_and_register_web_images, ingest_web_reference
from test_pipeline import client, media, new_project
import main


def test_url_validation():
    assert is_valid_http_url('https://example.com/article')
    assert is_valid_http_url('http://dantri.com.vn/bat-dong-san/nha-dep.htm')
    assert not is_valid_http_url('ftp://ftp.is.co.za/rfc/rfc1808.txt')
    assert not is_valid_http_url('javascript:void(0)')
    assert not is_valid_http_url('not-a-url')


def test_html_parser_extracts_clean_metadata_and_candidate_images():
    html = """
    <!DOCTYPE html>
    <html>
      <head>
        <title>Đánh giá Căn hộ Eco Green Sài Gòn</title>
        <meta property="og:description" content="Khu phức hợp căn hộ sinh thái cao cấp tại Quận 7 với đầy đủ tiện ích.">
        <meta property="og:image" content="/images/banner.jpg">
      </head>
      <body>
        <h1>Tổng quan dự án</h1>
        <p>Eco Green có diện tích rộng lớn với công viên xanh mát, hồ bơi và khu vui chơi trẻ em.</p>
        <img src="https://example.com/images/living_room.png" alt="Phòng khách sang trọng">
        <img src="/images/icon_star.png" alt="Icon">
        <img src="data:image/png;base64,AAAA" alt="Embedded">
      </body>
    </html>
    """
    parser = WebContentParser('https://example.com/project/detail')
    parser.feed(html)

    assert parser.title == 'Đánh giá Căn hộ Eco Green Sài Gòn'
    assert 'Khu phức hợp căn hộ sinh thái' in parser.description
    assert parser.og_image == 'https://example.com/images/banner.jpg'
    assert any('living_room.png' in img['url'] for img in parser.images)
    # data: images should not be in parser.images
    assert not any('data:' in img['url'] for img in parser.images)


def test_download_and_register_filters_small_images_and_creates_assets(tmp_path):
    # Setup a local test HTTP server that serves a valid 500x500 image and a 50x50 tiny icon
    img_large = io.BytesIO()
    Image.new('RGB', (600, 450), color='green').save(img_large, format='JPEG')
    large_bytes = img_large.getvalue()

    img_small = io.BytesIO()
    Image.new('RGB', (50, 50), color='red').save(img_small, format='JPEG')
    small_bytes = img_small.getvalue()

    class MockMediaHandler(BaseHTTPRequestHandler):
        def log_message(self, *args): pass
        def do_GET(self):
            if self.path == '/large.jpg':
                self.send_response(200)
                self.send_header('Content-Type', 'image/jpeg')
                self.send_header('Content-Length', str(len(large_bytes)))
                self.end_headers()
                self.wfile.write(large_bytes)
            elif self.path == '/small.jpg':
                self.send_response(200)
                self.send_header('Content-Type', 'image/jpeg')
                self.send_header('Content-Length', str(len(small_bytes)))
                self.end_headers()
                self.wfile.write(small_bytes)
            else:
                self.send_response(404)
                self.end_headers()

    server = ThreadingHTTPServer(('127.0.0.1', 0), MockMediaHandler)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    port = server.server_port

    try:
        candidates = [
            {'url': f'http://127.0.0.1:{port}/large.jpg', 'alt': 'Ảnh phòng khách'},
            {'url': f'http://127.0.0.1:{port}/small.jpg', 'alt': 'Ảnh icon nhỏ'}
        ]
        asset_dir = tmp_path / 'assets'
        saved = download_and_register_web_images(candidates, asset_dir, max_images=5)

        # Only the large image should be accepted and registered
        assert len(saved) == 1
        assert saved[0]['type'] == 'image'
        assert saved[0]['metadata']['width'] == 600
        assert saved[0]['metadata']['height'] == 450
        assert (asset_dir / saved[0]['filename']).exists()
    finally:
        server.shutdown()
        server.server_close()


def test_api_ingest_web_endpoint(media, monkeypatch, tmp_path):
    p = new_project(media)
    pid = p['id']

    # Mock ingest_web_reference to simulate scraping without external internet in test
    fake_asset = {
        'id': 'web_img_test123',
        'type': 'image',
        'filename': 'web_test123.jpg',
        'original_name': 'Căn hộ view biển',
        'source': 'user_uploaded',
        'metadata': {'width': 800, 'height': 600, 'source_url': 'https://example.com/photo.jpg'}
    }
    (main.ASSETS_DIR / 'web_test123.jpg').write_bytes(b'dummy')

    def mock_ingest(url, asset_dir, max_images=5):
        return {
            'url': url,
            'title': 'Căn hộ view biển đắt giá',
            'description': 'Tọa lạc tại vị trí vàng hướng nhìn thẳng ra biển.',
            'summary': 'Tiêu đề: Căn hộ view biển đắt giá | Tóm tắt: Tọa lạc tại vị trí vàng hướng nhìn thẳng ra biển.',
            'assets': [fake_asset],
            'image_count': 1
        }

    import web_researcher
    monkeypatch.setattr(web_researcher, 'ingest_web_reference', mock_ingest)

    resp = client.post(f'/api/projects/{pid}/ingest-web', json={'url': 'https://batdongsan.com.vn/can-ho-bien'})
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data['success'] is True
    assert data['image_count'] == 1
    assert 'Căn hộ view biển' in data['title']

    # Verify project has the new asset in edit_plan
    updated_proj = client.get(f'/api/projects/{pid}').json()
    asset_ids = [a['id'] for a in updated_proj['edit_plan']['assets']]
    assert 'web_img_test123' in asset_ids
    assert 'web_img_test123' in updated_proj['edit_plan']['branding']['image_asset_ids']
