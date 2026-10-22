"""Local style feedback memory; stores no speech, names, assets or timestamps.

Preserves curated style supervision and editorial preferences without neural model weight training.
"""
import copy
import hashlib
import json
import os
import re
from pathlib import Path
from statistics import median
from datetime import datetime, timezone
from project_paths import SKILLS_DIR
from motion_style import motion_skills
from text_review import valid_confirmations, unconfirmed_issues
from editing import length

SCHEMA_VERSION = 2

RULES = [
    'Preserve meaningful speech and source duration unless the user explicitly enables engine-verified filler cleanup. Use only current-source facts/names; never choose cut timestamps.',
    'Prefer camera opening and ending, with a few relevant interior illustrations.',
    'Use short clear headlines; keep explicit multiword names together.',
    'Use gentle purposeful camera zoom and quiet effects; respect the current request.',
    'Uploaded photos are preferred when relevant; conceptual graphics must not imply a real product screenshot.'
]


def editor_skills(path=None):
    """Load bounded project instructions; a broken file cannot break rendering."""
    try:
        pack = json.loads(Path(path or SKILLS_DIR / 'editing_skills.json').read_text(encoding='utf-8'))
        if not isinstance(pack, dict):
            raise ValueError('Invalid skill pack')
        skills = pack.get('skills')
        if pack.get('schema_version') != 1 or not isinstance(skills, list) or not 1 <= len(skills) <= 8:
            raise ValueError('Invalid skill pack')
        ids = set()
        active = []
        for skill in skills:
            if not isinstance(skill, dict) or not isinstance(skill.get('id'), str) or not 1 <= len(skill['id']) <= 40 or skill['id'] in ids or not isinstance(skill.get('enabled'), bool) or not isinstance(skill.get('rule'), str) or not 1 <= len(skill['rule']) <= 400:
                raise ValueError('Invalid skill')
            ids.add(skill['id'])
            if skill['enabled']:
                active.append({'id': skill['id'], 'rule': skill['rule']})
        if sum(len(skill['rule']) for skill in active) > 1800:
            raise ValueError('Skill instructions are too long')
        return active
    except (OSError, ValueError, TypeError):
        return []


def sanitize_note(note: str) -> str:
    """Strip private paths, customer/brand identifiers or absolute factual claims from feedback."""
    if not note or not isinstance(note, str):
        return ''
    cleaned = re.sub(r'[A-Za-z]:\\[^\s]+', '', note)  # Windows paths
    cleaned = re.sub(r'/(?:outputs|assets|tmp|projects|data)/[^\s]+', '', cleaned)  # Unix paths
    cleaned = re.sub(r'\b(?:dự án|khách hàng|thương hiệu|brand|công ty)\s+[\w\s]{2,30}', '', cleaned, flags=re.IGNORECASE)
    return ' '.join(cleaned.split())[:250]


def visual_summary(plan):
    """Extract structured, non-identifying editorial style features from edit plan.

    Features are statistical metadata of pacing, layout, and rhythm,
    NOT direct neural motion learning from raw video footage.
    """
    scenes = plan.get('storyboard', [])
    types = [s.get('scene_type', 'talking_head') for s in scenes]
    durations = [float(s.get('duration', 0)) for s in scenes if float(s.get('duration', 0)) > 0]
    total_dur = sum(durations) if durations else max(0.001, length(plan))

    # 1. illustration_duration_ratio: fraction of final timeline duration spent on illustration cards / pip
    ill_dur = sum(float(s.get('duration', 0)) for s in scenes if s.get('scene_type', 'talking_head') != 'talking_head')
    ill_ratio = round(ill_dur / max(0.001, total_dur), 2)

    # 2. median_scene_duration: median scene length in seconds
    med_scene_dur = round(median(durations), 2) if durations else 4.0

    # 3. transition_types: set of scene entry transition styles used
    transitions = sorted({s.get('animation_in', 'pop_in') for s in scenes if s.get('animation_in')})
    if not transitions:
        transitions = ['pop_in']

    # 4. zoom_amplitude_median: median zoom scale among active zoom shots
    zoom_scales = [float(s.get('zoom_scale', 1.0)) for s in scenes if float(s.get('zoom_scale', 1.0)) > 1.0]
    med_zoom = round(median(zoom_scales), 3) if zoom_scales else 1.0

    # 5. caption_preset: font & subtitle typography profile id
    cap_profile = plan.get('typography', {}).get('profile_id', 'legacy')

    # 6. sfx_density_per_minute: count of sound effects per minute of video
    sfx_count = sum(1 for s in scenes if s.get('sound_effect') and s.get('sound_effect') != 'none')
    sfx_density = round(sfx_count / max(0.1, total_dur / 60.0), 1)

    preset_id = plan.get('style_preset', {}).get('id', 'explainer') if isinstance(plan.get('style_preset'), dict) else 'explainer'

    return {
        'style_preset': preset_id,
        'motion_preset': plan.get('motion_style', {}).get('preset', 'clean'),
        'font_profile': cap_profile,
        'scene_types': types[:12],
        'scene_count': len(scenes),
        'illustration_fraction': round(sum(t != 'talking_head' for t in types) / max(1, len(types)), 2),
        'illustration_duration_ratio': ill_ratio,
        'median_scene_duration': med_scene_dur,
        'transition_types': transitions,
        'zoom_amplitude_median': med_zoom,
        'caption_preset': cap_profile,
        'sfx_density_per_minute': sfx_density,
        'headline_words_median': round(median([len(s.get('headline', '').split()) for s in scenes])) if scenes else 0
    }


def review_evidence(project, captions_checked):
    plan = project['edit_plan']
    subs = plan.get('subtitles', [])
    asset_id = plan.get('video_clips', [{}])[0].get('asset_id')
    asset = next((a for a in plan.get('assets', []) if a.get('id') == asset_id), {})
    return {
        'version': 1,
        'source_sha256': asset.get('sha256', ''),
        'subtitle_count': len(subs),
        'pending_subtitles': len(unconfirmed_issues(plan)),
        'confirmed_subtitles': len(valid_confirmations(plan)),
        'captions_checked': bool(captions_checked),
        'output_current': project.get('output_revision') == project.get('revision') and (project.get('job') or {}).get('status') == 'succeeded'
    }


def reviewed_record(record):
    evidence = record.get('review_evidence', {})
    if not isinstance(evidence, dict):
        return False
    return (
        record.get('decision') == 'approve_style'
        and record.get('captions_checked') is True
        and evidence.get('version') == 1
        and evidence.get('captions_checked') is True
        and evidence.get('output_current') is True
        and evidence.get('pending_subtitles') == 0
        and isinstance(evidence.get('subtitle_count'), int)
        and evidence['subtitle_count'] > 0
        and isinstance(evidence.get('source_sha256'), str)
        and len(evidence['source_sha256']) == 64
    )


def migrate_record(record):
    """Ensure older v1 records conform to schema v2 with safe defaults."""
    if not isinstance(record, dict):
        return None
    r = copy.deepcopy(record)
    ver = r.get('schema_version', 1)
    if ver < 2:
        r['schema_version'] = 2
        vs = r.setdefault('visual_style', {})
        vs.setdefault('style_preset', 'explainer')
        vs.setdefault('illustration_duration_ratio', vs.get('illustration_fraction', 0.0))
        vs.setdefault('median_scene_duration', 4.0)
        vs.setdefault('transition_types', ['pop_in'])
        vs.setdefault('zoom_amplitude_median', 1.04)
        vs.setdefault('caption_preset', vs.get('font_profile', 'legacy'))
        vs.setdefault('sfx_density_per_minute', 0.0)
        r.setdefault('confidence_score', 1.0 if reviewed_record(r) else 0.7)
    return r


def score_relevance(record, target):
    """Score historical style record relevance against current target video criteria."""
    if not target or not isinstance(target, dict):
        return 1.0
    score = 0.0
    vs = record.get('visual_style', {})

    # 1. Matching style preset (+5.0)
    target_preset = target.get('style_preset', 'explainer')
    if vs.get('style_preset') == target_preset:
        score += 5.0

    # 2. Matching motion preset (+3.0)
    target_motion = target.get('motion_preset', 'clean')
    if vs.get('motion_preset') == target_motion:
        score += 3.0

    # 3. Topic & brief keyword overlap in note / prompt (+1.5 per word, up to 4.5)
    note_words = set(re.findall(r'[^\W_]+', record.get('note', '').casefold()))
    prompt_words = set(re.findall(r'[^\W_]+', str(target.get('prompt', '')).casefold()))
    overlap = note_words & prompt_words
    score += min(4.5, len(overlap) * 1.5)

    # 4. Verified reviewed record confidence (+2.0)
    if reviewed_record(record):
        score += 2.0
    else:
        score += float(record.get('confidence_score', 0.5))

    # 5. Recency tie-breaker
    updated_at = record.get('updated_at', '')
    if updated_at:
        try:
            ts = datetime.fromisoformat(updated_at.replace('Z', '+00:00')).timestamp()
            score += min(0.5, max(0.0, (ts - 1700000000) / 100000000.0))
        except Exception:
            pass

    return score


def consolidate_feedback_and_conflicts(needs_changes_records, target):
    """Deduplicate remedial feedback, prioritize current prompt, record conflicts."""
    prompt = (target.get('prompt', '') if target else '').casefold()
    seen_concepts = set()
    consolidated = []
    conflicts = []

    for r in needs_changes_records:
        raw_note = r.get('note', '').strip()
        if not raw_note:
            continue
        cleaned = sanitize_note(raw_note)
        if not cleaned:
            continue

        lower_note = cleaned.casefold()

        # Check conflicts with current prompt or core rules
        if re.search(r'không (?:cần |thêm |dùng )?zoom|no zoom', prompt) and 'zoom' in lower_note:
            conflicts.append({
                'topic': 'zoom',
                'feedback_note': cleaned,
                'resolved_by': 'current_prompt',
                'explanation': 'Yêu cầu hiện tại tắt zoom; bỏ qua góp ý zoom trước đây.'
            })
            continue

        if re.search(r'không (?:thêm |chèn |dùng )?(?:minh họa|đồ họa)', prompt) and ('minh họa' in lower_note or 'đồ họa' in lower_note):
            conflicts.append({
                'topic': 'illustrations',
                'feedback_note': cleaned,
                'resolved_by': 'current_prompt',
                'explanation': 'Yêu cầu hiện tại tắt minh họa; bỏ qua góp ý minh họa trước đây.'
            })
            continue

        # Deduplication based on key phrase fingerprint
        words = tuple(sorted(re.findall(r'[^\W_]+', lower_note)))
        if words in seen_concepts:
            continue
        seen_concepts.add(words)
        consolidated.append(cleaned)

    return consolidated, conflicts


class LearningStore:
    def __init__(self, data_dir):
        self.root = Path(data_dir) / 'learning'
        self.root.mkdir(parents=True, exist_ok=True)

    def records(self):
        result = []
        for path in self.root.glob('*.json'):
            try:
                raw = json.loads(path.read_text(encoding='utf-8'))
                if raw.get('schema_version') in (1, 2) and raw.get('decision') in ('approve_style', 'needs_changes') and isinstance(raw.get('note'), str) and isinstance(raw.get('visual_style'), dict):
                    migrated = migrate_record(raw)
                    if migrated:
                        result.append(migrated)
            except (ValueError, OSError):
                continue
        return sorted(result, key=lambda r: r.get('updated_at', ''), reverse=True)

    def save(self, project, decision, note, captions_checked=False):
        identifier = hashlib.sha256((project['id'] + project['output_path'] + str(project['revision'])).encode()).hexdigest()
        cleaned_note = sanitize_note(note) if note else ''
        vis_summary = visual_summary(project['edit_plan'])
        rev_ev = review_evidence(project, captions_checked)
        record = {
            'schema_version': SCHEMA_VERSION,
            'id': identifier,
            'project_id': project['id'],
            'output_path': project['output_path'],
            'revision': project['revision'],
            'decision': decision,
            'note': cleaned_note[:800],
            'captions_checked': captions_checked,
            'visual_style': vis_summary,
            'planning_mode': (project.get('job') or {}).get('planning_mode', 'unknown'),
            'updated_at': datetime.now(timezone.utc).isoformat(),
            'review_evidence': rev_ev,
            'confidence_score': 1.0 if captions_checked and rev_ev.get('output_current') else 0.7
        }
        path = self.root / (identifier + '.json')
        temporary = path.with_suffix('.tmp')
        temporary.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding='utf-8')
        os.replace(temporary, path)
        return record

    def context(self, target_criteria=None):
        raw_records = self.records()
        approved_all = [r for r in raw_records if r['decision'] == 'approve_style']
        needs_all = [r for r in raw_records if r['decision'] == 'needs_changes' and r.get('note')]

        # Rank approved examples selectively by relevance score
        scored_approved = sorted(approved_all, key=lambda r: score_relevance(r, target_criteria), reverse=True)
        selected_approved = scored_approved[:3]

        # Consolidate feedback and detect direct conflicts
        consolidated_changes, conflicts = consolidate_feedback_and_conflicts(needs_all, target_criteria)
        selected_changes = consolidated_changes[:3]

        baseline = json.loads((SKILLS_DIR / 'style_reference.json').read_text(encoding='utf-8'))
        skills = editor_skills()

        approved_examples_payload = [
            {
                'id': r.get('id', ''),
                'visual_style': r['visual_style'],
                'user_note': r['note'][:250],
                'relevance_score': round(score_relevance(r, target_criteria), 2)
            }
            for r in selected_approved
        ]

        return {
            'schema_version': SCHEMA_VERSION,
            'active_skills': [s['id'] for s in skills],
            'rules': RULES + [s['rule'] for s in skills],
            'initial_visual_reference': baseline['visual_style'],
            'requested_changes': selected_changes,
            'approved_style_examples': approved_examples_payload,
            'style_memory_diagnostics': {
                'total_records': len(raw_records),
                'approved_count': len(approved_all),
                'needs_changes_count': len(needs_all),
                'selected_reference_ids': [r.get('id', '') for r in selected_approved],
                'selection_reasons': ['relevance_scoring', 'preset_match', 'reviewed_status'],
                'conflicts_detected': conflicts,
                'target_criteria': target_criteria or {}
            }
        }

    def status(self):
        records = self.records()
        reviewed = [r for r in records if reviewed_record(r)]
        return {
            'mode': 'style_memory',
            'model_weights_trained': False,
            'schema_version': SCHEMA_VERSION,
            'available_motion_skills': [{'id': s['id'], 'name': s.get('name', s['id']), 'purpose': s.get('purpose', '')} for s in motion_skills()],
            'initial_visual_references': 1,
            'approved_styles': sum(r['decision'] == 'approve_style' for r in records),
            'needs_changes': sum(r['decision'] == 'needs_changes' for r in records),
            'reference_limit': 3,
            'active_skills': [s['id'] for s in editor_skills()],
            'reviewed_examples': len(reviewed),
            'reviewed_sources': len({r['review_evidence']['source_sha256'] for r in reviewed if r.get('review_evidence')}),
            'dataset_kind': 'style_supervision',
            'style_only_examples': sum(r['decision'] == 'approve_style' and not reviewed_record(r) for r in records)
        }

    def reviewed_records(self):
        return [r for r in self.records() if reviewed_record(r)]

    def export(self, reviewed_only=False):
        # Export style supervision only; no private transcript/brand/asset paths.
        records = self.reviewed_records() if reviewed_only else self.records()
        return '\n'.join(
            json.dumps({
                'schema_version': SCHEMA_VERSION,
                'decision': r['decision'],
                'note': r['note'],
                'captions_checked': r['captions_checked'],
                'visual_style': r['visual_style'],
                'planning_mode': r['planning_mode']
            }, ensure_ascii=False)
            for r in records if r['decision'] == 'approve_style'
        )
