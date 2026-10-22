"""Comprehensive tests for balanced graphics, style_preset policies, and diagnostics."""
import threading
import pytest
from automatic_director import SceneChoice, balance_graphics, fallback_direction, semantic_units, apply_choices

def test_ten_valid_process_scenes_retained_in_explainer():
    """Verify that in explainer style, 10 valid distinct process scenes are retained."""
    steps = [
        'Khởi tạo dự án', 'Thu thập yêu cầu', 'Phân tích thiết kế',
        'Lập trình backend', 'Lập trình frontend', 'Kiểm thử tích hợp',
        'Triển khai hệ thống', 'Vận hành giám sát', 'Bảo trì định kỳ',
        'Cải tiến tính năng'
    ]
    texts = ['Mở đầu video'] + steps + ['Kết thúc video']
    units = [{'scene_index': i, 'start': i * 4.0, 'end': (i + 1) * 4.0, 'text': text} for i, text in enumerate(texts)]
    
    choices = {}
    for i, text in enumerate(texts):
        if 0 < i < len(texts) - 1:
            choices[i] = SceneChoice(
                scene_index=i,
                scene_type='explainer_card',
                headline=text,
                badge_text='',
                graphic_kind='process',
                graphic_title=text,
                graphic_items=text.split()[:3],
                sound_effect='whoosh'
            )
        else:
            choices[i] = SceneChoice(
                scene_index=i,
                scene_type='talking_head',
                headline=text,
                badge_text='',
                graphic_kind='chat',
                graphic_title='',
                graphic_items=[],
                sound_effect='none'
            )
            
    total = len(texts) * 4.0
    diagnostics = []
    plan = {
        'style_preset': {'id': 'explainer'},
        'output_settings': {'fps': 30},
        'has_speaker': True,
        'assets': []
    }
    
    balance_graphics(choices, units, 'Minh họa sinh động', total, style_preset='explainer', plan=plan, diagnostics=diagnostics)
    graphic_scenes = [i for i, c in choices.items() if c.scene_type != 'talking_head']
    
    # Requirement: 10 valid process scenes must NOT be reduced to 1!
    assert len(graphic_scenes) == 10
    assert all(choices[i].scene_type == 'explainer_card' for i in range(1, 11))
    assert choices[0].scene_type == 'talking_head'
    assert choices[11].scene_type == 'talking_head'
    # Check sound effect preserved
    assert all(choices[i].sound_effect == 'whoosh' for i in range(1, 11))


def test_invalid_scenes_demoted_with_diagnostics_reason():
    """Verify that ungrounded, short, duplicate, or excluded scenes are demoted with clear diagnostics."""
    texts = [
        'Mở đầu',
        'Khởi tạo hệ thống hợp lệ',     # 1: Valid
        'Thiếu tiêu đề',                # 2: Invalid (empty title)
        'Thiếu danh sách mục',          # 3: Invalid (< 2 items)
        'Bịa đặt thuật toán siêu việt', # 4: Invalid (unsupported words)
        'Thời lượng siêu ngắn',         # 5: Invalid (too short dur)
        'Trùng lặp nội dung',           # 6: Valid 1st
        'Trùng lặp nội dung lặp lại',   # 7: Duplicate of 6
        'Kết thúc'
    ]
    # Unit 5 is given a duration of 0.4s (< min_graphic_duration 1.0s)
    units = []
    cursor = 0.0
    for i, text in enumerate(texts):
        dur = 0.4 if i == 5 else 4.0
        units.append({'scene_index': i, 'start': cursor, 'end': cursor + dur, 'text': text})
        cursor += dur

    choices = {
        0: SceneChoice(scene_index=0, scene_type='talking_head', headline='Mở đầu', badge_text='', graphic_kind='chat', graphic_title='', graphic_items=[], sound_effect='none'),
        1: SceneChoice(scene_index=1, scene_type='explainer_card', headline='Khởi tạo hệ thống', badge_text='', graphic_kind='process', graphic_title='Khởi tạo', graphic_items=['Khởi tạo', 'Hệ thống'], sound_effect='whoosh'),
        2: SceneChoice(scene_index=2, scene_type='explainer_card', headline='Thiếu tiêu đề', badge_text='', graphic_kind='process', graphic_title='', graphic_items=['Tiêu', 'đề'], sound_effect='whoosh'),
        3: SceneChoice(scene_index=3, scene_type='explainer_card', headline='Thiếu danh sách mục', badge_text='', graphic_kind='process', graphic_title='Danh sách', graphic_items=['Mục một'], sound_effect='whoosh'),
        4: SceneChoice(scene_index=4, scene_type='explainer_card', headline='Bịa đặt thuật toán siêu việt', badge_text='', graphic_kind='process', graphic_title='Thuật toán', graphic_items=['Siêu việt', 'Đỉnh cao'], sound_effect='whoosh'),
        5: SceneChoice(scene_index=5, scene_type='explainer_card', headline='Thời lượng siêu ngắn', badge_text='', graphic_kind='process', graphic_title='Thời lượng', graphic_items=['Thời', 'lượng'], sound_effect='whoosh'),
        6: SceneChoice(scene_index=6, scene_type='explainer_card', headline='Trùng lặp nội dung', badge_text='', graphic_kind='process', graphic_title='Nội dung', graphic_items=['Trùng', 'lặp'], sound_effect='whoosh'),
        7: SceneChoice(scene_index=7, scene_type='explainer_card', headline='Trùng lặp nội dung lặp lại', badge_text='', graphic_kind='process', graphic_title='Nội dung', graphic_items=['Trùng', 'lặp'], sound_effect='whoosh'),
        8: SceneChoice(scene_index=8, scene_type='talking_head', headline='Kết thúc', badge_text='', graphic_kind='chat', graphic_title='', graphic_items=[], sound_effect='none'),
    }

    diagnostics = []
    plan = {'style_preset': {'id': 'explainer'}, 'output_settings': {'fps': 30}, 'has_speaker': True, 'assets': []}
    balance_graphics(choices, units, 'Minh họa sinh động', cursor, style_preset='explainer', plan=plan, diagnostics=diagnostics)

    reasons = {d['scene_index']: d['reason'] for d in diagnostics}
    
    # Scene 1 is valid, kept
    assert choices[1].scene_type == 'explainer_card'
    # Scene 2 demoted: empty title
    assert choices[2].scene_type == 'talking_head'
    assert 'Thiếu tiêu đề đồ họa' in reasons[2]
    # Scene 3 demoted: < 2 items
    assert choices[3].scene_type == 'talking_head'
    assert 'Thiếu danh sách mục minh họa' in reasons[3]
    # Scene 4 demoted: unsupported words
    assert choices[4].scene_type == 'talking_head'
    assert 'Nội dung minh họa không có căn cứ' in reasons[4]
    # Scene 5 demoted: insufficient duration
    assert choices[5].scene_type == 'talking_head'
    assert 'insufficient_duration' in reasons[5]
    # Scene 6 is valid, kept
    assert choices[6].scene_type == 'explainer_card'
    # Scene 7 demoted: duplicate of scene 6
    assert choices[7].scene_type == 'talking_head'
    assert 'Trùng lặp nội dung minh họa' in reasons[7]


def test_real_estate_preset_rejects_generic_graphics_without_property_photos():
    """Verify real_estate preset never fabricates property photos with generic graphics."""
    texts = ['Mở đầu', 'Khu biệt thự ven hồ', 'Kiến trúc hiện đại phong cách Âu', 'Kết thúc']
    units = [{'scene_index': i, 'start': i * 4.0, 'end': (i + 1) * 4.0, 'text': text} for i, text in enumerate(texts)]
    
    choices = {
        0: SceneChoice(scene_index=0, scene_type='talking_head', headline='Mở đầu', badge_text='', graphic_kind='chat', graphic_title='', graphic_items=[], sound_effect='none'),
        1: SceneChoice(scene_index=1, scene_type='explainer_card', headline='Biệt thự ven hồ', badge_text='', graphic_kind='process', graphic_title='Biệt thự ven hồ', graphic_items=['Biệt thự', 'Ven hồ'], sound_effect='whoosh'),
        2: SceneChoice(scene_index=2, scene_type='explainer_card', headline='Kiến trúc phong cách Âu', badge_text='', graphic_kind='network', graphic_title='Kiến trúc', graphic_items=['Kiến trúc', 'Phong cách'], sound_effect='whoosh'),
        3: SceneChoice(scene_index=3, scene_type='talking_head', headline='Kết thúc', badge_text='', graphic_kind='chat', graphic_title='', graphic_items=[], sound_effect='none'),
    }
    
    # Case A: No property image asset -> reject generic diagrams
    plan_without_photo = {'style_preset': {'id': 'real_estate'}, 'output_settings': {'fps': 30}, 'assets': []}
    diag = []
    balance_graphics(choices, units, 'Dựng bất động sản sang trọng', 16.0, style_preset='real_estate', plan=plan_without_photo, diagnostics=diag)
    
    assert choices[1].scene_type == 'talking_head'
    assert choices[2].scene_type == 'talking_head'
    assert any('Thiếu ảnh bất động sản thực tế' in d['reason'] for d in diag)

    # Case B: With authentic property image asset in assets
    choices_b = {
        0: SceneChoice(scene_index=0, scene_type='talking_head', headline='Mở đầu', badge_text='', graphic_kind='chat', graphic_title='', graphic_items=[], sound_effect='none'),
        1: SceneChoice(scene_index=1, scene_type='explainer_card', headline='Biệt thự ven hồ', badge_text='', graphic_kind='process', graphic_title='Biệt thự ven hồ', graphic_items=['Biệt thự', 'Ven hồ'], sound_effect='whoosh'),
        2: SceneChoice(scene_index=2, scene_type='talking_head', headline='Kết thúc', badge_text='', graphic_kind='chat', graphic_title='', graphic_items=[], sound_effect='none'),
    }
    plan_with_photo = {
        'style_preset': {'id': 'real_estate'},
        'output_settings': {'fps': 30},
        'assets': [{'id': 'prop_img', 'type': 'image', 'filename': 'villa.jpg'}]
    }
    diag_b = []
    balance_graphics(choices_b, units[:3], 'Dựng bất động sản sang trọng', 12.0, style_preset='real_estate', plan=plan_with_photo, diagnostics=diag_b)
    # When authentic property photo exists, valid visual is retained
    assert choices_b[1].scene_type == 'explainer_card'


def test_inspirational_preset_prioritizes_speaker():
    """Verify inspirational preset prioritizes speaker over dry abstract process diagrams."""
    texts = ['Mở đầu', 'Cảm xúc một', 'Quy trình kỹ thuật hai', 'Quy trình kỹ thuật ba', 'Kết thúc']
    units = [{'scene_index': i, 'start': i * 4.0, 'end': (i + 1) * 4.0, 'text': text} for i, text in enumerate(texts)]
    
    choices = {
        0: SceneChoice(scene_index=0, scene_type='talking_head', headline='Mở đầu', badge_text='', graphic_kind='chat', graphic_title='', graphic_items=[], sound_effect='none'),
        1: SceneChoice(scene_index=1, scene_type='talking_head_pip', headline='Cảm xúc một', badge_text='', graphic_kind='chat', graphic_title='Cảm xúc', graphic_items=['Cảm xúc', 'Một'], sound_effect='pop'),
        2: SceneChoice(scene_index=2, scene_type='explainer_card', headline='Quy trình kỹ thuật hai', badge_text='', graphic_kind='process', graphic_title='Quy trình', graphic_items=['Kỹ thuật', 'Hai'], sound_effect='whoosh'),
        3: SceneChoice(scene_index=3, scene_type='explainer_card', headline='Quy trình kỹ thuật ba', badge_text='', graphic_kind='process', graphic_title='Quy trình', graphic_items=['Kỹ thuật', 'Ba'], sound_effect='whoosh'),
        4: SceneChoice(scene_index=4, scene_type='talking_head', headline='Kết thúc', badge_text='', graphic_kind='chat', graphic_title='', graphic_items=[], sound_effect='none'),
    }
    plan = {'style_preset': {'id': 'inspirational'}, 'output_settings': {'fps': 30}, 'has_speaker': True, 'assets': []}
    diag = []
    balance_graphics(choices, units, 'Truyền cảm hứng', 20.0, style_preset='inspirational', plan=plan, diagnostics=diag)
    
    # 1 chat and at most 1 diagram kept; additional abstract diagrams demoted to favor speaker
    assert choices[1].scene_type == 'talking_head_pip'
    assert choices[2].scene_type == 'explainer_card'
    assert choices[3].scene_type == 'talking_head'
    assert any('style_preset_speaker_priority' in d['reason'] for d in diag)


def test_short_video_not_overcrowded_with_graphics():
    """Verify short video (<= 8s) keeps at most one focused illustration."""
    texts = ['Khái niệm A', 'Khái niệm B']
    units = [{'scene_index': 0, 'start': 0.0, 'end': 3.5, 'text': 'Khái niệm A'},
             {'scene_index': 1, 'start': 3.5, 'end': 7.0, 'text': 'Khái niệm B'}]
    choices = {
        0: SceneChoice(scene_index=0, scene_type='explainer_card', headline='Khái niệm A', badge_text='', graphic_kind='process', graphic_title='Khái niệm A', graphic_items=['Khái niệm', 'A'], sound_effect='whoosh'),
        1: SceneChoice(scene_index=1, scene_type='explainer_card', headline='Khái niệm B', badge_text='', graphic_kind='process', graphic_title='Khái niệm B', graphic_items=['Khái niệm', 'B'], sound_effect='whoosh'),
    }
    diag = []
    balance_graphics(choices, units, 'Minh họa sinh động', 7.0, diagnostics=diag)
    graphic_count = sum(1 for c in choices.values() if c.scene_type != 'talking_head')
    assert graphic_count == 1
    assert any('short_video_limit' in d['reason'] for d in diag)


def test_user_exclusion_request_demotes_all_graphics():
    """Verify prompt explicitly excluding illustrations demotes all graphic scenes with user_excluded reason."""
    texts = ['Mở đầu', 'Nội dung một', 'Nội dung hai', 'Kết thúc']
    units = [{'scene_index': i, 'start': i * 4.0, 'end': (i + 1) * 4.0, 'text': text} for i, text in enumerate(texts)]
    choices = {
        0: SceneChoice(scene_index=0, scene_type='talking_head', headline='Mở đầu', badge_text='', graphic_kind='chat', graphic_title='', graphic_items=[], sound_effect='none'),
        1: SceneChoice(scene_index=1, scene_type='explainer_card', headline='Nội dung một', badge_text='', graphic_kind='process', graphic_title='Nội dung', graphic_items=['Nội dung', 'Một'], sound_effect='whoosh'),
        2: SceneChoice(scene_index=2, scene_type='explainer_card', headline='Nội dung hai', badge_text='', graphic_kind='process', graphic_title='Nội dung', graphic_items=['Nội dung', 'Hai'], sound_effect='whoosh'),
        3: SceneChoice(scene_index=3, scene_type='talking_head', headline='Kết thúc', badge_text='', graphic_kind='chat', graphic_title='', graphic_items=[], sound_effect='none'),
    }
    diag = []
    balance_graphics(choices, units, 'không chèn minh họa hay đồ họa', 16.0, diagnostics=diag)
    assert all(c.scene_type == 'talking_head' for c in choices.values())
    assert all('user_excluded' in d['reason'] for d in diag)


def test_opening_ending_camera_policy():
    """Verify opening/ending can be graphics when non-speaker footage or user requested."""
    texts = ['Khái niệm mở đầu', 'Nội dung giữa', 'Lời kêu gọi hành động cuối']
    units = [{'scene_index': i, 'start': i * 4.0, 'end': (i + 1) * 4.0, 'text': text} for i, text in enumerate(texts)]
    
    # Case A: Non-speaker footage (slides/audio only)
    choices_a = {
        0: SceneChoice(scene_index=0, scene_type='explainer_card', headline='Khái niệm mở đầu', badge_text='', graphic_kind='process', graphic_title='Mở đầu', graphic_items=['Mở', 'đầu'], sound_effect='whoosh'),
        1: SceneChoice(scene_index=1, scene_type='explainer_card', headline='Nội dung giữa', badge_text='', graphic_kind='process', graphic_title='Giữa', graphic_items=['Nội', 'dung'], sound_effect='whoosh'),
        2: SceneChoice(scene_index=2, scene_type='explainer_card', headline='Kêu gọi cuối', badge_text='', graphic_kind='process', graphic_title='Cuối', graphic_items=['Kêu', 'gọi'], sound_effect='whoosh'),
    }
    plan_non_speaker = {'has_speaker': False, 'output_settings': {'fps': 30}, 'assets': []}
    balance_graphics(choices_a, units, 'Minh họa đầy đủ', 12.0, plan=plan_non_speaker)
    # Opening and ending can stay graphics because footage has no speaker
    assert choices_a[0].scene_type == 'explainer_card'
    assert choices_a[2].scene_type == 'explainer_card'

    # Case B: Speaker footage with explicit user prompt request for opening/ending graphics
    choices_b = {
        0: SceneChoice(scene_index=0, scene_type='explainer_card', headline='Khái niệm mở đầu', badge_text='', graphic_kind='process', graphic_title='Mở đầu', graphic_items=['Mở', 'đầu'], sound_effect='whoosh'),
        1: SceneChoice(scene_index=1, scene_type='explainer_card', headline='Nội dung giữa', badge_text='', graphic_kind='process', graphic_title='Giữa', graphic_items=['Nội', 'dung'], sound_effect='whoosh'),
        2: SceneChoice(scene_index=2, scene_type='explainer_card', headline='Kêu gọi cuối', badge_text='', graphic_kind='process', graphic_title='Cuối', graphic_items=['Kêu', 'gọi'], sound_effect='whoosh'),
    }
    plan_speaker = {'has_speaker': True, 'output_settings': {'fps': 30}, 'assets': []}
    balance_graphics(choices_b, units, 'mở đầu bằng đồ họa và kết thúc bằng đồ họa', 12.0, plan=plan_speaker)
    assert choices_b[0].scene_type == 'explainer_card'
    assert choices_b[2].scene_type == 'explainer_card'


def test_timing_and_speech_integrity():
    """Verify apply_choices and semantic_units preserve exact timestamps and speech tokens."""
    plan = {
        'assets': [],
        'video_clips': [{'asset_id': 'src', 'source_in': 0, 'duration': 12, 'timeline_start': 0}],
        'subtitles': [
            {'asset_id': 'src', 'start': 0, 'end': 6, 'text': 'Xin chào mừng các bạn đến dự án.',
             'words': [{'word': 'Xin', 'start': 0.1, 'end': 0.8}, {'word': 'chào', 'start': 0.8, 'end': 1.5},
                       {'word': 'mừng', 'start': 1.5, 'end': 2.2}, {'word': 'các', 'start': 2.2, 'end': 3.0},
                       {'word': 'bạn', 'start': 3.0, 'end': 3.8}, {'word': 'đến', 'start': 3.8, 'end': 4.5},
                       {'word': 'dự', 'start': 4.5, 'end': 5.2}, {'word': 'án.', 'start': 5.2, 'end': 6.0}]},
            {'asset_id': 'src', 'start': 6, 'end': 12, 'text': 'Chúng tôi cam kết chất lượng tuyệt đối.',
             'words': [{'word': 'Chúng', 'start': 6.2, 'end': 7.0}, {'word': 'tôi', 'start': 7.0, 'end': 8.0},
                       {'word': 'cam', 'start': 8.0, 'end': 9.0}, {'word': 'kết', 'start': 9.0, 'end': 10.0},
                       {'word': 'chất', 'start': 10.0, 'end': 11.0}, {'word': 'lượng.', 'start': 11.0, 'end': 12.0}]}
        ],
        'output_settings': {'fps': 30}
    }
    units = semantic_units(plan)
    assert units[0]['start'] == 0.0
    assert units[-1]['end'] == 12.0
    
    choices = {
        u['scene_index']: SceneChoice(
            scene_index=u['scene_index'],
            scene_type='talking_head',
            headline=u['text'][:20],
            badge_text='',
            graphic_kind='chat',
            graphic_title='',
            graphic_items=[],
            sound_effect='none',
            caption_text=u['text']
        )
        for u in units
    }
    applied = apply_choices(plan, 'Chỉnh sửa', units, choices, True)
    
    # Storyboard matches units timing exactly
    for u, sc in zip(units, applied['storyboard']):
        assert sc['timeline_start'] == u['start']
        assert sc['duration'] == u['end'] - u['start']
        assert sc['transcript_meaning'] == u['text']
    
    # Total duration unchanged
    assert applied['subtitles'][0]['start'] == 0.0
    assert applied['subtitles'][-1]['end'] == 12.0


def test_unrepairable_graphic_demotes_to_talking_head_without_schema_error(monkeypatch, tmp_path):
    """When AI fails to repair invalid graphic labels across all 3 attempts, demote scene to talking_head without crashing into SCHEMA_ERROR."""
    import json
    import automatic_director
    from automatic_director import automatic_direction
    import main

    plan = {
        'video_clips': [{'asset_id': 'vid_1', 'source_in': 0.0, 'duration': 12.0, 'timeline_start': 0.0}],
        'assets': [{'id': 'vid_1', 'type': 'video', 'filename': 'vid.mp4', 'metadata': {'duration': 12.0}}],
        'subtitles': [
            {'start': 0.0, 'end': 4.0, 'text': 'Giới thiệu công ty DANAVA.'},
            {'start': 4.0, 'end': 8.0, 'text': 'Giải pháp chăm sóc sức khỏe toàn diện.'},
            {'start': 8.0, 'end': 12.0, 'text': 'Kết nối mọi dịch vụ tiện ích.'}
        ],
        'output_settings': {'width': 720, 'height': 1280, 'fps': 30, 'fit': 'cover'}
    }

    calls = []
    def reply(messages, event, schema):
        calls.append(messages[-1]['content'])
        # AI returns an invalid graphic with unsupported words in all attempts
        return json.dumps({
            'summary': 'Kế hoạch AI',
            'scenes': [
                {'scene_index': 0, 'scene_type': 'talking_head', 'headline': 'GIỚI THIỆU', 'badge_text': '', 'graphic_kind': 'chat', 'graphic_title': '', 'graphic_items': [], 'sound_effect': 'none', 'caption_text': 'Giới thiệu công ty DANAVA.'},
                {'scene_index': 1, 'scene_type': 'explainer_card', 'headline': 'GIẢI PHÁP', 'badge_text': '', 'graphic_kind': 'process', 'graphic_title': 'Thuật toán siêu việt', 'graphic_items': ['Bịa đặt 1', 'Bịa đặt 2'], 'sound_effect': 'whoosh', 'caption_text': 'Giải pháp chăm sóc sức khỏe toàn diện.'},
                {'scene_index': 2, 'scene_type': 'talking_head', 'headline': 'KẾT NỐI', 'badge_text': '', 'graphic_kind': 'chat', 'graphic_title': '', 'graphic_items': [], 'sound_effect': 'none', 'caption_text': 'Kết nối mọi dịch vụ tiện ích.'}
            ]
        })

    monkeypatch.setattr(automatic_director, 'chat', reply)
    # Must NOT raise PlanningError with SCHEMA_ERROR; must demote scene 1 to talking_head gracefully
    result = automatic_direction(plan, 'Minh họa DANAVA', main.ASSETS_DIR, tmp_path, threading.Event())
    assert result['director']['engine'] == 'ollama'
    assert result['storyboard'][1]['scene_type'] == 'talking_head'

