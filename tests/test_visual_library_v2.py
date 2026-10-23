import copy
import json
from pathlib import Path
import pytest
from visual_library import (
    catalog,
    catalog_stats,
    library_image,
    phrase_in,
    tokens,
    apply_library_visuals,
    match_catalog_entry,
    is_real_estate_context,
    calculate_density_budget
)
from asset_resolver import AssetResolver, normalize_text, get_library_catalog
from video_branding import apply_visual_assets
from editing import validate


def test_catalog_stats_and_metadata_normalization():
    stats = catalog_stats()
    assert stats['total_records'] >= 2
    assert stats['files_existing'] >= 2
    assert stats['files_missing'] == 0
    # Every entry has standardized schema v2 fields
    for entry in stats['entries']:
        assert entry['id'] in ('ai_assistant', 'brand_strategy')
        assert entry['media_type'] == 'image'
        assert entry['topic'] in ('ai_technology', 'business_marketing')
        assert entry['origin'] == 'curated_stock'
        assert entry['usage_scope'] == 'conceptual_illustration'
        assert entry['size_bytes'] > 0


def test_multi_tier_matching_content_accuracy():
    entries = {e['id']: e for e in catalog()}
    ai_entry = entries['ai_assistant']
    brand_entry = entries['brand_strategy']

    # Tier 1: Exact phrase
    score1, tier1, matches1, _ = match_catalog_entry(ai_entry, "Chúng tôi phát triển trợ lý AI cho doanh nghiệp.")
    assert tier1 == 'exact_phrase'
    assert score1 >= 0.7
    assert any('AI' in m or 'trợ lý AI' in m for m in matches1)

    # Tier 3: Controlled synonym
    score3, tier3, matches3, _ = match_catalog_entry(ai_entry, "Hệ thống có một chatbot thông minh.")
    assert tier3 == 'exact_phrase'  # chatbot is a keyword in ai_assistant
    assert score3 >= 0.7

    # Distinct content: marketing speech matches brand_strategy, not ai_assistant
    score_brand, tier_brand, _, _ = match_catalog_entry(brand_entry, "Xây dựng chiến lược truyền thông và marketing bài bản.")
    assert score_brand >= 0.7
    assert tier_brand == 'exact_phrase'


def test_no_substring_false_matching_for_short_words():
    """Ensure 'AI' is never matched inside 'hai', 'giai đoạn', 'phải', 'trai', 'tai', or 'main'."""
    assert not phrase_in('AI', 'Hai người đang tập luyện chăm chỉ.')
    assert not phrase_in('AI', 'Chúng ta bước vào giai đoạn thứ hai.')
    assert not phrase_in('AI', 'Bạn phải kiên trì mỗi ngày.')
    assert not phrase_in('AI', 'Chàng trai trẻ đầy nhiệt huyết.')
    assert not phrase_in('AI', 'Bịt tai lại để tập trung.')
    assert not phrase_in('AI', 'Dự án đã merge vào branch main.')

    # Positive match strictly on word boundary
    assert phrase_in('AI', 'Ứng dụng AI rất hiệu quả.')
    assert phrase_in('AI', 'AI là xu hướng tương lai.')
    assert phrase_in('trợ lý AI', 'Tích hợp trợ lý AI chuyên nghiệp.')


def test_real_estate_rejects_conceptual_stock():
    """Requirement 7: Real estate property listings MUST NOT use fictional stock concepts."""
    entries = {e['id']: e for e in catalog()}
    ai_entry = entries['ai_assistant']
    brand_entry = entries['brand_strategy']

    re_speech = "Giới thiệu căn hộ chung cư cao cấp và biệt thự nghỉ dưỡng ven sông."
    assert is_real_estate_context(re_speech)

    score_ai, tier_ai, _, reason_ai = match_catalog_entry(ai_entry, re_speech)
    assert score_ai == 0.0
    assert reason_ai == 'real_estate_stock_rejected'

    score_brand, tier_brand, _, reason_brand = match_catalog_entry(brand_entry, re_speech)
    assert score_brand == 0.0
    assert reason_brand == 'real_estate_stock_rejected'


def test_density_budget_exceeds_two_images_on_longer_timelines():
    """Requirement 9: Density policy based on duration instead of hardcoded 2 images."""
    assert calculate_density_budget(4.0, 3) == 1
    assert calculate_density_budget(12.0, 4) == 2
    assert calculate_density_budget(30.0, 6) == 2
    # 60s timeline with 10 scenes can hold up to 4 visual beats
    budget_60s = calculate_density_budget(60.0, 10)
    assert budget_60s >= 4


def test_asset_resolver_authenticity_and_logo_protection(tmp_path):
    project_assets = [
        {
            'id': 'logo_01',
            'filename': 'logo.png',
            'type': 'image',
            'usage': 'logo',
            'original_name': 'MyCompany_Logo.png',
            'keywords': 'logo thương hiệu công ty'
        },
        {
            'id': 'photo_01',
            'filename': 'real_office.jpg',
            'type': 'image',
            'usage': 'photo',
            'original_name': 'Văn phòng làm việc.jpg',
            'keywords': 'văn phòng làm việc nhân viên'
        },
        {
            'id': 'video_broll_01',
            'filename': 'broll_factory.mp4',
            'type': 'video',
            'usage': 'broll',
            'original_name': 'Cảnh quay nhà máy.mp4',
            'keywords': 'nhà máy sản xuất quy trình',
            'metadata': {'duration': 15.5},
            'source_in': 2.0
        }
    ]

    # Create dummy files
    (tmp_path / 'logo.png').write_text('fake logo')
    (tmp_path / 'real_office.jpg').write_text('fake photo')
    (tmp_path / 'broll_factory.mp4').write_text('fake video')

    resolver = AssetResolver(project_assets, tmp_path, tmp_path)

    # 1. Logo cannot be resolved as an illustration when searching by keyword 'thương hiệu'
    res_ill = resolver.resolve_visual(query='thương hiệu')
    assert res_ill['asset_id'] != 'logo_01'
    assert res_ill['source'] != 'user_uploaded'

    # 2. Authentic user photo is resolved when relevant
    res_photo = resolver.resolve_visual(query='văn phòng làm việc')
    assert res_photo['asset_id'] == 'photo_01'
    assert res_photo['source'] == 'user_uploaded'
    assert res_photo['media_type'] == 'image'

    # 3. Authentic B-roll video preserves video media type and duration without silent downgrade
    res_video = resolver.resolve_visual(query='nhà máy sản xuất')
    assert res_video['asset_id'] == 'video_broll_01'
    assert res_video['source'] == 'user_uploaded'
    assert res_video['media_type'] == 'video'
    assert res_video['duration'] == 15.5
    assert res_video['source_in'] == 2.0


def test_schema_v1_migration_compatibility(tmp_path):
    """Requirement 10: Backward compatibility with schema_version 1."""
    legacy_catalog = {
        "schema_version": 1,
        "images": [
            {
                "id": "legacy_item",
                "file": "ai-assistant.webp",
                "keywords": ["trí tuệ", "máy tính"],
                "description": "Legacy item from schema v1."
            }
        ]
    }
    custom_cat_file = tmp_path / 'legacy_catalog.json'
    custom_cat_file.write_text(json.dumps(legacy_catalog), encoding='utf-8')

    loaded = catalog(custom_path=custom_cat_file)
    legacy = next((x for x in loaded if x['id'] == 'legacy_item'), None)
    assert legacy is not None
    # Verify auto-migrated metadata
    assert legacy['media_type'] == 'image'
    assert legacy['origin'] == 'curated_stock'
    assert legacy['aspect_ratio'] == '16:9'
    assert legacy['license'] == 'DANAVA Studio Built-in Graphic / Local Illustration'
    assert legacy['usage_scope'] == 'conceptual_illustration'


def test_missing_or_tampered_asset_fails_safely():
    """Requirement 12: Missing or unsafe path raises explicit ValueError."""
    with pytest.raises(ValueError, match="không tồn tại"):
        library_image("non_existent_id")

    with pytest.raises(ValueError):
        library_image("../../../etc/passwd")

    with pytest.raises(ValueError):
        library_image("bad/path/injection")


def test_image_insertion_smoothness_and_source_in_sync():
    """Verify that inserting visuals does not create jarring 0.4s flash frames,
    preserves minimum chunk durations >= 1.6s, and keeps source_in synchronized with timeline."""
    plan = {
        'schema_version': 2,
        'assets': [
            {'id': 'video_root', 'type': 'video', 'filename': 'root.mp4', 'metadata': {'duration': 16.6}}
        ],
        'video_clips': [
            {'id': 'c1', 'asset_id': 'video_root', 'source_in': 0.0, 'source_out': 16.6, 'duration': 16.6, 'timeline_start': 0.0}
        ],
        'output_settings': {'width': 720, 'height': 1280, 'fps': 30},
        'subtitles': [],
        'branding': {'illustrations': True},
        'director': {'topic': 'công nghệ'},
        'storyboard': [
            {
                'scene_id': 'sc_open',
                'scene_type': 'talking_head',
                'asset_id': 'video_root',
                'timeline_start': 0.0,
                'source_in': 0.0,
                'duration': 4.0,
                'transcript_meaning': 'Xin chào các bạn đến với buổi chia sẻ.'
            },
            {
                'scene_id': 'sc_ai',
                'scene_type': 'talking_head',
                'asset_id': 'video_root',
                'timeline_start': 4.0,
                'source_in': 4.0,
                'duration': 8.6,
                'transcript_meaning': 'Hôm nay chúng ta cùng tìm hiểu về trợ lý AI thông minh.'
            },
            {
                'scene_id': 'sc_close',
                'scene_type': 'talking_head',
                'asset_id': 'video_root',
                'timeline_start': 12.6,
                'source_in': 12.6,
                'duration': 4.0,
                'transcript_meaning': 'Cảm ơn và hẹn gặp lại các bạn.'
            }
        ]
    }

    result = apply_library_visuals(plan, prompt='Tạo video giới thiệu trợ lý AI')
    sc_ai_chunks = [s for s in result['storyboard'] if s['scene_id'].startswith('sc_ai')]
    assert len(sc_ai_chunks) >= 1

    # 1. No chunk should ever be a jarring 0.4s flash frame
    for ch in sc_ai_chunks:
        assert ch['duration'] >= 1.6, f"Chunk {ch['scene_id']} duration {ch['duration']} is too short (< 1.6s)"

    # 2. Total duration must be preserved exactly
    assert abs(sum(ch['duration'] for ch in sc_ai_chunks) - 8.6) < 1e-4

    # 3. source_in MUST be offset correctly matching timeline_start
    orig_start = 4.0
    orig_source_in = 4.0
    for ch in sc_ai_chunks:
        expected_source_in = orig_source_in + (ch['timeline_start'] - orig_start)
        assert abs(ch['source_in'] - expected_source_in) < 1e-4, (
            f"Chunk {ch['scene_id']} has desynced source_in: expected {expected_source_in}, got {ch['source_in']}"
        )

