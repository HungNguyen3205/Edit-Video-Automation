import pytest
from editing import validate
from test_pipeline import media, new_project


def test_short_storyboard_cannot_override_preserved_timeline(media):
    plan = new_project(media)['edit_plan']
    plan['storyboard'] = [{'scene_type': 'talking_head', 'timeline_start': 0, 'duration': 1}]
    with pytest.raises(ValueError, match='Storyboard dài'):
        validate(plan, plan['assets'])


def test_storyboard_maps_across_source_cut_boundaries(media):
    plan = new_project(media)['edit_plan']
    clip = plan['video_clips'][0]
    plan['video_clips'] = [{**clip, 'source_in': 0, 'duration': 1},
                           {**clip, 'source_in': 2, 'duration': 2}]
    plan['storyboard'] = [{'scene_type': 'talking_head', 'timeline_start': 0, 'duration': 3,
                           'source_in': 999}]
    out = validate(plan, plan['assets'])['storyboard']
    assert [(s['timeline_start'], s['source_in'], s['duration']) for s in out] == [(0, 0, 1), (1, 2, 2)]


def test_storyboard_rejects_overlap(media):
    plan = new_project(media)['edit_plan']
    plan['storyboard'] = [{'timeline_start': 0, 'duration': 2}, {'timeline_start': 1, 'duration': 2}]
    with pytest.raises(ValueError, match='chồng nhau'):
        validate(plan, plan['assets'])


def test_explainer_ai_repairs_missing_storyboard_instead_of_fixed_fallback(media, tmp_path, monkeypatch):
    import threading
    import main
    import ai_director
    from test_ai_director import decision
    messages = []
    responses = [decision(cuts=[{'start': 0, 'end': 4}]).model_dump_json(),
                 decision(cuts=[{'start': 0, 'end': 4}], storyboard=[
                     {'scene_type': 'talking_head', 'timeline_start': 0, 'duration': 4}]).model_dump_json()]
    def chat(seen, event):
        messages.append(str(seen))
        return responses.pop(0)
    monkeypatch.setattr(ai_director, 'chat', chat)
    result = ai_director.direct(new_project(media)['edit_plan'], 'Dựng theo ý nghĩa', main.ASSETS_DIR,
                               tmp_path, threading.Event(), visual_style='explainer_ref')
    assert len(messages) == 2
    assert 'requires a complete semantic storyboard' in messages[-1]
    assert sum(s['duration'] for s in result['storyboard']) == 4
