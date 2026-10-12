# SPDX-FileCopyrightText: Copyright 2026 TatsunaKyo
# SPDX-License-Identifier: GPL-2.0-or-later
"""Run the portable regression suite; private game files and a GPU are unnecessary."""
import argparse
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]


def run(command):
    print('Running: '+' '.join(map(str,command)),flush=True)
    label=next(Path(arg).stem for arg in command if Path(arg).name.startswith('test_'))
    with (ROOT/'out/verification'/(label+'.log')).open('w') as log:
        with subprocess.Popen(command,cwd=ROOT,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True) as process:
            for line in process.stdout:
                log.write(line);log.flush();print(line,end='',flush=True)
            result=process.wait()
    if result:raise subprocess.CalledProcessError(result,command)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--gui',action='store_true',help='Requires a display or xvfb-run')
    args=parser.parse_args()
    (ROOT/'out/verification').mkdir(parents=True,exist_ok=True)
    for file in ('test_launcher_updates.py','test_release_integrity.py','test_published_release.py','test_launcher_window_settings.py','test_diagnostics.py','test_geometry_diagnostics.py'):
        run([sys.executable,'tests/'+file])
    for file in ('test_run_settings.py',):
        run([sys.executable,'-m','unittest','discover','-s','tests','-p',file])
    for file in ('test_const_ram_order.py','test_draw_copy_order.py','test_vertex_descriptor_order.py',
                 'test_dma_copy_order.py','test_fg_depth_snapshot.py','test_queue_lock_scope.py','test_geometry_capture.py'):
        command=[sys.executable,'tests/'+file]
        if file in ('test_draw_copy_order.py','test_vertex_descriptor_order.py','test_dma_copy_order.py'):
            command+=['--compiler','g++']
        run(command)
    import ast
    source=ast.parse((ROOT/'launcher/bbport_launcher_win.py').read_text())
    version=next(n.value.value for n in source.body if isinstance(n,ast.Assign)
                 and any(isinstance(t,ast.Name) and t.id=='VERSION' for t in n.targets))
    revision=version.rsplit('.',1)[1]
    run([sys.executable,'tests/test_overlay_controls.py','--compiler','g++',
         '--capture-dir',f'out/verification/menu{revision}'])
    if args.gui:
        for file in ('test_launcher_geometry.py','test_launcher_xess.py'):
            run([sys.executable,'tests/'+file])


if __name__=='__main__':main()
