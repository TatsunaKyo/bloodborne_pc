# SPDX-License-Identifier: GPL-2.0-or-later
"""Copy required launcher artwork/fonts without the upstream visual-test fixtures."""
from pathlib import Path
import shutil
ROOT = Path(__file__).resolve().parents[1]

def prepare():
    target=ROOT/'out/launcher-assets'
    shutil.rmtree(target,ignore_errors=True)
    shutil.copytree(ROOT/'launcher/assets',target,
                    ignore=shutil.ignore_patterns('tests','__pycache__','*.pyc'))
    return target

if __name__=='__main__':
    print(prepare())
