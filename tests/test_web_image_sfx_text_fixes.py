"""Tests reproducing and verifying:
1. Web image matching and relevance diagnostics (reproducing pool vs face recognition bug).
2. 'No SFX' override removing all schema SFX kinds while preserving music & voice.
3. 'No Text' override removing brand_name from ASS and disabling all text layers.
"""
import copy
from pathlib import Path
import pytest

from video_branding import apply_visual_assets
from style_presets import apply_style_preset
from storyboard_style import write_storyboard_ass
from test_pipeline import media, new_project, client


def test_reproduce_pool_image_assigned_to_facial_recognition_unrelated():
    """Vấn đề 1: Ảnh 'Bể bơi căn hộ' có alt/name nhưng không có keywords.
    Transcript chỉ nói về 'nhận dạng khuôn mặt'.
    Hiện tại: bị gán sai vào cảnh nhận dạng khuôn mặt do fallback candidates[0].
    Yêu cầu: Không được gán vào cảnh không liên quan, phải bỏ qua và ghi cảnh báo/chẩn đoán.
    """
    plan = {
        'assets': [
            {'id': 'video_source', 'type': 'video', 'filename': 'v.mp4', 'metadata': {'duration': 10}},
            {
                'id': 'web_pool_img',
                'type': 'image',
                'filename': 'pool.jpg',
                'original_name': 'Bể bơi căn hộ cao cấp',
                'source': 'web_reference',
                'metadata': {
                    'width': 1280,
                    'height': 720,
                    'reference_alt': 'Bể bơi căn hộ sang trọng ngoài trời',
                    'source_url': 'https://example.com/pool.jpg'
                }
            }
        ],
        'video_clips': [{'asset_id': 'video_source', 'source_in': 0, 'duration': 10, 'timeline_start': 0}],
        'storyboard': [
            {
                'scene_id': 'sc_0',
                'scene_type': 'talking_head',
                'timeline_start': 0,
                'duration': 5,
                'transcript_meaning': 'Hệ thống nhận dạng khuôn mặt bằng trí tuệ nhân tạo và camera giám sát thông minh.'
            },
            {
                'scene_id': 'sc_1',
                'scene_type': 'talking_head',
                'timeline_start': 5,
                'duration': 5,
                'transcript_meaning': 'Thuật toán bảo mật sinh trắc học và kiểm soát cửa ra vào tự động.'
            }
        ],
        'audio_tracks': [],
        'effect_keyframes': [],
        'visual_overlays': [],
        'text_overlays': [],
        'output_settings': {'width': 720, 'height': 1280, 'fps': 30}
    }

    result = apply_visual_assets(plan, prompt='Dựng video', image_asset_ids=['web_pool_img'])

    # Sau khi sửa: cả 2 cảnh đều không liên quan đến bể bơi căn hộ
    # Ảnh bể bơi KHÔNG được gán vào bất kỳ cảnh nào
    assigned_assets = [sc.get('visual_asset_id') for sc in result['storyboard']]
    assert 'web_pool_img' not in assigned_assets, "Ảnh bể bơi không được gán vào cảnh nhận dạng khuôn mặt!"

    # Phải có warning và diagnostic giải thích rõ
    warnings = result.get('director', {}).get('warnings', [])
    assert any('Bể bơi' in w or 'phù hợp' in w for w in warnings)

    diagnostics = result.get('director', {}).get('visual_diagnostics', [])
    pool_diag = next((d for d in diagnostics if d.get('selected_id') == 'web_pool_img'), None)
    assert pool_diag is not None
    assert pool_diag['scene_index'] == -1
    assert pool_diag['relevance_score'] == 0.0


def test_reproduce_no_sfx_keeps_whoosh_pop_tracks_bug():
    """Vấn đề 2: Track SFX dùng kind='whoosh', kind='pop', v.v.
    Khi prompt='không sfx', code cũ chỉ lọc kind!='sfx' nên giữ lại whoosh/pop.
    Yêu cầu: Phải loại bỏ toàn bộ whoosh/pop/impact/chime/click, giữ lại music và voice.
    """
    plan = {
        'assets': [{'id': 'v1', 'type': 'video', 'filename': 'v.mp4', 'metadata': {'duration': 10}}],
        'video_clips': [{'asset_id': 'v1', 'source_in': 0, 'duration': 10, 'timeline_start': 0}],
        'audio_tracks': [
            {'id': 'bg_music', 'kind': 'music', 'timeline_start': 0, 'duration': 10, 'volume': 0.15},
            {'id': 'accent_whoosh', 'kind': 'whoosh', 'timeline_start': 2.0, 'duration': 0.5, 'volume': 0.2},
            {'id': 'click_sound', 'kind': 'click', 'timeline_start': 4.0, 'duration': 0.3, 'volume': 0.1},
            {'id': 'voiceover_track', 'kind': 'voice', 'timeline_start': 0, 'duration': 10, 'volume': 1.0}
        ],
        'storyboard': [
            {'scene_id': 'sc_0', 'scene_type': 'talking_head', 'timeline_start': 0, 'duration': 5, 'sound_effect': 'whoosh'},
            {'scene_id': 'sc_1', 'scene_type': 'talking_head', 'timeline_start': 5, 'duration': 5, 'sound_effect': 'pop'}
        ],
        'effect_keyframes': [],
        'visual_overlays': [],
        'text_overlays': []
    }

    for preset_id in ('explainer', 'inspirational', 'real_estate'):
        styled = apply_style_preset(copy.deepcopy(plan), identifier=preset_id, prompt='không sfx')

        # 1. Các track whoosh, click phải bị xóa
        track_kinds = [t.get('kind') for t in styled.get('audio_tracks', [])]
        assert 'whoosh' not in track_kinds, f"Preset {preset_id} phải xóa whoosh track"
        assert 'click' not in track_kinds, f"Preset {preset_id} phải xóa click track"
        assert 'pop' not in track_kinds, f"Preset {preset_id} phải xóa pop track"

        # 2. Track music và voice vẫn được giữ
        assert 'music' in track_kinds, f"Preset {preset_id} phải giữ music track"
        assert 'voice' in track_kinds, f"Preset {preset_id} phải giữ voice track"

        # 3. Tất cả sound_effect trong storyboard phải là 'none'
        for sc in styled.get('storyboard', []):
            assert sc.get('sound_effect') == 'none', f"Preset {preset_id} scene {sc.get('scene_id')} phải có sound_effect='none'"


def test_reproduce_no_text_leaves_brand_in_ass_bug(tmp_path):
    """Vấn đề 3: prompt='không chữ' xóa headline/caption nhưng vẫn ghi brand_name vào file ASS.
    Yêu cầu: 'Không chữ' phải tắt cả brand_name trong file ASS.
    'Không phụ đề' chỉ tắt caption, vẫn giữ brand_name.
    """
    plan = {
        'assets': [{'id': 'v1', 'type': 'video', 'filename': 'v.mp4', 'metadata': {'duration': 10}}],
        'video_clips': [{'asset_id': 'v1', 'source_in': 0, 'duration': 10, 'timeline_start': 0}],
        'subtitles': [{'asset_id': 'v1', 'start': 0, 'end': 5, 'text': 'Xin chào mọi người'}],
        'branding': {'brand_name': 'THUONG_HIEU_VIP'},
        'storyboard': [
            {'scene_id': 'sc_0', 'scene_type': 'talking_head', 'timeline_start': 0, 'duration': 5, 'headline': 'TIÊU ĐỀ 1'},
            {'scene_id': 'sc_1', 'scene_type': 'talking_head', 'timeline_start': 5, 'duration': 5, 'headline': 'TIÊU ĐỀ 2'}
        ],
        'audio_tracks': [],
        'effect_keyframes': [],
        'visual_overlays': [],
        'text_overlays': []
    }

    # TH1: "không chữ"
    no_text_plan = apply_style_preset(copy.deepcopy(plan), identifier='explainer', prompt='video không chữ')
    ass_path = tmp_path / 'no_text.ass'
    write_storyboard_ass(ass_path, no_text_plan, 720, 1280)
    ass_content = ass_path.read_text(encoding='utf-8')

    assert 'THUONG_HIEU_VIP' not in ass_content, "Khi yêu cầu 'không chữ', brand_name KHÔNG được xuất hiện trong ASS!"
    assert 'TIÊU ĐỀ' not in ass_content, "Khi yêu cầu 'không chữ', headline KHÔNG được xuất hiện trong ASS!"
    assert 'Dialogue:' not in ass_content, "Khi yêu cầu 'không chữ', không được có dòng Dialogue nào trong ASS!"

    # TH2: "không phụ đề" (chỉ tắt caption, vẫn giữ brand_name và headline)
    no_caption_plan = apply_style_preset(copy.deepcopy(plan), identifier='explainer', prompt='không phụ đề')
    ass_path2 = tmp_path / 'no_caption.ass'
    write_storyboard_ass(ass_path2, no_caption_plan, 720, 1280)
    ass_content2 = ass_path2.read_text(encoding='utf-8')

    assert 'THUONG_HIEU_VIP' in ass_content2, "Khi chỉ yêu cầu 'không phụ đề', brand_name VẪN được hiển thị!"
    assert 'Xin chào' not in ass_content2, "Khi yêu cầu 'không phụ đề', caption lời thoại phải bị tắt!"


def test_web_image_assigned_to_matching_scene_with_score_and_terms():
    """Kiểm tra: Khi có cảnh nói đúng chủ đề (hồ bơi / căn hộ), ảnh web được chọn chuẩn xác
    với điểm số rõ ràng và danh sách cụm từ khớp (matched_terms).
    """
    plan = {
        'assets': [
            {'id': 'video_source', 'type': 'video', 'filename': 'v.mp4', 'metadata': {'duration': 15}},
            {
                'id': 'web_pool_img',
                'type': 'image',
                'filename': 'pool.jpg',
                'original_name': 'Bể bơi căn hộ cao cấp',
                'source': 'web_reference',
                'metadata': {
                    'width': 1280,
                    'height': 720,
                    'reference_alt': 'Bể bơi căn hộ ngoài trời',
                    'search_terms': ['bể bơi căn hộ', 'bể bơi', 'căn hộ cao cấp'],
                    'source_url': 'https://example.com/pool.jpg'
                }
            }
        ],
        'video_clips': [{'asset_id': 'video_source', 'source_in': 0, 'duration': 15, 'timeline_start': 0}],
        'storyboard': [
            {
                'scene_id': 'sc_intro',
                'scene_type': 'talking_head',
                'timeline_start': 0,
                'duration': 5,
                'transcript_meaning': 'Xin chào mừng quý vị đến với buổi giới thiệu ngày hôm nay.'
            },
            {
                'scene_id': 'sc_pool',
                'scene_type': 'talking_head',
                'timeline_start': 5,
                'duration': 5,
                'transcript_meaning': 'Khuôn viên dự án sở hữu tiện ích bể bơi căn hộ cao cấp chuẩn nghỉ dưỡng.'
            },
            {
                'scene_id': 'sc_tech',
                'scene_type': 'talking_head',
                'timeline_start': 10,
                'duration': 5,
                'transcript_meaning': 'Hệ thống an ninh và camera giám sát thông minh hoạt động 24/7.'
            }
        ],
        'audio_tracks': [],
        'effect_keyframes': [],
        'visual_overlays': [],
        'text_overlays': [],
        'output_settings': {'width': 720, 'height': 1280, 'fps': 30}
    }

    result = apply_visual_assets(plan, prompt='Dựng video', image_asset_ids=['web_pool_img'])

    # Ảnh bể bơi phải được gán vào đúng cảnh 1 (sc_pool), không gán vào intro hay tech
    sc_pool = result['storyboard'][1]
    assert sc_pool.get('visual_asset_id') == 'web_pool_img'
    assert result['storyboard'][0].get('visual_asset_id') is None
    assert result['storyboard'][2].get('visual_asset_id') is None

    # Kiểm tra diagnostics ghi nhận điểm và cụm từ khớp
    diagnostics = result.get('director', {}).get('visual_diagnostics', [])
    diag = next((d for d in diagnostics if d.get('selected_id') == 'web_pool_img'), None)
    assert diag is not None
    assert diag['scene_index'] == 1
    assert diag['scene_id'] == 'sc_pool'
    assert diag['relevance_score'] >= 2.0
    assert diag['tier'] == 'semantic_match'
    assert any('bể bơi' in t or 'căn hộ' in t for t in diag['matched_terms'])


def test_real_render_with_no_text_and_no_sfx(media, monkeypatch):
    """Kiểm tra render thực tế qua make-video với prompt 'không chữ, không sfx'.
    Xác nhận video MP4 được tạo thành công, không có track SFX và ASS sạch chữ.
    """
    from test_pipeline import client, new_project
    import main
    from editing import probe

    project = new_project(media)
    monkeypatch.setenv('OLLAMA_URL', 'http://127.0.0.1:9')

    # Yêu cầu make-video với cả 2 cờ: không chữ và không SFX
    body = {
        'prompt': 'video tối giản, không chữ, không sfx',
        'brand_name': 'TEST_HIDDEN_BRAND',
        'illustrations': False
    }
    r = client.post(f"/api/projects/{project['id']}/make-video", json=body)
    assert r.status_code == 200, r.text

    proj = client.get(f"/api/projects/{project['id']}").json()
    assert proj['job']['status'] == 'succeeded', proj['job']

    edit_plan = proj['edit_plan']
    # 1. Chữ bị tắt hoàn toàn
    assert edit_plan.get('show_text') is False or edit_plan.get('text_enabled') is False
    assert edit_plan.get('show_captions') is False

    # 2. Không có track SFX nào
    track_kinds = [t.get('kind') for t in edit_plan.get('audio_tracks', [])]
    assert not any(k in ('whoosh', 'pop', 'click', 'impact', 'chime', 'sfx') for k in track_kinds)

    # 3. Output video thực tế tồn tại và có âm thanh giọng nói nguồn
    out_file = main.OUTPUTS_DIR / proj['output_path'].split('/')[-1]
    assert out_file.exists()
    info = probe(out_file)
    assert info['has_audio'] is True
    assert info['duration'] > 0

