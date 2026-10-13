"""Stable repository resources, independent of module location and cwd."""
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SKILLS_DIR = PROJECT_ROOT / 'skills'
