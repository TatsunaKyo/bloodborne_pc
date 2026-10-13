# SPDX-FileCopyrightText: Copyright 2026 TatsunaKyo
# SPDX-License-Identifier: GPL-2.0-or-later
from pathlib import Path
import sys
from PIL import Image,ImageDraw,ImageFont
r=Path(__file__).resolve().parents[1];sys.path.insert(0,str(r/'tools'))
import workshop_visual_proposals as v
v.MENU=r/'out/verification/menu25';v.CAPTURE=r/'out/verification/visual25';v.CAPTURE.mkdir(exist_ok=True)
font='/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf';serif='/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf'
frames=[]
for enabled,menu in [(False,False),(False,True),(True,True),(True,False)]:
 name=('fg-demo-menu-' if menu else 'frametime-demo-')+('on' if enabled else 'off')
 ui=v.render_imgui(name);canvas=Image.new('RGB',(1000,850),v.BG);d=ImageDraw.Draw(canvas)
 d.text((32,25),'Frame Generation, changed while playing',font=ImageFont.truetype(serif,32),fill=v.GOLD)
 d.text((32,86),'FG ×2: 60 real frames → 120 display frames',font=ImageFont.truetype(font,27),fill=v.INK)
 if menu:
  ui.thumbnail((850,660),Image.Resampling.LANCZOS);canvas.paste(ui,((1000-ui.width)//2,135))
 else:
  ui=ui.resize((850,round(ui.height*850/ui.width)),Image.Resampling.LANCZOS);canvas.paste(ui,(75,190))
  d.text((75,430),'FG '+('ON · ×2' if enabled else 'OFF'),font=ImageFont.truetype(font,42),fill=v.GOLD)
  d.text((75,500),'120 display FPS' if enabled else '60 display FPS',font=ImageFont.truetype(font,38),fill=v.INK)
  d.text((75,577),'Real frames: 60 FPS · 16.7 ms',font=ImageFont.truetype(font,29),fill=v.MUTED)
  d.text((75,625),'FG adds display updates; the real-frame graph stays at 16.7 ms.',font=ImageFont.truetype(font,23),fill=v.MUTED)
 d.text((32,812),'Illustrative UI animation · example FPS and frametime values',font=ImageFont.truetype(font,23),fill=v.MUTED)
 frames.append(canvas)
out=r/'docs/assets/proposals/revision25';out.mkdir(parents=True,exist_ok=True)
frames[0].save(out/'frame-generation.png')
frames[0].save(out/'frame-generation.gif',save_all=True,append_images=frames[1:],duration=[1800,1600,1800,2200],loop=0,optimize=True)
print('Rendered illustrative actual-menu/OSD off/on animation:',(out/'frame-generation.gif').stat().st_size)
