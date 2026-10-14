# SPDX-FileCopyrightText: Copyright 2026 TatsunaKyo
# SPDX-License-Identifier: GPL-2.0-or-later
"""Operate the actual diagnostic buttons and check compact/high-DPI layout."""
import importlib.util
import os
from pathlib import Path
import sys
import tempfile
import tkinter as tk
from tkinter import ttk,filedialog,messagebox
ROOT=Path(__file__).resolve().parents[1]
source=ROOT/'launcher/bbport_launcher_win.py'
if len(sys.argv)>1:
 import marshal,types
 from PyInstaller.archive.readers import CArchiveReader
 launcher=types.ModuleType('fg_control_launcher');launcher.__file__=str(source)
 exec(marshal.loads(CArchiveReader(sys.argv[1]).extract('bbport_launcher_win')),launcher.__dict__)
else:
 spec=importlib.util.spec_from_file_location('fg_control_launcher',source)
 launcher=importlib.util.module_from_spec(spec);spec.loader.exec_module(launcher)
launcher.Launcher.detect_gpu=lambda self:None
launcher.Launcher.check_update=lambda self:None
cases=0
with tempfile.TemporaryDirectory(prefix='workshop-fg-ui-') as directory:
 launcher.DATA_DIR=Path(directory);launcher.CONFIG_DIR=Path(directory)/'launcher';launcher.CONFIG_FILE=launcher.CONFIG_DIR/'settings.json'
 os.environ['BB_CONFIG']=str(Path(directory)/'bbport.ini')
 for language in ('en','ru'):
  launcher.LANG=language
  for scale in (1.0,1.25,1.5,1.75,2.0):
   root=tk.Tk();root.tk.call('tk','scaling',scale*96/72)
   try:
    obj=launcher.Launcher(root,tk,ttk,filedialog,messagebox)
    selected=[];obj.play=lambda mode=None:selected.append(mode)
    for size in ((980,660),(1280,850)):
     root.geometry(f'{round(size[0]*scale)}x{round(size[1]*scale)}+0+0');obj.show('advanced');root.update()
     a,b=obj.nvidia_capture_button,obj.nvidia_compare_button
     parent=a.master
     page=obj.pages['advanced']
     assert parent.winfo_rootx()+parent.winfo_width()<=page.winfo_rootx()+page.winfo_width(),(language,scale,size,'diagnostics outside page')
     for button in (a,b):
      assert button.winfo_x()>=0 and button.winfo_x()+button.winfo_width()<=parent.winfo_width(),(language,scale,size,button.cget('text'))
      assert button.winfo_width()>=button.winfo_reqwidth(),(language,scale,size,'clipped button')
     assert a.winfo_x()+a.winfo_width()<=b.winfo_x()
     a.invoke();b.invoke();assert selected[-2:]==['inputs','generated-only']
     assert '_nvidia_diagnostic' not in obj.app
     cases+=1
   finally:
    for callback in root.tk.call('after','info'):root.after_cancel(callback)
    root.destroy()
print(f'PASS: {cases} actual diagnostic-button layouts in English/Russian at 100–200% scaling, with precise one-run actions and unchanged preferences.')
