import json
import threading
import time
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
from test_pipeline import media,new_project,client
import ai_director
from ai_director import AIError,ai_session,chat


@contextmanager
def stream_server(monkeypatch, mode):
    stop=threading.Event(); requests=[]
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):pass
        def do_POST(self):
            requests.append(json.loads(self.rfile.read(int(self.headers['Content-Length']))))
            self.send_response(200);self.end_headers();self.wfile.flush()
            try:
                if mode=='active':
                    while not stop.wait(.02):
                        self.wfile.write(b'{"message":{"content":"x"},"done":false}\n');self.wfile.flush()
                elif mode=='stall' or (mode=='repair' and len(requests)>1):
                    stop.wait(2)
                else:
                    if mode=='repair':stop.wait(.12)
                    body={'message':{'content':'{}'},'done':mode!='incomplete','prompt_eval_count':10,'eval_count':2,
                          'load_duration':123,'done_reason':'length' if mode=='length' else 'stop'}
                    self.wfile.write((json.dumps(body)+'\n').encode());self.wfile.flush()
            except (BrokenPipeError,ConnectionResetError):pass
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
    server.daemon_threads=True
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    monkeypatch.setenv('OLLAMA_URL',f'http://127.0.0.1:{server.server_port}')
    try:yield requests
    finally:stop.set();server.shutdown();server.server_close();thread.join(timeout=2)


@pytest.mark.parametrize('mode',['stall','active'])
def test_deadline_interrupts_io_with_or_without_chunks(monkeypatch,mode):
    monkeypatch.setenv('VIDEO_AI_REQUEST_TIMEOUT','.25')
    event=threading.Event()
    with stream_server(monkeypatch,mode) as requests:
        started=time.monotonic()
        with pytest.raises(AIError) as exc:chat([{'role':'user','content':'test'}],event)
        assert exc.value.code=='AI_TIMEOUT'
        assert time.monotonic()-started<2
        assert len(requests)==1
        assert event.ai_diagnostics['requests'][0]['status']=='failed'
        # No returned partial content or retry request after the timeout.
        time.sleep(.05);assert len(requests)==1


def test_cancel_closes_waiting_request_before_worker_returns(monkeypatch):
    event=threading.Event();timer=threading.Timer(.2,event.set)
    with stream_server(monkeypatch,'stall') as requests:
        timer.start();started=time.monotonic()
        try:
            with pytest.raises(InterruptedError):chat([],event)
            assert time.monotonic()-started<2
            assert event.ai_diagnostics['requests'][0]['status']=='cancelled'
            assert len(requests)==1
        finally:timer.cancel()


def test_repairs_share_total_planning_deadline(monkeypatch):
    monkeypatch.setenv('VIDEO_AI_PLANNING_TIMEOUT','.35')
    monkeypatch.setenv('VIDEO_AI_REQUEST_TIMEOUT','5')
    event=threading.Event()
    with stream_server(monkeypatch,'repair') as requests:
        started=time.monotonic()
        with pytest.raises(AIError) as exc:
            with ai_session(event):
                assert chat([],event)=='{}'
                chat([],event)
        assert exc.value.code=='AI_TIMEOUT'
        assert time.monotonic()-started<2
        assert len(requests)==2
        assert [r['status'] for r in event.ai_diagnostics['requests']]==['succeeded','failed']


@pytest.mark.parametrize('mode,code',[('incomplete','AI_STREAM_INCOMPLETE'),('length','AI_OUTPUT_LIMIT')])
def test_incomplete_and_token_limited_responses_are_never_success(monkeypatch,mode,code):
    with stream_server(monkeypatch,mode):
        with pytest.raises(AIError) as exc:chat([],threading.Event())
        assert exc.value.code==code


def test_real_stream_metadata_and_bounded_generation_are_recorded(monkeypatch):
    event=threading.Event()
    with stream_server(monkeypatch,'done') as requests:
        assert chat([],event)=='{}'
        assert requests[0]['options']['num_predict']==8192
    record=event.ai_diagnostics['requests'][0]
    assert record['prompt_eval_count']==10 and record['eval_count']==2
    assert record['load_duration']==123 and record['status']=='succeeded'
    assert 'first_chunk_seconds' in record and 'elapsed_seconds' in record


def test_timeout_does_not_replace_old_output_or_start_render(media,monkeypatch):
    import main
    p=new_project(media);aid=p['video']['asset_id']
    p['edit_plan']['subtitles']=[{'id':'s','asset_id':aid,'start':0,'end':4,'text':'Giữ lời nói.'}]
    p['output_path']='/outputs/previous-valid.mp4';p['output_revision']=p['revision']
    previous=main.OUTPUTS_DIR/'previous-valid.mp4';previous.write_bytes(media[0].read_bytes())
    main.save_project(p['id'],p)
    monkeypatch.setattr(main,'ai_health',lambda:{'available':True,'model':'fixture'})
    calls=[]
    def timeout(*args):
        calls.append('ai');raise AIError('AI_TIMEOUT','AI mất quá nhiều thời gian để lập kế hoạch.')
    monkeypatch.setattr(main,'direct',timeout)
    monkeypatch.setattr(main,'compile_storyboard_scenes',lambda *args,**kwargs:pytest.fail('Must not render after AI timeout'))
    r=client.post(f'/api/projects/{p["id"]}/auto-edit',json={'prompt':'Dựng đẹp','planner':'ai','transcribe':False})
    assert r.status_code==200
    result=client.get(f'/api/projects/{p["id"]}').json()
    assert result['job']['status']=='failed' and result['job']['error_code']=='AI_TIMEOUT'
    assert result['output_path']==p['output_path'] and result['revision']==p['revision']
    assert previous.read_bytes()==media[0].read_bytes()
    assert calls==['ai'] and result['job']['id'] not in main.CANCEL


def test_read_timeout_is_distinct_from_total_deadline(monkeypatch):
    monkeypatch.setenv('VIDEO_AI_READ_TIMEOUT','.1')
    monkeypatch.setenv('VIDEO_AI_REQUEST_TIMEOUT','5')
    with stream_server(monkeypatch,'stall'):
        with pytest.raises(AIError) as exc:chat([],threading.Event())
        assert exc.value.code=='AI_IDLE_TIMEOUT'


def test_total_budget_includes_validation_after_request(monkeypatch):
    monkeypatch.setenv('VIDEO_AI_PLANNING_TIMEOUT','.03')
    event=threading.Event()
    with pytest.raises(AIError) as exc:
        with ai_session(event):time.sleep(.05)
    assert exc.value.code=='AI_TIMEOUT'
    assert event.ai_diagnostics['elapsed_seconds']>=.03
