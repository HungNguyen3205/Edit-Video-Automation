import json,os,shutil,subprocess,sys
from pathlib import Path
import main


def test_main_entry_resources_work_outside_repository(tmp_path):
    root=Path(main.BASE_DIR)
    env={**os.environ,'PYTHONPATH':str(root),'VIDEO_DATA_DIR':str(tmp_path/'runtime')}
    code='''import json,main
from fastapi.testclient import TestClient
from learning_store import editor_skills,LearningStore
from project_paths import PROJECT_ROOT,SKILLS_DIR
from storyboard_compiler import MOTION_DIR
assert PROJECT_ROOT==main.BASE_DIR
assert SKILLS_DIR.is_dir() and (MOTION_DIR/'fonts/Inter-Variable.ttf').is_file()
r=TestClient(main.app).get('/frontend/index.html')
assert r.status_code==200 and '/docs/APPROVED_STYLE.md' in r.text
assert {s['id'] for s in editor_skills()} >= {'faithful_captions','speech_cleanup'}
assert LearningStore(main.DATA_DIR).context()['initial_visual_reference']
print('ENTRY_OK')'''
    result=subprocess.run([sys.executable,'-c',code],cwd=tmp_path,env=env,capture_output=True,text=True)
    assert result.returncode==0,result.stderr
    assert 'ENTRY_OK' in result.stdout


def test_sfx_script_preserves_project_relative_output(tmp_path):
    clone=tmp_path/'copy';(clone/'scripts').mkdir(parents=True)
    shutil.copy2(Path(main.BASE_DIR)/'scripts/generate_sfx.py',clone/'scripts/generate_sfx.py')
    run=subprocess.run([sys.executable,str(clone/'scripts/generate_sfx.py')],cwd=tmp_path,capture_output=True,text=True)
    assert run.returncode==0,run.stderr
    metadata=json.loads((clone/'data/sfx/metadata.json').read_text(encoding='utf-8'))
    assert set(metadata)=={'pop','click','whoosh','impact','chime'}
    assert all((clone/'data/sfx'/record['file']).is_file() for record in metadata.values())
