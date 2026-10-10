"""Director contract and end-to-end render tests, independent of model downloads."""
import copy
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
from editing import compile_render, mapped_subtitles, probe, validate
from ai_director import Direction, apply_direction, direct, chat
from test_pipeline import media, new_project, save, get_result, client


def decision(**changes):
    data = dict(summary='Giữ hai đoạn lời nói, nhấn ý bằng chữ và âm thanh.', cuts=[{'start': 0, 'end': 1}, {'start': 2, 'end': 4}],
                titles=[{'start': 1, 'duration': 1, 'text': 'Điểm quan trọng'}],
                zooms=[{'start': 1, 'duration': 1, 'scale': 1.12}],
                sounds=[{'start': 1, 'duration': .4, 'kind': 'whoosh', 'volume': .2}])
    data.update(changes)
    return Direction.model_validate(data)


def test_cuts_remap_captions_and_manual_edits(media):
    p = new_project(media)
    plan = p['edit_plan']
    plan['subtitles'] = [{'id': 's', 'asset_id': p['video']['asset_id'], 'start': 2.2, 'end': 3.2, 'text': 'Nội dung'}]
    plan['text_overlays'] = [{'id': 'manual', 'origin': 'manual', 'timeline_start': 2.3, 'duration': .5, 'text': 'Giữ chữ'}]
    plan = apply_direction(plan, decision())
    assert sum(c['duration'] for c in plan['video_clips']) == 3
    assert mapped_subtitles(plan)[0]['start'] == pytest.approx(1.2)
    assert plan['text_overlays'][0]['timeline_start'] == pytest.approx(1.3)
    assert plan['audio_tracks'][0]['timeline_start'] == 1
    p = save(p, plan)
    _, output = get_result(p)
    assert probe(output)['duration'] == pytest.approx(3, abs=.1)


def test_music_upload_loop_and_real_mixed_output(media, tmp_path):
    import subprocess
    p = new_project(media)
    music = tmp_path / 'music.wav'
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'lavfi', '-i', 'sine=frequency=900:duration=0.7', str(music)], check=True)
    with music.open('rb') as f:
        response = client.post(f'/api/projects/{p["id"]}/upload', files={'file': ('music.wav', f)}, data={'role': 'asset'})
    assert response.status_code == 200, response.text
    p = response.json()
    a = p['edit_plan']['assets'][-1]
    assert a['type'] == 'audio'
    base = apply_direction(p['edit_plan'], decision(titles=[], zooms=[], sounds=[], music_volume=0))
    p = save(p, base)
    _, dry = get_result(p)
    mixed = apply_direction(p['edit_plan'], decision(cuts=[{'start': 0, 'end': 3}], sounds=[
        {'start': 1, 'duration': .4, 'kind': kind, 'volume': .2} for kind in ('whoosh', 'impact', 'chime')]), a['id'])
    p = save(p, mixed)
    _, output = get_result(p)
    def audio_bytes(file):
        return subprocess.run(['ffmpeg', '-v', 'error', '-i', str(file), '-vn', '-f', 's16le', '-'], capture_output=True, check=True).stdout
    assert audio_bytes(dry) != audio_bytes(output)
    assert probe(output)['has_audio'] and probe(output)['duration'] == pytest.approx(3, abs=.1)


@pytest.mark.parametrize('changes', [
    {'cuts': [{'start': 0, 'end': 20}]},
    {'titles': [{'start': 2.8, 'duration': 1, 'text': 'Sai'}]},
    {'illustrations': [{'start': 0, 'duration': 1, 'asset_id': 'not-owned'}]},
    {'sounds': [{'start': 0, 'duration': 5, 'kind': 'whoosh'}]},
])
def test_invalid_model_decisions_cannot_render(media, changes):
    with pytest.raises(ValueError):
        apply_direction(new_project(media)['edit_plan'], decision(**changes))


def test_director_repairs_invalid_response_and_passes_prompt_context(media, tmp_path, monkeypatch):
    import ai_director
    p = new_project(media)
    responses = [decision(cuts=[{'start': 0, 'end': 40}]).model_dump_json(), decision().model_dump_json()]
    messages_seen = []
    def reply(messages, event):
        messages_seen.append(copy.deepcopy(messages))
        return responses.pop(0)
    monkeypatch.setattr(ai_director, 'chat', reply)
    result = direct(p['edit_plan'], 'Làm wow, nhấn ý chính', __import__('main').ASSETS_DIR, tmp_path, threading.Event())
    assert len(messages_seen) == 2
    assert 'Repair' in messages_seen[1][-1]['content']
    assert json.loads(messages_seen[0][1]['content'])['brief'] == 'Làm wow, nhấn ý chính'
    assert 'cues' in json.loads(messages_seen[0][1]['content'])
    assert result['director']['warnings']  # truthfully reports missing transcript/vision


def test_local_ollama_stream_contract_and_cancel(monkeypatch):
    requests = []
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass
        def do_POST(self):
            requests.append(json.loads(self.rfile.read(int(self.headers['Content-Length']))))
            self.send_response(200)
            self.end_headers()
            self.wfile.write((json.dumps({'message': {'content': decision().model_dump_json()}, 'done': True})+'\n').encode())
    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    monkeypatch.setenv('OLLAMA_URL', f'http://127.0.0.1:{server.server_port}')
    try:
        event = threading.Event()
        assert Direction.model_validate_json(chat([{'role': 'user', 'content': 'wow'}], event)).cuts
        assert requests[0]['format']['properties']['cuts'] and requests[0]['stream']
        event.set()
        with pytest.raises(InterruptedError):
            chat([], event)
    finally:
        server.shutdown()
        server.server_close()


def test_ai_endpoint_exports_director_decisions_and_no_silent_rule_fallback(media, monkeypatch):
    import main
    monkeypatch.setattr(main, 'ai_health', lambda: {'available': True, 'model': 'test'})
    monkeypatch.setattr(main, 'direct', lambda plan, *args: apply_direction(plan, decision()))
    p = new_project(media)
    p, output = get_result(p, 'auto-edit', planner='ai', prompt='wow', transcribe=False)
    assert p['edit_plan']['director']['engine'] == 'ollama'
    assert probe(output)['duration'] == pytest.approx(3, abs=.1)
    monkeypatch.setattr(main, 'ai_health', lambda: {'available': False, 'model': 'missing'})
    response = client.post(f'/api/projects/{p["id"]}/auto-edit', json={'planner': 'ai', 'prompt': 'wow', 'transcribe': False})
    assert response.status_code == 422 and 'Ollama' in response.json()['detail']
    assert client.post(f'/api/projects/{p["id"]}/auto-edit', json={'planner': 'ai', 'prompt': ''}).status_code == 422
