"""Asset Resolver: resolves visual and audio assets in prioritized order.

Priority:
1. User-uploaded project assets.
2. Curated local asset library (data/library).
3. Procedural SVG/HTML vector cards when no suitable image is found.

Every resolved asset stores:
- local_path: Absolute local path on disk.
- source: 'user_uploaded' | 'local_library' | 'procedural_svg'
- license: License or attribution information.
- keywords: Matched or associated keywords.
- role: Role in scene (e.g., 'card_mockup', 'badge_icon', 'avatar', 'chart')
- status: 'verified' | 'procedural_fallback' | 'missing'
"""
import copy
import json
import os
import re
from pathlib import Path
from illustrations import draw_graphic

BASE_DIR = Path(__file__).resolve().parent
LIBRARY_DIR = BASE_DIR / 'data' / 'library'
SFX_DIR = BASE_DIR / 'data' / 'sfx'
LIBRARY_DIR.mkdir(parents=True, exist_ok=True)
SFX_DIR.mkdir(parents=True, exist_ok=True)

LIBRARY_CATALOG = {
    'tiktok': {'file': 'tiktok.svg', 'keywords': ['tiktok', 'tik tok', 'douyin', 'short video', 'video ngắn'], 'role': 'app_icon', 'license': 'Brand Trademark / Fair Use Commentary'},
    'facebook': {'file': 'facebook.svg', 'keywords': ['facebook', 'fb', 'meta', 'mạng xã hội'], 'role': 'app_icon', 'license': 'Brand Trademark / Fair Use Commentary'},
    'shopee': {'file': 'shopee.svg', 'keywords': ['shopee', 'sàn', 'thương mại điện tử', 'ecommerce', 'nội sàn'], 'role': 'app_icon', 'license': 'Brand Trademark / Fair Use Commentary'},
    'alert': {'file': 'siren_alert.svg', 'keywords': ['alert', 'cảnh báo', 'tắt ads', 'rủi ro', 'chú ý', 'nguy hiểm', 'lưu ý', 'ads'], 'role': 'badge_icon', 'license': 'DANAVA Studio Built-in SVG'},
    'bookmark': {'file': 'bookmark.svg', 'keywords': ['bookmark', 'lưu video', 'save', 'cta', 'kêu gọi'], 'role': 'cta_icon', 'license': 'DANAVA Studio Built-in SVG'},
    'chart': {'file': 'analytics_chart.svg', 'keywords': ['chart', 'doanh số', 'báo cáo', 'phân tích', 'tăng trưởng', 'doanh thu', 'số liệu'], 'role': 'chart_mockup', 'license': 'DANAVA Studio Built-in SVG'},
}

def normalize_text(text: str) -> str:
    text = (text or '').lower()
    text = re.sub(r'[àáạảãâầấậẩẫăằắặẳẵ]', 'a', text)
    text = re.sub(r'[èéẹẻẽêềếệểễ]', 'e', text)
    text = re.sub(r'[ìíịỉĩ]', 'i', text)
    text = re.sub(r'[òóọỏõôồốộổỗơờớợởỡ]', 'o', text)
    text = re.sub(r'[ùúụủũưừứựửữ]', 'u', text)
    text = re.sub(r'[ỳýỵỷỹ]', 'y', text)
    text = re.sub(r'[đ]', 'd', text)
    return text

def build_procedural_card(title: str, subtitle: str, badge_text: str, badge_color: str, output_path: Path) -> Path:
    """Build a clean procedural SVG card when no user image exists."""
    color_map = {
        'teal': '#0D9488',
        'navy': '#1E293B',
        'red': '#EF4444',
    }
    hex_color = color_map.get(badge_color, '#0D9488')
    safe_title = (title or 'THÔNG TIN MINH HỌA').replace('<', '&lt;').replace('>', '&gt;')
    safe_sub = (subtitle or '').replace('<', '&lt;').replace('>', '&gt;')
    safe_badge = (badge_text or 'ĐIỂM NHẤN').replace('<', '&lt;').replace('>', '&gt;')

    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 600 400" width="600" height="400">
  <defs>
    <filter id="card-shadow" x="-10%" y="-10%" width="120%" height="125%">
      <feDropShadow dx="0" dy="16" stdDeviation="20" flood-color="rgba(0,0,0,0.08)"/>
    </filter>
  </defs>
  <rect x="20" y="20" width="560" height="360" rx="24" fill="#FFFFFF" stroke="#E2E8F0" stroke-width="2" filter="url(#card-shadow)"/>
  
  <!-- Top badge -->
  <rect x="50" y="50" width="{min(300, max(120, len(safe_badge) * 14 + 40))}" height="42" rx="21" fill="{hex_color}"/>
  <text x="{50 + min(300, max(120, len(safe_badge) * 14 + 40)) / 2}" y="77" font-family="'Barlow Condensed', Arial, sans-serif" font-size="20" font-weight="bold" fill="#FFFFFF" text-anchor="middle">{safe_badge}</text>
  
  <!-- Title -->
  <text x="50" y="150" font-family="'Barlow Condensed', Arial, sans-serif" font-size="34" font-weight="800" fill="#1E293B">{safe_title[:28]}</text>
  <text x="50" y="195" font-family="'Barlow Condensed', Arial, sans-serif" font-size="34" font-weight="800" fill="#1E293B">{safe_title[28:56]}</text>
  
  <!-- Subtitle -->
  <text x="50" y="250" font-family="Arial, sans-serif" font-size="18" fill="#64748B">{safe_sub[:45]}</text>
  
  <!-- Decorative accent bar -->
  <rect x="50" y="320" width="500" height="6" rx="3" fill="#F1F5F9"/>
  <rect x="50" y="320" width="180" height="6" rx="3" fill="{hex_color}"/>
</svg>'''
    output_path.write_text(svg, encoding='utf-8')
    return output_path

class AssetResolver:
    def __init__(self, project_assets: list, asset_dir: Path, work_dir: Path):
        self.project_assets = project_assets or []
        self.asset_dir = Path(asset_dir)
        self.work_dir = Path(work_dir)
        self.resolved_log = []

    def resolve_visual(self, query: str = '', role: str = 'illustration', fallback_title: str = '', fallback_badge: str = '', badge_color: str = 'teal', graphic_kind='auto', graphic_title='', graphic_items=None, visual_asset_id='') -> dict:
        norm_query = normalize_text(query)
        words = set(re.findall(r'\w+', norm_query))

        # 1. Search in user-uploaded project assets
        for a in self.project_assets:
            if a.get('type') == 'image' and (a.get('usage')!='logo' or a['id']==visual_asset_id):
                match_target = normalize_text(f"{a.get('original_name', '')} {a.get('keywords', '')}")
                target_words = set(re.findall(r'\w+', match_target))
                if (visual_asset_id and a['id'] == visual_asset_id) or (not visual_asset_id and (words & target_words or (norm_query and norm_query in match_target))):
                    file_path = self.asset_dir / a['filename']
                    if file_path.exists():
                        res = {
                            'local_path': str(file_path),
                            'source': 'user_uploaded',
                            'asset_id': a['id'],
                            'original_name': a.get('original_name', a['filename']),
                            'license': 'User project asset',
                            'keywords': query,
                            'role': role,
                            'status': 'verified',
                            'media_type': a.get('type', 'image')
                        }
                        self.resolved_log.append(res)
                        return res

        # 2. Search in Curated Local Library
        for key, entry in LIBRARY_CATALOG.items():
            catalog_words = set(normalize_text(kw) for kw in entry['keywords'])
            if words & catalog_words or any(kw in norm_query for kw in catalog_words):
                file_path = LIBRARY_DIR / entry['file']
                if file_path.exists():
                    res = {
                        'local_path': str(file_path),
                        'source': 'local_library',
                        'asset_id': f'lib_{key}',
                        'original_name': entry['file'],
                        'license': entry['license'],
                        'keywords': query,
                        'role': entry['role'],
                        'status': 'verified',
                        'media_type': 'image'
                    }
                    self.resolved_log.append(res)
                    return res

        # Approved conceptual graphics can be selected by AI without stock APIs.
        if graphic_kind in ('chat', 'process', 'network'):
            path = self.work_dir / f'graphic_{len(self.resolved_log)}.png'
            draw_graphic(path, graphic_kind, graphic_title or fallback_title, graphic_items)
            res = {'local_path': str(path), 'source': 'conceptual_graphic', 'license': 'Original generated diagram',
                   'role': graphic_kind, 'status': 'procedural_fallback', 'media_type': 'image'}
            self.resolved_log.append(res)
            return res
        # 3. Procedural SVG Card Fallback (ensures visual presentation never fails or crashes)
        clean_name = re.sub(r'[^\w]+', '_', normalize_text(fallback_title or query or 'card'))[:30]
        proc_path = self.work_dir / f'proc_{clean_name}_{len(self.resolved_log)}.svg'
        build_procedural_card(
            title=fallback_title or query or 'MINH HỌA NỘI DUNG',
            subtitle='Đồ họa tự dựng theo ý chính của lời thoại',
            badge_text=fallback_badge or 'ĐIỂM NHẤN',
            badge_color=badge_color,
            output_path=proc_path
        )
        res = {
            'local_path': str(proc_path),
            'source': 'procedural_svg',
            'asset_id': f'proc_{clean_name}',
            'original_name': proc_path.name,
            'license': 'DANAVA Studio Procedural Vector Graphic',
            'keywords': query,
            'role': 'procedural_card',
            'status': 'procedural_fallback',
            'media_type': 'image'
        }
        self.resolved_log.append(res)
        return res

    def resolve_sound(self, kind: str) -> dict:
        """Resolve sound effect from local curated SFX library."""
        kind = (kind or 'pop').lower()
        wav_file = SFX_DIR / f'{kind}.wav'
        if not wav_file.exists():
            wav_file = SFX_DIR / 'pop.wav'
        return {
            'local_path': str(wav_file),
            'kind': kind,
            'status': 'verified' if wav_file.exists() else 'missing',
            'source': 'local_sfx'
        }
