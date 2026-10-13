"""One bounded font choice; engine owns typography, timing and safe areas."""
import copy
import json
import re
from typing import Literal
from project_paths import PROJECT_ROOT, SKILLS_DIR

FontStyle = Literal['auto', 'clean', 'business', 'energetic', 'friendly', 'tutorial', 'technology', 'story', 'editorial', 'documentary', 'impact']
CATALOG = json.loads((SKILLS_DIR / 'typography.json').read_text(encoding='utf-8'))
PROFILES = {p['id']: p for p in CATALOG['profiles']}
FONT_DIR = PROJECT_ROOT / 'motion_engine' / 'fonts'


def profile_for(plan):
    identifier = plan.get('typography', {}).get('profile_id')
    return PROFILES.get(identifier)


def font_path(profile, role):
    # File names come only from the checked-in catalog, never model/user paths.
    return FONT_DIR / profile['heading_file' if role == 'heading' else 'caption_file']


def public_profiles():
    return [{**p, 'caption_url': '/fonts/' + p['caption_file'],
             'heading_url': '/fonts/' + p['heading_file']} for p in PROFILES.values()]


def ai_guidance():
    return '; '.join(p['id'] + '(' + p['family'] + ')=' + p['topics'] for p in PROFILES.values())


def apply_typography(plan, requested='auto', prompt=''):
    if requested not in ('auto', *PROFILES):
        raise ValueError('Unknown font style')
    p = copy.deepcopy(plan)
    chosen = p.get('director', {}).get('font_style', 'auto')
    source = 'user' if requested != 'auto' else 'ai'
    if requested != 'auto':
        chosen = requested
    elif chosen not in PROFILES or p.get('director', {}).get('engine') != 'ollama':
        source = 'rules'
        # Explicit wording first. Transcript provides context, never new text.
        transcript = ' '.join(s.get('text', '') for s in p.get('subtitles', []))
        patterns = [('impact', r'quảng cáo|khuyến mãi|reels'),
                    ('energetic', r'thể thao|fitness|tập luyện|sự kiện'),
                    ('tutorial', r'hướng dẫn|thao tác|bài học'),
                    ('technology', r'công nghệ|phần mềm|trí tuệ nhân tạo|\bAI\b'),
                    ('business', r'doanh nghiệp|thương hiệu|dịch vụ'),
                    ('documentary', r'tư liệu|báo cáo|phân tích'),
                    ('editorial', r'phỏng vấn|lịch sử|cao cấp'),
                    ('story', r'kể chuyện|hồi tưởng|câu chuyện'),
                    ('friendly', r'gia đình|cộng đồng|đời sống')]
        chosen = 'clean'
        named = next((key for key, profile in PROFILES.items() if re.search(r'\b'+re.escape(profile['family'])+r'\b',prompt,re.I)), None)
        if named:
            chosen = named
        for text in (() if named else (prompt, transcript)):
            match = next((key for key, pattern in patterns if re.search(pattern, text, re.I)), None)
            if match:
                chosen = match
                break
    p['typography'] = {'version': 1, 'profile_id': chosen, 'requested': requested,
                       'selected_by': source, 'family': PROFILES[chosen]['family']}
    return p
