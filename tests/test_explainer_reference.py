import json
import pytest
from pathlib import Path
from test_pipeline import client, media, new_project, probe, save, get_result
import main

def test_explainer_storyboard_e2e_render(media):
    p = new_project(media)
    plan = p['edit_plan']
    # Add subtitles so storyboard can analyze semantic meaning
    vid_asset = p['video']['asset_id']
    plan['subtitles'] = [
        {'id': 's1', 'asset_id': vid_asset, 'start': 0.0, 'end': 1.5, 'text': 'Ưu điểm nội sàn là khách rất gần hành vi mua'},
        {'id': 's2', 'asset_id': vid_asset, 'start': 1.5, 'end': 2.8, 'text': 'Doanh số 85% đến từ video và livestream'},
        {'id': 's3', 'asset_id': vid_asset, 'start': 2.8, 'end': 4.0, 'text': 'Lưu video này lại để áp dụng cho shop'}
    ]
    p = save(p, plan)

    # Run auto-edit with visual_style = explainer_ref
    result, output_file = get_result(p, 'auto-edit', planner='rules', visual_style='explainer_ref', headline='BÍ QUYẾT BÁN HÀNG')
    
    assert output_file.exists()
    meta = probe(output_file)
    assert meta['has_audio']
    assert meta['duration'] >= 3.8
    assert meta['width'] > 0 and meta['height'] > 0
    
    # Check storyboard presence
    assert 'storyboard' in result['edit_plan']
    assert len(result['edit_plan']['storyboard']) >= 1

    # Check duration audit log
    assert 'duration_audit' in result
    audit = result['duration_audit']
    assert audit['source_duration'] == 4.0
    assert audit['ffprobe_duration'] >= 3.8

    # Test rollback endpoint
    rev_before = result['revision']
    rb_res = client.post(f"/api/projects/{p['id']}/rollback", json={'revision': 1})
    assert rb_res.status_code == 200
    p_rb = rb_res.json()
    assert p_rb['revision'] > rev_before
