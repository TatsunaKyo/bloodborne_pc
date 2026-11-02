# SPDX-License-Identifier: GPL-2.0-or-later
"""Freeze the current launcher with the same assets/imports in CI and packaging."""
import argparse
import os
from pathlib import Path
import subprocess
import sys
from prepare_launcher_assets import prepare as prepare_assets
from prepare_tk_runtime import prepare as prepare_tk
ROOT=Path(__file__).resolve().parents[1]

def freeze():
    assets=prepare_assets()
    prepare_tk(ROOT/'out/tk-runtime')
    command=[sys.executable,'-m','PyInstaller','--noconfirm','--clean','--log-level','WARN',
             '--windowed','--name','Bloodborne','--icon',str(ROOT/'launcher/bloodborne.ico'),
             '--distpath',str(ROOT/'out/pyi-dist'),'--workpath',str(ROOT/'out/pyi-work'),
             '--specpath',str(ROOT/'out/pyi-work')]
    for name in ('scripts','tools'):
        command+=['--paths',str(ROOT/name)]
    for name in ('argparse','base64','collections','hashlib','json','re','shutil','struct','tempfile',
                 'xml.etree.ElementTree','urllib.request','ctypes.wintypes','dataclasses','datetime',
                 'ipaddress','contextlib','support_report','support_report_ui','save_access',
                 'save_manager','save_manager_ui'):
        command+=['--hidden-import',name]
    for source,target in ((assets,'assets'),(ROOT/'out/tk-runtime/_tcl_data','_tcl_data'),
                          (ROOT/'out/tk-runtime/_tk_data','_tk_data')):
        command+=['--add-data',str(source)+os.pathsep+target]
    command.append(str(ROOT/'launcher/bbport_launcher_win.py'))
    subprocess.run(command,cwd=ROOT,check=True)

if __name__=='__main__':
    argparse.ArgumentParser(description=__doc__).parse_args()
    freeze()
