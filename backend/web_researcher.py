"""Web reference researcher and intelligent asset scraper.

Fetches web articles, extracts factual summary and downloads high-quality
reference images into project assets for AI storytelling and visual matching.
Uses only standard library html.parser, httpx, and Pillow.
"""
import hashlib
import io
import os
import re
import uuid
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlparse

import httpx
from PIL import Image

USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'


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


def fetch_web_page_data(url: str, timeout: float = 12.0) -> dict:
    """Fetch and parse webpage HTML into clean metadata and candidate image URLs."""
    if not is_valid_http_url(url):
        raise ValueError('Đường link web không hợp lệ. Vui lòng nhập link bắt đầu bằng http:// hoặc https://')

    headers = {'User-Agent': USER_AGENT, 'Accept-Language': 'vi,en-US;q=0.9,en;q=0.8'}
    with httpx.Client(timeout=timeout, follow_redirects=True, headers=headers) as client:
        resp = client.get(url)
        resp.raise_for_status()
        html = resp.text

    parser = WebContentParser(str(resp.url))
    parser.feed(html)

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
        'url': str(resp.url),
        'title': parser.title or 'Trang tham khảo',
        'description': parser.description,
        'summary': research_text,
        'candidate_images': candidates[:20]
    }


def download_and_register_web_images(candidate_images: list, asset_dir: Path, max_images: int = 6) -> list:
    """Download candidate images, validate resolution with Pillow, and return asset objects."""
    asset_dir = Path(asset_dir)
    asset_dir.mkdir(parents=True, exist_ok=True)
    saved_assets = []
    headers = {'User-Agent': USER_AGENT}

    with httpx.Client(timeout=10.0, follow_redirects=True, headers=headers) as client:
        for item in candidate_images:
            if len(saved_assets) >= max_images:
                break
            img_url = item['url']
            try:
                r = client.get(img_url)
                if r.status_code != 200 or len(r.content) < 512:
                    continue

                # Verify image format and dimension using Pillow
                with Image.open(io.BytesIO(r.content)) as im:
                    w, h = im.size
                    fmt = (im.format or 'JPEG').lower()
                    if w < 240 or h < 240:
                        continue  # Skip low-res thumbnails

                    ext = 'jpg' if fmt in ('jpeg', 'jpg') else ('png' if fmt == 'png' else ('webp' if fmt == 'webp' else 'jpg'))
                    uid = uuid.uuid4().hex[:8]
                    filename = f"web_{uid}.{ext}"
                    local_path = asset_dir / filename
                    local_path.write_bytes(r.content)

                    clean_alt = item.get('alt', '').strip() or f"Ảnh tham chiếu web ({w}x{h})"
                    clean_alt = re.sub(r'[\r\n\t]+', ' ', clean_alt)[:100]

                    asset = {
                        'id': f"web_img_{uid}",
                        'type': 'image',
                        'filename': filename,
                        'original_name': clean_alt,
                        'source': 'user_uploaded',  # High priority in visual matching
                        'metadata': {
                            'width': w,
                            'height': h,
                            'source_url': img_url,
                            'reference_alt': clean_alt
                        }
                    }
                    saved_assets.append(asset)
            except Exception:
                continue

    return saved_assets


def ingest_web_reference(url: str, asset_dir: Path, max_images: int = 5) -> dict:
    """One-stop research & image ingestion from a webpage link."""
    page_data = fetch_web_page_data(url)
    assets = download_and_register_web_images(page_data['candidate_images'], asset_dir, max_images=max_images)
    return {
        'url': page_data['url'],
        'title': page_data['title'],
        'description': page_data['description'],
        'summary': page_data['summary'],
        'assets': assets,
        'image_count': len(assets)
    }
