import copy
from PIL import ImageFont
from pathlib import Path
from text_review import normalize_names,prepare_source,headline_layout,review_issues
from test_pipeline import media,new_project,client
import main


def test_names_are_project_scoped_and_explicit_aliases_only():
    text='Dannava Solution giới thiệu Anna.'
    assert normalize_names(text)==text
    assert normalize_names(text,'DANAVA Solutions','AN NA | Anna')=='DANAVA Solutions giới thiệu AN NA.'
    assert normalize_names('A solution is useful.','DANAVA Solutions')=='A solution is useful.'
    assert normalize_names('Anh An đang nói.','','AN NA | Anna')=='Anh An đang nói.'
    assert normalize_names('Mộc Spa và Nguyễn Thị Hoa.','','MỘC SPA | Mộc Spa')=='MỘC SPA và Nguyễn Thị Hoa.'


def test_corrected_source_retains_raw_cache_and_word_span():
    p={'subtitles':[{'text':'Anna nói.','start':2,'end':4,'words':[{'word':'Anna','start':2,'end':3},{'word':'nói.','start':3,'end':4}]}]}
    result=prepare_source(p,'','AN NA | Anna')
    assert result['subtitles'][0]['text']=='AN NA nói.'
    assert result['recognition_subtitles']==p['subtitles']
    assert result['subtitles'][0]['words'][0]['start']==2
    assert result['subtitles'][0]['words'][-1]['end']==4
    assert p['subtitles'][0]['text']=='Anna nói.'
    p['user_subtitles']=copy.deepcopy(p['subtitles'])
    assert prepare_source(p,'','AN NA | Anna')['subtitles']==p['subtitles']


def test_headline_is_measured_and_has_no_orphan_ai():
    source='DANAVA SOLUTION GIỚI THIỆU AI'
    text,size=headline_layout(source)
    assert ' '.join(text.split())==source
    assert '\nAI' not in text
    font=ImageFont.truetype(str(Path(main.BASE_DIR)/'motion_engine/fonts/BarlowCondensed-Bold.ttf'),size)
    assert all(font.getlength(line)<=640 for line in text.splitlines())
    assert len(text.splitlines())<=2


def test_review_does_not_guess_ambiguous_speech():
    subs=[{'start':1,'end':2,'text':'Mọi người có thể chết cái này.'},
          {'start':2,'end':3,'text':'Một câu khác.','words':[{'word':'khác','probability':.2}]}]
    original=copy.deepcopy(subs)
    issues=review_issues(subs)
    assert len(issues)==2
    assert subs==original
    assert review_issues([{'start':0,'end':1,'text':'Trợ lý AI.'}])==[]


def test_real_retry_uses_new_name_config_not_old_plan(media,monkeypatch):
    p=new_project(media);aid=p['video']['asset_id']
    p['edit_plan']['subtitles']=[{'id':'s','asset_id':aid,'start':0,'end':4,'text':'Anna nói về Dannava.'}]
    main.save_project(p['id'],p)
    monkeypatch.setenv('OLLAMA_URL','http://127.0.0.1:9')
    for name in ('AN NA','AN AN'):
        r=client.post(f'/api/projects/{p["id"]}/make-video',json={'brand_name':'DANAVA','proper_names':name+' | Anna','illustrations':False})
        assert r.status_code==200,r.text
        result=client.get(f'/api/projects/{p["id"]}').json()
        assert result['job']['status']=='succeeded',result['job']
        assert result['edit_plan']['subtitles'][0]['text']==name+' nói về DANAVA.'
        assert result['edit_plan']['recognition_subtitles'][0]['text']=='Anna nói về Dannava.'
        assert result['job']['branding']['proper_names']==name+' | Anna'


def test_caption_pages_keep_explicit_multiword_name_together():
    from storyboard_style import caption_chunks
    words='Mọi người có thể thử trợ lý AN NA hôm nay'.split()
    sub={'start':0,'end':10,'text':' '.join(words),'words':[{'word':w,'start':i,'end':i+1} for i,w in enumerate(words)]}
    # Boundary at AN would split the name without protection.
    for timed in (True,False):
        if not timed:sub.pop('words')
        chunks=caption_chunks([sub],max_words=8,proper_names='AN NA | Anna')
        assert any('AN NA' in c['text'] for c in chunks)
        assert ' '.join(c['text'] for c in chunks)==sub['text']
