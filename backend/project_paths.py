import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SKILLS_DIR = PROJECT_ROOT / 'skills'
DATA_DIR = Path(os.getenv('VIDEO_DATA_DIR', PROJECT_ROOT / 'data')).resolve()
