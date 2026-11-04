"""Repository paths for the Python tests (run: python3 -m unittest discover -s tests)."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
def setup_imports():
    for folder in ('tools', 'scripts', 'launcher'):
        path = str(ROOT / folder)
        if path not in sys.path:
            sys.path.insert(0, path)


setup_imports()
