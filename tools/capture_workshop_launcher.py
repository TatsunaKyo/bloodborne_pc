# SPDX-FileCopyrightText: Copyright 2026 TatsunaKyo
# SPDX-License-Identifier: GPL-2.0-or-later
from pathlib import Path
import os,tempfile,types,marshal,time
import tkinter as tk
from tkinter import ttk,filedialog,messagebox
from PIL import ImageGrab
from PyInstaller.archive.readers import CArchiveReader
repo=Path(__file__).resolve().parents[1]
import argparse,importlib.util
parser=argparse.ArgumentParser(description='Capture actual launcher controls with isolated preview settings; never launches the game.')
parser.add_argument('--launcher',type=Path,help='Matching CPython 3.14 frozen Windows launcher; omit to capture current source.')
args=parser.parse_args()
module=types.ModuleType('workshop_capture');module.__file__=str(repo/'launcher/bbport_launcher_win.py')
if args.launcher:
 exec(marshal.loads(CArchiveReader(str(args.launcher)).extract('bbport_launcher_win')),module.__dict__)
else:
 exec(compile(Path(module.__file__).read_text(),module.__file__,'exec'),module.__dict__)
module.Launcher.detect_gpu=lambda self:None;module.Launcher.check_update=lambda self:None
out=repo/'out/verification/visual24';out.mkdir(parents=True,exist_ok=True)
with tempfile.TemporaryDirectory(prefix='workshop-ui-preview-') as temp:
 module.DATA_DIR=Path(temp);module.CONFIG_DIR=Path(temp)/'config';module.CONFIG_FILE=module.CONFIG_DIR/'settings.json';module.LANG='en'
 os.environ['BB_CONFIG']=str(Path(temp)/'bbport.ini')
 root=tk.Tk();root.tk.call('tk','scaling',96/72)
 app=module.Launcher(root,tk,ttk,filedialog,messagebox);root.geometry('1280x850+0+0')
 def grab(name):
  root.update();time.sleep(.04);root.update()
  for key,label in [('game','Preview: choose game files in Game & files'),('saves','Choose your existing saves location'),('gpu','GPU-specific options depend on your hardware'),('fsr4','Download optional FSR 4 assets in Image')]:
   if key in app.checks:app.checks[key].configure(text=label)
  root.update()
  ImageGrab.grab(bbox=(root.winfo_rootx(),root.winfo_rooty(),root.winfo_rootx()+root.winfo_width(),root.winfo_rooty()+root.winfo_height()),xdisplay=os.environ.get('DISPLAY')).save(out/(name+'.png'))
 app.vars['upscaler'].set('dlss');app.vars['frame_generation'].set('off');app.show('play');grab('play-dlss')
 app.vars['upscaler'].set('xess');root.update();grab('play-xess')
 box=app.quick_xess_row
 box.event_generate('<ButtonPress-1>',x=box.winfo_width()-8,y=box.winfo_height()//2);box.event_generate('<ButtonRelease-1>',x=box.winfo_width()-8,y=box.winfo_height()//2);root.update();grab('play-xess-popup')
 box.event_generate('<Escape>');root.tk.call('ttk::combobox::Unpost',str(box));root.update()
 for page in ('image','frames','window','overlay'):
  app.show(page);app.pages[page].scroll_to_top();grab('launcher-'+page)
 app.vars['upscaler'].set('dlss');app.show('play');grab('play-return-dlss')
 root.destroy()
print('PASS: actual compiled Tk controls captured; isolated sample settings, no game or hardware claims.')
