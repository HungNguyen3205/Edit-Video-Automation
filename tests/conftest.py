"""Resolve the same backend modules used by the unchanged main entry point."""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'backend'))
os.environ.setdefault('ALLOW_LOCAL_WEB_RESEARCH', '1')
