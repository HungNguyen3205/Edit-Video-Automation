"""Comprehensive test suite for Selective Style Feedback Memory (LearningStore v2).

Validates:
- Relevance-based retrieval: older matching example selected over newer unmatching examples.
- Remedial feedback deduplication & conflict resolution against current prompt.
- Tiered context degradation: long context degrades gracefully to core rules before dropping.
- Privacy & sanitization: no transcript, customer names, or private paths leaked.
- Backward compatibility & schema migration from v1 to v2.
- Truthful memory_applied and detailed diagnostics reporting.
- Clear mathematical definitions for all 6 editorial style features.
"""
import copy
import json
import threading
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

import main
import automatic_director
from learning_store import (
    LearningStore,
    SCHEMA_VERSION,
    visual_summary,
    migrate_record,
    sanitize_note,
    score_relevance,
    consolidate_feedback_and_conflicts
)


def make_dummy_project(proj_id, preset='explainer', motion='clean', note='Duyệt phong cách', decision='approve_style'):
    return {
        'id': proj_id,
        'revision': 1,
        'output_path': f'/outputs/{proj_id}.mp4',
        'output_revision': 1,
        'job': {'status': 'succeeded', 'planning_mode': 'ai'},
        'edit_plan': {
            'style_preset': {'id': preset, 'version': 1},
            'motion_style': {'preset': motion},
            'typography': {'profile_id': 'barlow_condensed'},
            'assets': [{'id': 'a1', 'sha256': 'a' * 64}],
            'video_clips': [{'asset_id': 'a1', 'source_in': 0, 'duration': 12.0, 'timeline_start': 0}],
            'subtitles': [{'id': 's1', 'start': 0, 'end': 4, 'text': 'Nội dung video'}],
            'storyboard': [
                {'scene_id': 'sc1', 'scene_type': 'talking_head', 'duration': 4.0, 'zoom_scale': 1.05, 'sound_effect': 'none', 'animation_in': 'pop_in', 'headline': 'TIÊU ĐỀ 1'},
                {'scene_id': 'sc2', 'scene_type': 'explainer_card', 'duration': 4.0, 'zoom_scale': 1.0, 'sound_effect': 'whoosh', 'animation_in': 'slide_up', 'headline': 'TIÊU ĐỀ 2'},
                {'scene_id': 'sc3', 'scene_type': 'talking_head', 'duration': 4.0, 'zoom_scale': 1.04, 'sound_effect': 'chime', 'animation_in': 'fade', 'headline': 'TIÊU ĐỀ 3'}
            ]
        }
    }


def test_visual_summary_editorial_features():
    """Verify mathematical calculation and presence of all 6 editorial style features."""
    p = make_dummy_project('p1')
    vs = visual_summary(p['edit_plan'])

    assert vs['style_preset'] == 'explainer'
    assert vs['motion_preset'] == 'clean'
    # 1 scene explainer_card out of 3 total (4s / 12s = 0.33)
    assert vs['illustration_duration_ratio'] == pytest.approx(0.33, rel=1e-2)
    # median scene duration = 4.0s
    assert vs['median_scene_duration'] == 4.0
    # transitions used
    assert sorted(vs['transition_types']) == ['fade', 'pop_in', 'slide_up']
    # active zoom shots: [1.05, 1.04] -> median = 1.045
    assert vs['zoom_amplitude_median'] == pytest.approx(1.045, rel=1e-2)
    # caption profile
    assert vs['caption_preset'] == 'barlow_condensed'
    # sfx density: 2 sfx in 12s (0.2 min) -> 2 / 0.2 = 10.0 sfx/min
    assert vs['sfx_density_per_minute'] == 10.0


def test_privacy_sanitization_filters_paths_and_identifiers():
    """Verify that private file paths, customer references and brand claims are sanitized."""
    raw = "Làm chữ ngắn hơn ở /outputs/proj_123.mp4 theo yêu cầu khách hàng ABC Corp tại C:\\Users\\Admin\\clip.mp4"
    cleaned = sanitize_note(raw)

    assert '/outputs/' not in cleaned
    assert 'C:\\Users' not in cleaned
    assert 'khách hàng ABC Corp' not in cleaned
    assert 'Làm chữ ngắn hơn' in cleaned


def test_relevance_retrieval_prefers_matching_older_example_over_newer_mismatches(tmp_path):
    """An older example matching style_preset and topic must be ranked above newer irrelevant examples."""
    store = LearningStore(tmp_path)

    # 1 older matching explainer example
    p_old = make_dummy_project('old_match', preset='explainer', motion='clean', note='Phong cách chuyên gia tài chính giải thích rõ ràng')
    rec_old = store.save(p_old, 'approve_style', 'Phong cách chuyên gia tài chính giải thích rõ ràng')
    rec_old['updated_at'] = '2026-01-01T00:00:00Z'
    (tmp_path / 'learning' / f"{rec_old['id']}.json").write_text(json.dumps(rec_old), encoding='utf-8')

    # 3 newer mismatching dynamic_reels examples
    for i in range(3):
        p_new = make_dummy_project(f'new_mismatch_{i}', preset='dynamic_reels', motion='dynamic_explainer', note='Fast cuts zoom mạnh')
        rec_new = store.save(p_new, 'approve_style', 'Fast cuts zoom mạnh')
        rec_new['updated_at'] = f'2026-10-0{i+1}T00:00:00Z'
        (tmp_path / 'learning' / f"{rec_new['id']}.json").write_text(json.dumps(rec_new), encoding='utf-8')

    # Query with target criteria matching the older project
    target_criteria = {
        'style_preset': 'explainer',
        'motion_preset': 'clean',
        'prompt': 'Video giải thích tài chính cho chuyên gia'
    }

    ctx = store.context(target_criteria=target_criteria)
    examples = ctx['approved_style_examples']

    assert len(examples) > 0
    # The older matching example must be selected first because of higher relevance score
    assert examples[0]['id'] == rec_old['id']
    assert examples[0]['visual_style']['style_preset'] == 'explainer'
    assert examples[0]['relevance_score'] > examples[-1]['relevance_score']


def test_conflict_detection_and_resolution(tmp_path):
    """Past remedial feedback conflicting with current user prompt is resolved in favor of the current prompt."""
    store = LearningStore(tmp_path)

    # Past feedback asked for more zoom
    p = make_dummy_project('p_zoom', preset='explainer')
    store.save(p, 'needs_changes', 'Thêm zoom mạnh ở các cảnh mở đầu')

    # Current target explicitly disables zoom
    target_criteria = {
        'style_preset': 'explainer',
        'prompt': 'Dựng video đơn giản, không zoom, giữ camera cố định'
    }

    ctx = store.context(target_criteria=target_criteria)
    diag = ctx['style_memory_diagnostics']

    # The conflicting feedback must be detected and filtered out of active requested_changes
    assert 'Thêm zoom' not in ' '.join(ctx['requested_changes'])
    assert len(diag['conflicts_detected']) == 1
    conflict = diag['conflicts_detected'][0]
    assert conflict['topic'] == 'zoom'
    assert conflict['resolved_by'] == 'current_prompt'


def test_backward_compatibility_v1_migration():
    """V1 records missing schema v2 fields are migrated seamlessly with safe fallback defaults."""
    v1_record = {
        'schema_version': 1,
        'id': 'v1_hash',
        'decision': 'approve_style',
        'note': 'Phong cách tốt',
        'captions_checked': False,
        'visual_style': {
            'motion_preset': 'clean',
            'font_profile': 'legacy',
            'scene_types': ['talking_head'],
            'scene_count': 1,
            'illustration_fraction': 0.0,
            'headline_words_median': 3
        }
    }

    migrated = migrate_record(v1_record)
    assert migrated['schema_version'] == SCHEMA_VERSION
    vs = migrated['visual_style']
    assert vs['style_preset'] == 'explainer'
    assert vs['illustration_duration_ratio'] == 0.0
    assert vs['median_scene_duration'] == 4.0
    assert vs['transition_types'] == ['pop_in']
    assert vs['zoom_amplitude_median'] == 1.04
    assert vs['caption_preset'] == 'legacy'
    assert vs['sfx_density_per_minute'] == 0.0


def test_tiered_context_degradation_preserves_core_rules_before_dropping(tmp_path, monkeypatch):
    """When context exceeds budget, tiered degradation keeps core rules instead of discarding all memory."""
    plan = {
        'id': 'test-plan',
        'style_preset': {'id': 'explainer', 'version': 1},
        'output_settings': {'fps': 30, 'width': 720, 'height': 1280},
        'assets': [{'id': 'a1', 'type': 'video', 'filename': 'v.mp4', 'metadata': {'duration': 10.0, 'has_audio': True}}],
        'video_clips': [{'id': 'c1', 'asset_id': 'a1', 'source_in': 0, 'duration': 10.0, 'timeline_start': 0}],
        'subtitles': [{'id': 's1', 'start': 0, 'end': 10, 'text': 'Lời thoại mẫu dài vừa phải.'}],
        'learning_context': {
            'rules': ['Quy tắc phong cách 1', 'Quy tắc phong cách 2'],
            'approved_style_examples': [
                {'id': 'e1', 'visual_style': {'style_preset': 'explainer'}, 'user_note': 'Note 1' * 200},
                {'id': 'e2', 'visual_style': {'style_preset': 'explainer'}, 'user_note': 'Note 2' * 200},
                {'id': 'e3', 'visual_style': {'style_preset': 'explainer'}, 'user_note': 'Note 3' * 200}
            ],
            'requested_changes': ['Sửa đổi 1' * 200, 'Sửa đổi 2' * 200],
            'style_memory_diagnostics': {'total_records': 3}
        }
    }

    seen_contexts = []

    def fake_chat(messages, event, schema=None):
        ctx = json.loads(messages[1]['content'])
        seen_contexts.append(ctx)
        return json.dumps({
            'summary': 'Kế hoạch',
            'scenes': [{'i': 0, 't': 'talking_head', 'h': 'TIÊU ĐỀ', 'z': 1.0}],
            'captions': True,
            'font_style': 'auto'
        })

    monkeypatch.setattr(automatic_director, 'chat', fake_chat)
    event = threading.Event()
    event.ai_diagnostics = {}

    # Artificially expand example payload to trigger Tier 2 (compacted)
    plan['learning_context']['approved_style_examples'][0]['user_note'] = 'X' * 30000
    plan['learning_context']['approved_style_examples'][1]['user_note'] = 'Y' * 20000

    res = automatic_director.automatic_direction(plan, 'Dựng video', tmp_path, tmp_path, event)

    assert event.style_memory_applied is True
    # Verify that memory was compacted rather than completely dropped
    assert event.style_memory_tier in ('compacted', 'core_only')
    assert 'style_guidance' in seen_contexts[0]
    assert 'rules' in seen_contexts[0]['style_guidance']


def test_diagnostics_report_truthful_memory_status(tmp_path, monkeypatch):
    """Director diagnostics must truthfully state whether style memory was applied and details of selection."""
    plan = {
        'id': 'diag-test',
        'style_preset': {'id': 'explainer', 'version': 1},
        'output_settings': {'fps': 30, 'width': 720, 'height': 1280},
        'assets': [{'id': 'a1', 'type': 'video', 'filename': 'v.mp4', 'metadata': {'duration': 8.0, 'has_audio': True}}],
        'video_clips': [{'id': 'c1', 'asset_id': 'a1', 'source_in': 0, 'duration': 8.0, 'timeline_start': 0}],
        'subtitles': [{'id': 's1', 'start': 0, 'end': 8, 'text': 'Lời thoại chuẩn'}],
        'learning_context': {
            'rules': ['Quy tắc 1'],
            'approved_style_examples': [{'id': 'ref_101', 'visual_style': {'style_preset': 'explainer'}, 'user_note': 'Đẹp'}],
            'requested_changes': [],
            'style_memory_diagnostics': {
                'total_records': 5,
                'selected_reference_ids': ['ref_101'],
                'selection_reasons': ['relevance_scoring'],
                'conflicts_detected': []
            }
        }
    }

    def fake_chat(messages, event, schema=None):
        return json.dumps({
            'summary': 'Kế hoạch',
            'scenes': [{'i': 0, 't': 'talking_head', 'h': 'TIÊU ĐỀ', 'z': 1.0}],
            'captions': True,
            'font_style': 'auto'
        })

    monkeypatch.setattr(automatic_director, 'chat', fake_chat)
    event = threading.Event()
    event.ai_diagnostics = {}

    res = automatic_director.automatic_direction(plan, 'Dựng video đẹp', tmp_path, tmp_path, event)

    style_diag = res['director']['style_memory']
    assert style_diag['mode'] == 'style_memory'
    assert style_diag['model_weights_trained'] is False
    assert style_diag['memory_applied'] is True
    assert style_diag['tier_applied'] == 'full'
    assert style_diag['total_records'] == 5
    assert style_diag['selected_examples_count'] == 1
    assert style_diag['reference_ids'] == ['ref_101']
    assert style_diag['applied_rules'] == 1
