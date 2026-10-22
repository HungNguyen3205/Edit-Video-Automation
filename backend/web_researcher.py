"""Web reference researcher and intelligent asset scraper.

Fetches web articles, extracts factual summary, validates SSRF security,
and downloads high-quality reference images into project assets for AI storytelling.
Uses only standard library html.parser, httpx, and Pillow.
"""
import hashlib
import io
import ipaddress
import os
import re
import socket
import uuid
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlparse

import httpx
from PIL import Image

USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'

# Security & resource bounds
MAX_IMAGE_BYTES = 10 * 1024 * 1024          # 10 MB per image
MAX_TOTAL_DOWNLOAD_BYTES = 30 * 1024 * 1024 # 30 MB session limit
MAX_IMAGE_PIXELS = 16_000_000               # 16 MP max decoded image size
Image.MAX_IMAGE_PIXELS = MAX_IMAGE_PIXELS


class WebContentParser(HTMLParser):
    def __init__(self, base_url: str):
        super().__init__()
        self.base_url = base_url
        self.title = ''
        self.description = ''
        self.og_image = ''
        self.headings = []
        self.paragraphs = []
        self.images = []

        self._in_title = False
        self._current_tag = None

    def handle_starttag(self, tag, attrs):
        self._current_tag = tag.lower()
        attr_dict = {k.lower(): v for k, v in attrs if v is not None}

        if self._current_tag == 'title':
            self._in_title = True
        elif self._current_tag == 'meta':
            prop = attr_dict.get('property', '').lower()
            name = attr_dict.get('name', '').lower()
            content = attr_dict.get('content', '').strip()
            if not content:
                return

            if prop == 'og:title' and not self.title:
                self.title = content
            elif (prop == 'og:description' or name == 'description') and not self.description:
                self.description = content
            elif prop == 'og:image' and not self.og_image:
                self.og_image = urljoin(self.base_url, content)

        elif self._current_tag == 'img':
            src = attr_dict.get('src') or attr_dict.get('data-src') or attr_dict.get('srcset', '').split()[0:1]
            if isinstance(src, list):
                src = src[0] if src else ''
            src = (src or '').strip()
            alt = (attr_dict.get('alt') or '').strip()
            if src and not src.startswith('data:'):
                abs_url = urljoin(self.base_url, src)
                if abs_url.startswith(('http://', 'https://')):
                    self.images.append({'url': abs_url, 'alt': alt})

    def handle_endtag(self, tag):
        if tag.lower() == 'title':
            self._in_title = False
        self._current_tag = None

    def handle_data(self, data):
        text = data.strip()
        if not text:
            return
        if self._in_title and not self.title:
            self.title = text
        elif self._current_tag in ('h1', 'h2') and len(self.headings) < 6:
            self.headings.append(text)
        elif self._current_tag == 'p' and len(self.paragraphs) < 8 and len(text.split()) > 4:
            self.paragraphs.append(text)


def is_valid_http_url(url: str) -> bool:
    try:
        parsed = urlparse(url)
        return parsed.scheme in ('http', 'https') and bool(parsed.netloc)
    except Exception:
        return False


def is_safe_web_url(url: str, allow_local: bool = False) -> bool:
    """Validate URL syntax and block SSRF attempts to private/loopback/cloud metadata IPs."""
    if not is_valid_http_url(url):
        return False
    if allow_local or os.getenv('ALLOW_LOCAL_WEB_RESEARCH', '').lower() in ('1', 'true', 'yes'):
        return True

    try:
        parsed = urlparse(url)
        hostname = (parsed.hostname or '').strip().lower()
        if not hostname:
            return False

        # Block localhost aliases and link-local addresses
        if hostname in ('localhost', '127.0.0.1', '::1', '0.0.0.0') or hostname.endswith('.local'):
            return False

        # Resolve IP to verify destination is public
        addr_info = socket.getaddrinfo(hostname, None)
        for item in addr_info:
            ip_str = item[4][0]
            ip = ipaddress.ip_address(ip_str)
            if ip.is_loopback or ip.is_private or ip.is_link_local or ip.is_reserved or ip.is_multicast:
                return False
        return True
    except Exception:
        return False


def fetch_web_page_data(url: str, timeout: float = 10.0, allow_local: bool = False) -> dict:
    """Fetch and parse webpage HTML into clean metadata and candidate image URLs with SSRF protection."""
    if not is_valid_http_url(url):
        raise ValueError('Đường link web không hợp lệ. Vui lòng nhập link bắt đầu bằng http:// hoặc https://')

    if not is_safe_web_url(url, allow_local=allow_local):
        raise ValueError('Đường link web bị chặn: không được phép truy cập địa chỉ mạng nội bộ hoặc máy chủ cục bộ.')

    headers = {'User-Agent': USER_AGENT, 'Accept-Language': 'vi,en-US;q=0.9,en;q=0.8'}

    curr_url = url
    resp_text = None
    final_url = url

    with httpx.Client(timeout=timeout, follow_redirects=False, headers=headers) as client:
        for _ in range(5):  # Max 5 redirects
            resp = client.get(curr_url)
            if resp.status_code in (301, 302, 303, 307, 308):
                redirect_target = resp.headers.get('Location', '')
                if not redirect_target:
                    break
                next_url = urljoin(curr_url, redirect_target)
                if not is_safe_web_url(next_url, allow_local=allow_local):
                    raise ValueError('Chuyển hướng đến địa chỉ mạng nội bộ không hợp lệ.')
                curr_url = next_url
                continue
            resp.raise_for_status()
            resp_text = resp.text
            final_url = str(resp.url)
            break

    if resp_text is None:
        raise ValueError('Không thể nhận nội dung từ trang web.')

    parser = WebContentParser(final_url)
    parser.feed(resp_text)

    # Compile a succinct research summary for AI briefing
    summary_parts = []
    if parser.title:
        summary_parts.append(f"Tiêu đề: {parser.title}")
    if parser.description:
        summary_parts.append(f"Tóm tắt: {parser.description}")
    elif parser.headings:
        summary_parts.append("Ý chính: " + "; ".join(parser.headings[:3]))
    elif parser.paragraphs:
        summary_parts.append("Nội dung: " + " ".join(parser.paragraphs[:2]))

    research_text = " | ".join(summary_parts)

    candidates = []
    seen = set()
    if parser.og_image:
        candidates.append({'url': parser.og_image, 'alt': parser.title or 'Ảnh tiêu biểu'})
        seen.add(parser.og_image)

    junk_patterns = ('avatar', 'icon', 'logo', 'badge', 'button', 'pixel', 'advert', 'sponsor', 'social', 'analytics')
    for img in parser.images:
        u = img['url'].lower()
        if img['url'] in seen:
            continue
        if any(p in u for p in junk_patterns):
            continue
        candidates.append(img)
        seen.add(img['url'])

    return {
        'url': final_url,
        'title': parser.title or 'Trang tham khảo',
        'description': parser.description,
        'summary': research_text,
        'candidate_images': candidates[:20]
    }


def download_and_register_web_images(
    candidate_images: list,
    asset_dir: Path,
    max_images: int = 5,
    cancel_event = None,
    existing_hashes: set = None,
    allow_local: bool = False
) -> list:
    """Download candidate images safely outside locks, validate with Pillow, compute content hash."""
    asset_dir = Path(asset_dir)
    asset_dir.mkdir(parents=True, exist_ok=True)
    saved_assets = []
    new_local_files = []
    headers = {'User-Agent': USER_AGENT}
    seen_hashes = set(existing_hashes or set())
    total_download_bytes = 0

    try:
        with httpx.Client(timeout=8.0, follow_redirects=True, headers=headers) as client:
            for item in candidate_images:
                if cancel_event and cancel_event.is_set():
                    raise InterruptedError('Đã hủy tải tài nguyên web.')

                if len(saved_assets) >= max_images:
                    break

                img_url = item['url']
                if not is_safe_web_url(img_url, allow_local=allow_local):
                    continue

                try:
                    r = client.get(img_url)
                    if r.status_code != 200:
                        continue

                    content = r.content
                    content_len = len(content)
                    if content_len < 512 or content_len > MAX_IMAGE_BYTES:
                        continue

                    total_download_bytes += content_len
                    if total_download_bytes > MAX_TOTAL_DOWNLOAD_BYTES:
                        break  # Session byte quota reached

                    # Content hashing to deduplicate identical images across different URLs
                    sha256 = hashlib.sha256(content).hexdigest()
                    if sha256 in seen_hashes:
                        continue  # Duplicate image already stored
                    seen_hashes.add(sha256)

                    # Verify image format and dimension using Pillow with decompression bomb check
                    with Image.open(io.BytesIO(content)) as im:
                        w, h = im.size
                        if w * h > MAX_IMAGE_PIXELS:
                            continue
                        if w < 240 or h < 240:
                            continue  # Skip low-res thumbnails

                        fmt = (im.format or 'JPEG').lower()
                        ext = 'jpg' if fmt in ('jpeg', 'jpg') else ('png' if fmt == 'png' else ('webp' if fmt == 'webp' else 'jpg'))
                        uid = uuid.uuid4().hex[:8]
                        filename = f"web_{uid}.{ext}"
                        local_path = asset_dir / filename
                        local_path.write_bytes(content)
                        new_local_files.append(local_path)

                        clean_alt = item.get('alt', '').strip() or f"Ảnh tham chiếu web ({w}x{h})"
                        clean_alt = re.sub(r'[\r\n\t]+', ' ', clean_alt)[:100]

                        asset = {
                            'id': f"web_img_{uid}",
                            'type': 'image',
                            'filename': filename,
                            'original_name': clean_alt,
                            'source': 'web_reference',  # Accurately reflect web origin
                            'metadata': {
                                'width': w,
                                'height': h,
                                'source_url': img_url,
                                'content_hash': sha256,
                                'reference_alt': clean_alt
                            }
                        }
                        saved_assets.append(asset)
                except Exception:
                    continue
        return saved_assets
    except (InterruptedError, Exception):
        # Clean up any uncommitted files on cancel or fatal error
        for f in new_local_files:
            try:
                if f.exists():
                    f.unlink()
            except Exception:
                pass
        raise


def ingest_web_reference(
    url: str,
    asset_dir: Path,
    max_images: int = 5,
    cancel_event = None,
    existing_hashes: set = None,
    allow_local: bool = False
) -> dict:
    """One-stop research & image ingestion with SSRF protection, hashing, and cancel awareness."""
    page_data = fetch_web_page_data(url, allow_local=allow_local)
    assets = download_and_register_web_images(
        page_data['candidate_images'],
        asset_dir,
        max_images=max_images,
        cancel_event=cancel_event,
        existing_hashes=existing_hashes,
        allow_local=allow_local
    )
    return {
        'url': page_data['url'],
        'title': page_data['title'],
        'description': page_data['description'],
        'summary': page_data['summary'],
        'assets': assets,
        'image_count': len(assets)
    }
