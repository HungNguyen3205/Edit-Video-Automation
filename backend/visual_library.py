"""Offline image & visual media catalog with multi-tier relevance matching, density policy, and real estate authenticity."""
import copy
import json
import re
from pathlib import Path
from project_paths import PROJECT_ROOT, SKILLS_DIR, DATA_DIR

IMAGE_DIR = PROJECT_ROOT / 'motion_engine/images'

CONTROLLED_SYNONYMS = {
    'ai': ['trợ lý ai', 'trợ lý ảo', 'trí tuệ nhân tạo', 'chatbot', 'chat bot', 'llm', 'mô hình ai', 'artificial intelligence'],
    'thương hiệu': ['branding', 'nhận diện thương hiệu', 'chiến lược thương hiệu', 'logo thương hiệu'],
    'marketing': ['tiếp thị', 'quảng cáo', 'truyền thông', 'kế hoạch nội dung', 'content strategy'],
    'chiến lược': ['kế hoạch', 'định hướng', 'tầm nhìn', 'lộ trình phát triển'],
    'doanh thu': ['doanh số', 'báo cáo', 'tăng trưởng', 'tài chính', 'số liệu', 'analytics'],
    'bất động sản': ['nhà đất', 'căn hộ', 'chung cư', 'biệt thự', 'villa', 'đất nền', 'nhà phố', 'shophouse', 'dự án bất động sản']
}

GENERIC_STOPWORDS = {
    'và', 'là', 'trong', 'cho', 'được', 'người', 'video', 'ảnh', 'hình', 'của', 'với', 'các', 'những', 'một', 'đang', 'rất', 'này'
}


def _is_safe_filename(name: str) -> bool:
    if not isinstance(name, str) or not name:
        return False
    if '..' in name or '/' in name or '\\' in name:
        return False
    p = Path(name)
    return p.name == name and p.suffix.lower() in ('.webp', '.png', '.jpg', '.jpeg', '.svg', '.mp4')


def _migrate_entry_v1_to_v2(raw: dict) -> dict:
    entry = dict(raw)
    entry.setdefault('media_type', 'image')
    entry.setdefault('topic', 'general')
    entry.setdefault('aspect_ratio', '16:9')
    entry.setdefault('duration', None)
    entry.setdefault('origin', 'curated_stock')
    entry.setdefault('license', 'DANAVA Studio Built-in Graphic / Local Illustration')
    entry.setdefault('usage_scope', 'conceptual_illustration')
    return entry


def catalog(custom_path=None):
    """Loads all valid visual catalog entries supporting schema v1 and v2, local custom catalogs, and safe path resolution."""
    entries = []
    seen_ids = set()

    sources = [SKILLS_DIR / 'visual_library.json']
    custom_catalog_path = Path(custom_path) if custom_path else (DATA_DIR / 'library' / 'visual_catalog.json')
    if custom_catalog_path.is_file():
        sources.append(custom_catalog_path)

    for src in sources:
        try:
            if not src.is_file():
                continue
            data = json.loads(src.read_text(encoding='utf-8'))
            version = data.get('schema_version')
            if version not in (1, 2):
                continue
            items = data.get('images', [])
            for raw in items:
                eid = raw.get('id', '')
                if not isinstance(eid, str) or not re.fullmatch(r'[a-z][a-z0-9_]{1,49}', eid):
                    continue
                if eid in seen_ids:
                    continue
                name = raw.get('file', '')
                if not _is_safe_filename(name):
                    continue
                kws = raw.get('keywords', [])
                if not isinstance(kws, list) or not 1 <= len(kws) <= 40:
                    continue
                if any(not isinstance(k, str) or not 1 <= len(k) <= 80 for k in kws):
                    continue

                # Locate file: check motion_engine/images, then DATA_DIR/library
                file_path = IMAGE_DIR / name
                if not file_path.is_file():
                    alt_path = DATA_DIR / 'library' / name
                    if alt_path.is_file():
                        file_path = alt_path

                if file_path.is_file():
                    entry = _migrate_entry_v1_to_v2(raw)
                    entry['_resolved_path'] = str(file_path)
                    entries.append(entry)
                    seen_ids.add(eid)
        except (OSError, ValueError, KeyError, TypeError):
            continue

    return entries


def catalog_stats():
    """Returns actual catalog statistics, existing files, and source paths without network calls."""
    items = catalog()
    existing_files = [e for e in items if Path(e.get('_resolved_path', '')).is_file()]
    return {
        'total_records': len(items),
        'files_existing': len(existing_files),
        'files_missing': len(items) - len(existing_files),
        'catalog_source': str(SKILLS_DIR / 'visual_library.json'),
        'image_dir': str(IMAGE_DIR),
        'entries': [
            {
                'id': e['id'],
                'file': e['file'],
                'media_type': e.get('media_type', 'image'),
                'topic': e.get('topic', 'general'),
                'origin': e.get('origin', 'curated_stock'),
                'usage_scope': e.get('usage_scope', 'conceptual_illustration'),
                'path': e.get('_resolved_path'),
                'size_bytes': Path(e['_resolved_path']).stat().st_size if e.get('_resolved_path') and Path(e['_resolved_path']).is_file() else 0
            }
            for e in items
        ]
    }


def library_image(identifier: str) -> Path:
    if not isinstance(identifier, str) or not re.fullmatch(r'[a-z][a-z0-9_]{1,49}', identifier):
        raise ValueError('Ảnh thư viện không tồn tại; định danh không hợp lệ.')
    entry = next((x for x in catalog() if x['id'] == identifier), None)
    if entry is None:
        raise ValueError('Ảnh thư viện không tồn tại; khôi phục tài nguyên của dự án.')
    resolved = Path(entry.get('_resolved_path', IMAGE_DIR / entry['file']))
    if not resolved.is_file():
        raise ValueError('Ảnh thư viện không tồn tại; tệp tin bị thiếu trên đĩa.')
    return resolved


def tokens(text: str):
    return re.findall(r'[^\W_]+', (text or '').casefold())


def phrase_in(phrase: str, text: str) -> bool:
    """Exact sequence token matching preventing substring false matches (e.g. 'AI' inside 'hai' or 'giai đoạn')."""
    a = tokens(phrase)
    b = tokens(text)
    if not a or not b:
        return False
    # If phrase is a single short token (e.g. 'ai'), strictly check token boundary
    if len(a) == 1 and len(a[0]) <= 2:
        return any(t == a[0] for t in b)
    return any(b[i:i + len(a)] == a for i in range(len(b) - len(a) + 1))


def is_generic_single_word(phrase: str) -> bool:
    t = tokens(phrase)
    return len(t) == 1 and t[0] in GENERIC_STOPWORDS


def is_real_estate_context(text: str, prompt: str = '') -> bool:
    """Detect if content pertains to real estate property where generic stock concepts must NOT impersonate actual assets."""
    combined = f'{text} {prompt}'.casefold()
    for term in CONTROLLED_SYNONYMS['bất động sản']:
        if phrase_in(term, combined):
            return True
    return False


def match_catalog_entry(entry: dict, speech: str, video_topic: str = '', prompt: str = ''):
    """Multi-tier matching:
    Tier 1: Exact phrase match in speech.
    Tier 2: Normalized non-generic token match.
    Tier 3: Controlled synonym match.
    Tier 4: Topic overlap.
    Returns: (score, tier, matched_terms, fallback_reason)
    """
    speech_lower = speech.casefold()

    # Requirement 7: Strict authenticity for real estate
    if is_real_estate_context(speech, prompt):
        if entry.get('topic') != 'real_estate' and entry.get('usage_scope') == 'conceptual_illustration':
            return 0.0, 'none', [], 'real_estate_stock_rejected'

    # Tier 1: Exact phrase matching
    tier1_matches = [k for k in entry['keywords'] if not is_generic_single_word(k) and phrase_in(k, speech)]
    if tier1_matches:
        # Score based on phrase specificity
        best_len = max(len(tokens(k)) for k in tier1_matches)
        score = min(1.0, 0.65 + best_len * 0.1)
        return score, 'exact_phrase', tier1_matches, ''

    # Tier 2: Normalized token match (filtered)
    speech_tokens = set(tokens(speech)) - GENERIC_STOPWORDS
    tier2_matches = []
    for k in entry['keywords']:
        k_tokens = set(tokens(k)) - GENERIC_STOPWORDS
        if k_tokens and k_tokens.issubset(speech_tokens):
            tier2_matches.append(k)
    if tier2_matches:
        score = 0.55 + min(0.2, len(tier2_matches) * 0.05)
        return score, 'normalized_tokens', tier2_matches, ''

    # Tier 3: Controlled synonyms match
    tier3_matches = []
    for root_concept, syn_list in CONTROLLED_SYNONYMS.items():
        if any(phrase_in(k, root_concept) or any(phrase_in(k, syn) for syn in syn_list) for k in entry['keywords']):
            for syn in syn_list:
                if phrase_in(syn, speech):
                    tier3_matches.append(f'{syn} (~{root_concept})')
    if tier3_matches:
        return 0.45, 'controlled_synonym', tier3_matches, ''

    # Tier 4: Contextual topic match
    if video_topic and entry.get('topic') and entry.get('topic') == video_topic:
        return 0.35, 'topic_context', [video_topic], ''

    return 0.0, 'none', [], 'no_content_match'


def calculate_density_budget(total_duration: float, scene_count: int, preset: str = 'dynamic_explainer') -> int:
    """Calculates realistic visual density based on timeline duration and pacing instead of a hardcoded limit of 2."""
    if total_duration < 8.0:
        return 1 if total_duration >= 3.0 and scene_count >= 3 else 0
    if total_duration <= 20.0:
        return min(2, max(1, scene_count // 2))
    if total_duration <= 45.0:
        return min(3, max(2, scene_count // 3))
    # For longer timelines, allow 1 visual every 12-15 seconds
    interval_budget = int(total_duration // 13)
    return min(max(3, interval_budget), scene_count // 2)


def apply_library_visuals(plan, prompt='', enabled=True):
    """Selects grounded visual library assets using multi-tier relevance, density budget, spacing, and strict diagnostics."""
    p = copy.deepcopy(plan)

    if not enabled or not p.get('branding', {}).get('illustrations', True) or re.search(r'không (?:thêm |chèn |dùng |cần )?(?:minh họa|đồ họa|hình|ảnh)', prompt, re.I):
        return p

    scenes = p.get('storyboard', [])
    if len(scenes) < 3:
        return p

    diagnostics = []


    total_duration = sum(s.get('duration', 0) for s in scenes)
    preset = p.get('motion_style', {}).get('preset', 'dynamic_explainer')
    max_visuals = calculate_density_budget(total_duration, len(scenes), preset)

    used_library_ids = {s.get('library_visual_id') for s in scenes if s.get('library_visual_id')}
    selected = {}  # scene_index -> (entry, matches, score, tier)
    taken_indices = set()
    available_entries = catalog()

    video_topic = p.get('director', {}).get('topic', '')

    for i, sc in enumerate(scenes):
        sc_id = sc.get('scene_id', str(i))
        speech = sc.get('transcript_meaning', '')

        # Opening and closing scenes stay talking_head for personal anchor
        if i == 0 or i == len(scenes) - 1:
            diagnostics.append({
                'scene_index': i,
                'scene_id': sc_id,
                'selected_id': None,
                'source': 'talking_head_anchor',
                'relevance_score': 0.0,
                'matched_terms': [],
                'tier': 'anchor',
                'fallback_reason': 'boundary_scene_anchor'
            })
            continue

        # Respect user-supplied or already protected visual assets
        if sc.get('visual_asset_id'):
            diagnostics.append({
                'scene_index': i,
                'scene_id': sc_id,
                'selected_id': sc['visual_asset_id'],
                'source': 'user_supplied',
                'relevance_score': 1.0,
                'matched_terms': ['explicit_user_asset'],
                'tier': 'user_specified',
                'fallback_reason': ''
            })
            taken_indices.add(i)
            continue

        if sc.get('library_visual_id'):
            taken_indices.add(i)
            continue

        if sc.get('duration', 0) < 2.4:
            diagnostics.append({
                'scene_index': i,
                'scene_id': sc_id,
                'selected_id': None,
                'source': 'none',
                'relevance_score': 0.0,
                'matched_terms': [],
                'tier': 'none',
                'fallback_reason': 'scene_duration_too_short'
            })
            continue

        # Check spacing from already taken visuals (minimum 4 seconds)
        if any(abs(sc['timeline_start'] - scenes[j]['timeline_start']) < 4.0 for j in taken_indices):
            diagnostics.append({
                'scene_index': i,
                'scene_id': sc_id,
                'selected_id': None,
                'source': 'none',
                'relevance_score': 0.0,
                'matched_terms': [],
                'tier': 'none',
                'fallback_reason': 'spacing_pacing_limit'
            })
            continue

        # Rank all available catalog entries
        best_candidate = None
        for entry in available_entries:
            if entry['id'] in used_library_ids or any(sel[0]['id'] == entry['id'] for sel in selected.values()):
                continue
            score, tier, matches, reason = match_catalog_entry(entry, speech, video_topic, prompt)
            if score >= 0.40:
                if not best_candidate or score > best_candidate[0]:
                    best_candidate = (score, tier, matches, entry)

        if best_candidate and len(selected) + len(used_library_ids) < max_visuals:
            score, tier, matches, entry = best_candidate
            selected[i] = (entry, matches, score, tier)
            taken_indices.add(i)
            diagnostics.append({
                'scene_index': i,
                'scene_id': sc_id,
                'selected_id': entry['id'],
                'source': entry.get('origin', 'curated_stock'),
                'relevance_score': round(score, 3),
                'matched_terms': matches,
                'tier': tier,
                'fallback_reason': ''
            })
        else:
            reason = 'density_budget_reached' if len(selected) + len(used_library_ids) >= max_visuals else 'below_relevance_threshold'
            if is_real_estate_context(speech, prompt):
                reason = 'real_estate_stock_rejected'
            diagnostics.append({
                'scene_index': i,
                'scene_id': sc_id,
                'selected_id': None,
                'source': 'none',
                'relevance_score': 0.0,
                'matched_terms': [],
                'tier': 'none',
                'fallback_reason': reason
            })

    if not selected:
        return p


    result = []
    for i, sc in enumerate(scenes):
        if i not in selected:
            result.append(sc)
            continue
        entry, matches, score, tier = selected[i]
        duration = sc['duration']
        start = sc['timeline_start']

        orig_source_in = sc.get('source_in', start)
        min_scene_dur = 1.6
        if duration >= 6.8:
            lead = 2.0
        else:
            lead = 0.0

        beat = min(4.2, duration - lead)
        if duration - lead - beat < min_scene_dur:
            beat = duration - lead

        chunks = []
        if lead > 0:
            chunks.append((0.0, lead, False))
        chunks.append((lead, beat, True))
        remainder = round(duration - lead - beat, 4)
        if remainder >= min_scene_dur:
            chunks.append((lead + beat, remainder, False))

        layout = 'full' if len([s for s in result if s.get('library_visual_id')]) % 2 == 0 else 'pip'
        for n, (offset, length, is_photo) in enumerate(chunks):
            part = copy.deepcopy(sc)
            part.update(
                scene_id=f"{sc['scene_id']}_photo{n}",
                timeline_start=start + offset,
                duration=length,
                source_in=orig_source_in + offset
            )
            part.pop('motion', None)
            if is_photo:
                part.update(
                    scene_type='explainer_card' if layout == 'full' else 'talking_head_pip',
                    library_visual_id=entry['id'],
                    photo_layout=layout,
                    library_match=matches,
                    relevance_score=score,
                    match_tier=tier,
                    animation_in='fade',
                    animation_out='none',
                    sound_effect='none'
                )
                part['graphic_items'] = []
                part['graphic_title'] = ''
                part['badge_text'] = ''
                if part.get('headline') and not phrase_in(part['headline'], sc.get('transcript_meaning', '')):
                    part['headline'] = ''
            else:
                part.update(scene_type='talking_head', sound_effect='none', headline='', badge_text='')
                part.pop('library_visual_id', None)
                part.pop('photo_layout', None)
            result.append(part)

    p['storyboard'] = result
    p.setdefault('director', {})['library_visuals'] = [
        {
            'scene_index': idx,
            'id': s['library_visual_id'],
            'source': 'local_generated_illustration',
            'matched_phrases': s.get('library_match', []),
            'relevance_score': s.get('relevance_score', 0.5),
            'tier': s.get('match_tier', 'exact_phrase')
        }
        for idx, s in enumerate(result) if s.get('library_visual_id')
    ]
    p['director']['visual_diagnostics'] = diagnostics
    warnings = p['director'].get('warnings', [])
    p['director']['warnings'] = list(dict.fromkeys([
        *[w for w in warnings if not w.startswith('Chưa đủ nội dung rõ để chọn minh họa tự động.')],
        'Ảnh thư viện là minh họa tổng hợp, không phải ảnh khách hàng hoặc giao diện sản phẩm thật.'
    ]))


    from editing import validate
    return validate(p, p['assets'])

