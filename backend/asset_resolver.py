"""Asset Resolver: resolves visual, video, and audio assets in prioritized order.

Priority:
1. User-uploaded project assets (images and authentic B-roll videos).
2. Curated local asset library (DATA_DIR/library with fallback to project data/library).
3. Procedural SVG/HTML vector cards & conceptual diagrams when no suitable asset is found.

Every resolved asset stores:
- local_path: Absolute local path on disk.
- source: 'user_uploaded' | 'local_library' | 'conceptual_graphic' | 'procedural_svg'
- license: License or attribution information.
- keywords: Matched or associated keywords.
- role: Role in scene (e.g., 'card_mockup', 'badge_icon', 'avatar', 'chart', 'broll_cutaway')
- status: 'verified' | 'procedural_fallback' | 'missing'
- media_type: 'image' | 'video' | 'svg'
"""
import copy
import json
import os
import re
from pathlib import Path
from illustrations import draw_graphic
from project_paths import PROJECT_ROOT, DATA_DIR

BASE_DIR = PROJECT_ROOT
LIBRARY_DIR = DATA_DIR / 'library'
SFX_DIR = DATA_DIR / 'sfx'
FALLBACK_LIBRARY_DIR = BASE_DIR / 'data' / 'library'
FALLBACK_SFX_DIR = BASE_DIR / 'data' / 'sfx'

LIBRARY_DIR.mkdir(parents=True, exist_ok=True)
SFX_DIR.mkdir(parents=True, exist_ok=True)

STOPWORDS = {'và', 'là', 'trong', 'cho', 'được', 'người', 'video', 'ảnh', 'hình', 'của', 'với', 'các', 'những', 'một'}

BASE_LIBRARY_CATALOG = {
    'tiktok': {
        'id': 'tiktok',
        'file': 'tiktok.svg',
        'media_type': 'svg',
        'topic': 'social_media',
        'keywords': ['tiktok', 'tik tok', 'douyin', 'short video', 'video ngắn'],
        'role': 'app_icon',
        'license': 'Brand Trademark / Fair Use Commentary',
        'origin': 'curated_stock',
        'usage_scope': 'app_icon',
        'description': 'Biểu tượng ứng dụng TikTok dùng cho ngữ cảnh video ngắn',
        'aspect_ratio': '1:1',
        'duration': None
    },
    'facebook': {
        'id': 'facebook',
        'file': 'facebook.svg',
        'media_type': 'svg',
        'topic': 'social_media',
        'keywords': ['facebook', 'fb', 'meta', 'mạng xã hội'],
        'role': 'app_icon',
        'license': 'Brand Trademark / Fair Use Commentary',
        'origin': 'curated_stock',
        'usage_scope': 'app_icon',
        'description': 'Biểu tượng Facebook dùng cho thảo luận mạng xã hội',
        'aspect_ratio': '1:1',
        'duration': None
    },
    'shopee': {
        'id': 'shopee',
        'file': 'shopee.svg',
        'media_type': 'svg',
        'topic': 'ecommerce',
        'keywords': ['shopee', 'sàn', 'thương mại điện tử', 'ecommerce', 'nội sàn'],
        'role': 'app_icon',
        'license': 'Brand Trademark / Fair Use Commentary',
        'origin': 'curated_stock',
        'usage_scope': 'app_icon',
        'description': 'Biểu tượng sàn thương mại điện tử Shopee',
        'aspect_ratio': '1:1',
        'duration': None
    },
    'alert': {
        'id': 'alert',
        'file': 'siren_alert.svg',
        'media_type': 'svg',
        'topic': 'warning_system',
        'keywords': ['alert', 'cảnh báo', 'tắt ads', 'rủi ro', 'chú ý', 'nguy hiểm', 'lưu ý', 'ads'],
        'role': 'badge_icon',
        'license': 'DANAVA Studio Built-in SVG',
        'origin': 'curated_stock',
        'usage_scope': 'badge_icon',
        'description': 'Huy hiệu cảnh báo rủi ro hoặc chú ý quan trọng',
        'aspect_ratio': '1:1',
        'duration': None
    },
    'bookmark': {
        'id': 'bookmark',
        'file': 'bookmark.svg',
        'media_type': 'svg',
        'topic': 'cta',
        'keywords': ['bookmark', 'lưu video', 'save', 'cta', 'kêu gọi'],
        'role': 'cta_icon',
        'license': 'DANAVA Studio Built-in SVG',
        'origin': 'curated_stock',
        'usage_scope': 'cta_icon',
        'description': 'Biểu tượng đánh dấu lưu lại video kêu gọi hành động',
        'aspect_ratio': '1:1',
        'duration': None
    },
    'chart': {
        'id': 'chart',
        'file': 'analytics_chart.svg',
        'media_type': 'svg',
        'topic': 'analytics',
        'keywords': ['chart', 'doanh số', 'báo cáo', 'phân tích', 'tăng trưởng', 'doanh thu', 'số liệu'],
        'role': 'chart_mockup',
        'license': 'DANAVA Studio Built-in SVG',
        'origin': 'curated_stock',
        'usage_scope': 'chart_mockup',
        'description': 'Đồ họa minh họa biểu đồ phân tích số liệu và tăng trưởng',
        'aspect_ratio': '16:9',
        'duration': None
    },
}

# Compatibility alias
LIBRARY_CATALOG = BASE_LIBRARY_CATALOG


def get_library_catalog() -> dict:
    """Loads default library catalog and merges custom catalog from DATA_DIR if present."""
    cat = copy.deepcopy(BASE_LIBRARY_CATALOG)
    custom_file = LIBRARY_DIR / 'catalog.json'
    if custom_file.is_file():
        try:
            data = json.loads(custom_file.read_text(encoding='utf-8'))
            for item in data.get('items', []):
                cid = item.get('id')
                if cid and isinstance(cid, str):
                    cat[cid] = item
        except (OSError, ValueError, KeyError):
            pass
    return cat


def find_library_file(filename: str) -> Path:
    p1 = LIBRARY_DIR / filename
    if p1.is_file():
        return p1
    p2 = FALLBACK_LIBRARY_DIR / filename
    if p2.is_file():
        return p2
    return p1


def find_sfx_file(filename: str) -> Path:
    p1 = SFX_DIR / filename
    if p1.is_file():
        return p1
    p2 = FALLBACK_SFX_DIR / filename
    if p2.is_file():
        return p2
    return p1


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


def words_tokens(text: str) -> set:
    norm = normalize_text(text)
    return set(re.findall(r'\b\w+\b', norm)) - STOPWORDS


def check_term_match(term: str, target: str) -> bool:
    """Checks exact token match or bounded phrase match, avoiding substring errors like 'AI' in 'giai đoạn'."""
    term_clean = term.strip().lower()
    if not term_clean:
        return False
    # If short term <= 2 chars (e.g. 'ai'), enforce strict word boundary
    if len(term_clean) <= 2:
        return bool(re.search(r'\b' + re.escape(term_clean) + r'\b', target.lower()))
    return term_clean in target.lower()


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
        self.catalog = get_library_catalog()

    def resolve_visual(self, query: str = '', role: str = 'illustration', fallback_title: str = '', fallback_badge: str = '', badge_color: str = 'teal', graphic_kind='auto', graphic_title='', graphic_items=None, visual_asset_id='') -> dict:
        norm_query = normalize_text(query)
        query_words = words_tokens(query)

        # 1. Search in user-uploaded project assets (images and authentic B-roll videos)
        for a in self.project_assets:
            is_valid_type = a.get('type') in ('image', 'video')
            # Protect logo from being mistakenly used as an illustration
            is_allowed_usage = (a.get('usage') != 'logo' or a['id'] == visual_asset_id)
            if is_valid_type and is_allowed_usage:
                match_target = f"{a.get('original_name', '')} {a.get('keywords', '')}"
                target_words = words_tokens(match_target)

                # Match by explicit visual_asset_id or content match
                id_match = bool(visual_asset_id and a['id'] == visual_asset_id)
                content_match = bool(query_words and (query_words & target_words)) or (bool(norm_query) and check_term_match(norm_query, match_target))

                if id_match or (not visual_asset_id and content_match):
                    file_path = self.asset_dir / a['filename']
                    if file_path.exists():
                        media_type = a.get('type', 'image')
                        res = {
                            'local_path': str(file_path),
                            'source': 'user_uploaded',
                            'asset_id': a['id'],
                            'original_name': a.get('original_name', a['filename']),
                            'license': 'User project asset (authentic media)',
                            'keywords': query,
                            'role': role if role != 'illustration' else ('broll_cutaway' if media_type == 'video' else 'user_photo'),
                            'status': 'verified',
                            'media_type': media_type,
                            'duration': a.get('metadata', {}).get('duration') if media_type == 'video' else None,
                            'source_in': a.get('source_in', 0.0) if media_type == 'video' else None,
                            'relevance_score': 1.0,
                            'matched_terms': list(query_words & target_words) if query_words else [query]
                        }
                        self.resolved_log.append(res)
                        return res

        # 2. Search in Curated Local Library (SVG icons and charts)
        for key, entry in self.catalog.items():
            entry_words = set()
            for kw in entry['keywords']:
                entry_words.update(words_tokens(kw))
            matched_kws = [kw for kw in entry['keywords'] if check_term_match(kw, query) or check_term_match(query, kw)]
            if (query_words & entry_words) or matched_kws:
                file_path = find_library_file(entry['file'])
                if file_path.exists():
                    res = {
                        'local_path': str(file_path),
                        'source': 'local_library',
                        'asset_id': f'lib_{key}',
                        'original_name': entry['file'],
                        'license': entry.get('license', 'DANAVA Studio Curated Stock'),
                        'keywords': query,
                        'role': entry.get('role', 'app_icon'),
                        'status': 'verified',
                        'media_type': entry.get('media_type', 'svg'),
                        'relevance_score': 0.75,
                        'matched_terms': matched_kws or list(query_words & entry_words)
                    }
                    self.resolved_log.append(res)
                    return res

        # 3. Approved conceptual graphics can be selected by AI without stock APIs
        if graphic_kind in ('chat', 'process', 'network'):
            path = self.work_dir / f'graphic_{len(self.resolved_log)}.png'
            draw_graphic(path, graphic_kind, graphic_title or fallback_title, graphic_items)
            res = {
                'local_path': str(path),
                'source': 'conceptual_graphic',
                'license': 'Original generated diagram',
                'role': graphic_kind,
                'status': 'procedural_fallback',
                'media_type': 'image',
                'relevance_score': 0.60,
                'matched_terms': [graphic_kind]
            }
            self.resolved_log.append(res)
            return res

        # 4. Procedural SVG Card Fallback (ensures visual presentation never fails or crashes)
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
            'media_type': 'svg',
            'relevance_score': 0.40,
            'matched_terms': []
        }
        self.resolved_log.append(res)
        return res

    def resolve_sound(self, kind: str) -> dict:
        """Resolve sound effect from local curated SFX library respecting DATA_DIR and fallback."""
        kind = (kind or 'pop').lower()
        wav_file = find_sfx_file(f'{kind}.wav')
        if not wav_file.exists():
            wav_file = find_sfx_file('pop.wav')
        return {
            'local_path': str(wav_file),
            'kind': kind,
            'status': 'verified' if wav_file.exists() else 'missing',
            'source': 'local_sfx'
        }

