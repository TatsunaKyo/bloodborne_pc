# SPDX-FileCopyrightText: Copyright 2026 TatsunaKyo
# SPDX-License-Identifier: GPL-2.0-or-later
"""Export selective Workshop diagrams and actual UI previews without replacing approved art.

Run launcher/widget captures and tests/test_overlay_controls.py --capture-dir first.
Exact labels/ratios are diagrams, not gameplay comparisons. Embedded UI readouts use fixture data.
"""
from pathlib import Path
from html import escape
import base64, io, json
import xml.etree.ElementTree as ET
import cairosvg
import numpy as np
from PIL import Image,ImageFont,ImageDraw
ROOT=Path(__file__).resolve().parents[1]
DEST=ROOT/'docs/assets/proposals/revision24'
CAPTURE=ROOT/'out/verification/visual24'
MENU=ROOT/'out/verification/menu24'
BG,PANEL,LINE,GOLD,INK,MUTED='#0c0f12','#171c21','#49453d','#d6c1a1','#efe6d8','#b9b0a2'
REAL,GENERATED='#d6c1a1','#9cb8bd'
FONT='/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
SERIF='/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf'
LABELS=[]

def text(x,y,value,size=28,color=INK,anchor='start',serif=False,limit=None):
    width=ImageFont.truetype(SERIF if serif else FONT,size).getlength(value)
    if limit is not None:assert width<=limit,(value,width,limit)
    LABELS.append({'text':value,'font_px':size,'width':round(width,2),'limit':limit})
    return f'<text x="{x}" y="{y}" font-family="DejaVu {"Serif" if serif else "Sans"}" font-size="{size}" text-anchor="{anchor}" fill="{color}">{escape(value)}</text>'
def rect(x,y,w,h,fill=PANEL,stroke=LINE,rx=4):return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" fill="{fill}" stroke="{stroke}"/>'
def path(d,color=GOLD,width=3,fill='none',opacity=1):return f'<path d="{d}" stroke="{color}" stroke-width="{width}" fill="{fill}" opacity="{opacity}"/>'
def arrow(x,y,end,color=GOLD):return path(f'M{x} {y}H{end}m-10-8 10 8-10 8',color)
def emblem():
    group=next(c for c in ET.parse(ROOT/'docs/assets/crowned-workshop-emblem.svg').getroot() if c.tag.endswith('g'))
    return '<g transform="translate(928 18) scale(.18)" color="'+GOLD+'">'+ET.tostring(group,encoding='unicode')+'</g>'
def image_element(image,x,y,w,h):
    data=io.BytesIO();image.convert('RGB').save(data,format='PNG')
    return f'<image x="{x}" y="{y}" width="{w}" height="{h}" href="data:image/png;base64,{base64.b64encode(data.getvalue()).decode()}"/>'
def document(title,desc,content,height=560):
    return f'<svg xmlns="http://www.w3.org/2000/svg" width="1000" height="{height}" viewBox="0 0 1000 {height}" role="img" aria-labelledby="title desc"><title id="title">{escape(title)}</title><desc id="desc">{escape(desc)}</desc>'+rect(0,0,1000,height,BG,BG,0)+emblem()+text(32,56,title,32,GOLD,serif=True,limit=875)+path('M32 82H968',LINE,1)+content+'</svg>\n'
def save(name,title,desc,content,height=560):
    svg=document(title,desc,content,height);(DEST/(name+'.svg')).write_text(svg)
    cairosvg.svg2png(bytestring=svg.encode(),write_to=str(DEST/(name+'.png')))
    return Image.open(DEST/(name+'.png')).convert('RGB')
def arch(x,y,w,h,color=GOLD):
    return path(f'M{x} {y+h}V{y+h*.40}Q{x} {y+h*.1} {x+w/2} {y}Q{x+w} {y+h*.1} {x+w} {y+h*.4}V{y+h}Z',color,2)

def upscaling():
    c=text(32,123,'Render the scene smaller. Reconstruct your display resolution.',27,limit=932)
    # Nested rectangles use real dimension ratios; the scenery is schematic.
    c+=rect(32,151,586,330,'#11171c',GOLD)
    c+=arch(255,205,144,240,'#596369')+path('M49 453H601M57 481H593','#596369',2)
    c+=rect(32,151,293,165,'#29343a',REAL,0)+arch(143,214,73,79)+path('M42 297H315',GOLD,2)
    c+=text(48,182,'1920 × 1080 input',24,limit=277)
    c+=rect(44,421,355,52,'#11171c','#11171c',0)+text(52,459,'3840 × 2160 output',28,GOLD,limit=546)
    c+=text(653,184,'DLSS / FSR',27,GOLD,limit=315)
    c+=text(653,222,'Performance · ×2.0',25,limit=315)
    c+=text(653,259,'1920 × 1080',28,limit=315)
    c+=text(653,323,'XeSS',27,GOLD,limit=315)
    c+=text(653,361,'Performance · ×2.3',25,limit=315)
    c+=text(653,398,'1670 × 940',28,limit=315)
    c+=text(653,446,'7 dedicated quality modes',23,MUTED,limit=315)
    c+=text(32,529,'Resolution diagram · 4K example · DLSS model presets remain separate',23,MUTED,limit=936)
    return save('upscaling','Upscaling: one output, different input ratios','Schematic resolution diagram. DLSS/FSR Performance at 4K renders 1920x1080; XeSS Performance uses 1670x940. This is not a visual-quality comparison.',c)

def window():
    c=text(32,125,'Your desktop mode, with a policy for when the game loses focus.',26,limit=932)
    for x,title,focused in [(32,'Foreground',True),(583,'Background',False)]:
        c+=rect(x,160,385,220,'#20272c',LINE,8)+rect(x+10,170,365,193,'#11181e','#11181e',2)
        c+=arch(x+128,190,120,144,'#8a8378')+path(f'M{x+46} 340H{x+336}',LINE,3)
        if not focused:
            c+=rect(x+67,205,240,112,'#343b41',GOLD,3)+rect(x+67,205,240,24,'#41464a',GOLD,2)
            c+=text(x+83,259,'Another window',22,limit=210)
        c+=rect(x+10,345,365,18,'#353a3d','#353a3d',0)
        c+=text(x+192,422,title,29,GOLD,'middle',limit=385)
    c+=rect(435,232,130,54)+text(500,267,'Alt + Tab',22,GOLD,'middle',limit=118)
    c+=arrow(420,219,578)
    for i,value in enumerate(('Keep running','Pause','30 FPS','60 FPS')):
        x=32+i*238;c+=rect(x,454,222,52)+text(x+111,488,value,25,INK,'middle',limit=204)
    c+=text(32,548,'Return to focus → restore your foreground settings',25,MUTED,limit=936)
    return save('window','Borderless, with a background policy','Conceptual desktop/window diagram: borderless uses desktop resolution; Alt-Tab activates an optional keep-running, pause, 30 or 60 FPS policy.',c,580)

def temporal():
    c=text(32,125,'Keep history during movement. Reset it when the scene changes.',26,limit=936)
    for i,title in enumerate(('Ordinary movement','Teleport / camera cut','Fresh scene history')):
        x=32+i*318;c+=rect(x,160,298,253,'#141a1f',LINE)
        c+=text(x+149,459,title,24,GOLD,'middle',limit=305)
        if i==0:
            c+=arch(x+85,193,100,177,'#6e716c')+arch(x+105,200,100,170)
            c+=arrow(x+89,388,x+208)
        elif i==1:
            c+=arch(x+35,215,75,151,'#696965')+arch(x+186,185,77,180)
            c+=path(f'M{x+127} 211L{x+166} 249M{x+166} 211L{x+127} 249','#ad8d86',3)
            c+=arrow(x+110,380,x+183)
        else:
            c+=arch(x+103,185,105,185)+path(f'M{x+232} 232l13 13 22-31',REAL,3)
    c+=text(32,508,'Shared reset: DLSS / FSR / XeSS / TAA / FG',27,limit=936)
    c+=text(32,552,'History reset diagram',23,MUTED,limit=936)
    return save('temporal','Temporal history that follows the scene','Conceptual diagram of retained history during movement, invalidation at a cut and fresh accumulation. It does not claim a measured image-quality difference.',c,580)

def render_imgui(name):
    data=json.loads((MENU/(name+'.json')).read_text());x,y,w,h=map(int,data['window']);atlas=np.asarray(Image.frombytes('RGBA',tuple(data['atlas']),(MENU/(name+'.atlas')).read_bytes()),dtype=np.float32)/255
    canvas=np.zeros((h,w,4),dtype=np.float32);canvas[:,:,:3]=np.array([12,15,18])/255;canvas[:,:,3]=1
    ah,aw=atlas.shape[:2]
    for dl in data['lists']:
        vertices=np.array(dl['vertices'],dtype=np.float64);indices=dl['indices']
        for command in dl['commands']:
            clip=command['clip'];start=command['offset'];end=start+command['count']
            for pos in range(start,end,3):
                tri=vertices[[indices[pos+j]+command['base'] for j in range(3)]]
                p=tri[:,:2]-[x,y];lo=np.maximum(np.floor(p.min(axis=0)),[max(0,clip[0]-x),max(0,clip[1]-y)]).astype(int);hi=np.minimum(np.ceil(p.max(axis=0)),[min(w,clip[2]-x),min(h,clip[3]-y)]).astype(int)
                if np.any(hi<=lo):continue
                xx,yy=np.meshgrid(np.arange(lo[0],hi[0])+.5,np.arange(lo[1],hi[1])+.5)
                denom=(p[1,1]-p[2,1])*(p[0,0]-p[2,0])+(p[2,0]-p[1,0])*(p[0,1]-p[2,1])
                if abs(denom)<1e-7:continue
                a=((p[1,1]-p[2,1])*(xx-p[2,0])+(p[2,0]-p[1,0])*(yy-p[2,1]))/denom
                b=((p[2,1]-p[0,1])*(xx-p[2,0])+(p[0,0]-p[2,0])*(yy-p[2,1]))/denom;weights=np.stack([a,b,1-a-b],axis=-1)
                mask=np.all(weights>=-1e-7,axis=-1)
                # A half-open edge avoids double blending adjacent triangles.
                for j in range(3):
                    e0=p[(j+1)%3];e1=p[(j+2)%3]
                    if denom<0:e0,e1=e1,e0
                    d=e1-e0;inclusive=d[1]<0 or (d[1]==0 and d[0]>0)
                    if not inclusive:mask &= weights[:,:,j]>1e-7
                if not mask.any():continue
                uv=weights@tri[:,2:4];tx=np.clip(uv[:,:,0]*aw-.5,0,aw-1);ty=np.clip(uv[:,:,1]*ah-.5,0,ah-1)
                ix,iy=np.floor(tx).astype(int),np.floor(ty).astype(int);fx,fy=tx-ix,ty-iy
                tex=(atlas[iy,ix]*(1-fx)[...,None]+atlas[iy,np.minimum(ix+1,aw-1)]*fx[...,None])*(1-fy)[...,None]+(atlas[np.minimum(iy+1,ah-1),ix]*(1-fx)[...,None]+atlas[np.minimum(iy+1,ah-1),np.minimum(ix+1,aw-1)]*fx[...,None])*fy[...,None]
                color=np.array([[(int(v[4])>>(8*k))&255 for k in range(4)] for v in tri])/255
                src=tex*(weights@color);alpha=src[:,:,3:4];target=canvas[lo[1]:hi[1],lo[0]:hi[0]]
                blended=src[:,:,:3]*alpha+target[:,:,:3]*(1-alpha);target[:,:,:3][mask]=blended[mask]
    result=Image.fromarray(np.clip(canvas[:,:,:3]*255+.5,0,255).astype('uint8'))
    result.save(CAPTURE/(name+'-imgui.png'));return result

def launcher():
    capture=Image.open(CAPTURE/'play-dlss.png')
    c=text(32,125,'Quick choices on Play. Full controls in matching settings pages.',26,limit=936)
    c+=image_element(capture,32,146,936,621.6)
    c+=text(32,804,'Launcher preview · example settings',24,MUTED,limit=936)
    return save('launcher','The Crowned Workshop launcher','Actual compiled launcher controls captured at 1280x850. Isolated example settings; no game or hardware result is claimed.',c,834)

def menu():
    capture=render_imgui('frames')
    c=text(32,125,'Insert / L3 + R3 → seven tabs → edit while playing',26,limit=936)
    c+=image_element(capture,116,146,768,597.4)
    c+=text(32,788,'Menu preview · example settings',23,MUTED,limit=936)
    return save('in-game-menu','Live settings, grouped into tabs','Actual production in-game menu controls rendered from Dear ImGui draw data. Fixture settings and status, without a gameplay backdrop.',c,818)

def overlay():
    capture=render_imgui('frametime-full-en')
    c=text(32,125,'Start with the basic readout. Add only what you want.',27,limit=936)
    c+=image_element(capture,48,165,904,capture.height*904/capture.width)
    y=165+capture.height*904/capture.width+48
    c+=text(32,y,'Output FPS / FG mode · preset letter · input → output · PC latency',24,limit=936)
    c+=text(32,y+42,'The optional graph shows raw real-frame intervals, including spikes.',24,limit=936)
    c+=text(32,y+99,'Example readout · synthetic frametime data',23,MUTED,limit=936)
    return save('overlay','A compact overlay, with the frametime graph','Actual FpsCounter output rendered from Dear ImGui buffers. Values and the 55ms hitch are synthetic fixture data, not a gameplay benchmark.',c,int(y+131))

def fg_content(progress=None):
    c=text(32,125,'The game renders real frames. FG inserts extra display frames.',27,limit=936)
    for row,multiple in enumerate((2,3,4)):
        y=181+row*111;c+=text(32,y+35,'×'+str(multiple),31,GOLD,limit=135)
        c+=path(f'M200 {y+33}H949',LINE,2)
        for step in range(2*multiple+1):
            x=200+step*370/multiple;real=step%multiple==0;color=REAL if real else GENERATED
            active=progress is None or step/(2*multiple)<=progress
            fill=color if active else PANEL;label='R'+str(step//multiple) if real else 'G'
            c+=rect(x-31,y,62,65,fill,color,3)+text(x,y+42,label,24,BG if active else color,'middle',limit=56)
    c+=rect(32,507,22,22,REAL,REAL,0)+text(65,528,'Real game frame',24,limit=310)
    c+=rect(379,507,22,22,GENERATED,GENERATED,0)+text(412,528,'Generated display frame',24,limit=520)
    c+=text(32,581,'Illustrated timeline · ×2 / ×3 / ×4 depend on provider and GPU support',23,MUTED,limit=936)
    return c

def animations():
    save('frame-generation','Frame Generation: between real frames','Illustrated x2/x3/x4 timeline. Generated display frames do not advance game logic. Modes depend on provider and hardware.',fg_content(),613)
    frames=[]
    for i in range(37):
        svg=document('Frame Generation: between real frames','Illustrated timeline, not captured gameplay.',fg_content(min(1,i/28)),613)
        frames.append(Image.open(io.BytesIO(cairosvg.svg2png(bytestring=svg.encode(),output_width=1000,output_height=613))).convert('RGB'))
    frames[0].save(DEST/'frame-generation.gif',save_all=True,append_images=frames[1:],duration=110,loop=0,optimize=True)
    names=['play-dlss','play-xess','play-xess-popup','play-xess','launcher-image','launcher-frames','launcher-window','launcher-overlay','play-return-dlss']
    sequence=[]
    for name in names:
        im=Image.open(CAPTURE/(name+'.png')).convert('RGB');im=im.resize((1000,664),Image.Resampling.LANCZOS)
        frame=Image.new('RGB',(1000,716),BG);frame.paste(im,(0,0))
        ImageDraw.Draw(frame).text((20,680),'Launcher preview · example settings',font=ImageFont.truetype(FONT,20),fill=MUTED)
        sequence.append(frame)
    sequence[0].save(DEST/'launcher.gif',save_all=True,append_images=sequence[1:],duration=[1300,900,1900,700,1300,1300,1300,1300,1300],loop=0,optimize=True)

def main():
    DEST.mkdir(parents=True,exist_ok=True);CAPTURE.mkdir(parents=True,exist_ok=True)
    figures=[upscaling(),window(),temporal(),launcher(),menu(),overlay()]
    animations()
    proof=Image.new('RGB',(720,3*360),BG)
    for i,im in enumerate(figures):
        im.thumbnail((360,330),Image.Resampling.LANCZOS);x=(i%2)*360;y=(i//2)*360;proof.paste(im,(x,y+26));ImageDraw.Draw(proof).text((x+9,y+5),['Upscaling','Window','History','Launcher','In-game menu','Overlay'][i],font=ImageFont.truetype(FONT,17),fill=GOLD)
    proof.save(DEST/'mobile-proofs.png')
    (ROOT/'out/verification/visual-proposals-revision24.json').write_text(json.dumps({'original_assets_replaced':False,'mobile_proof_width':360,'actual_ui_source':'compiled Tk launcher and production ImGui draw buffers','readouts':'isolated/synthetic fixture values','gameplay_comparison_claimed':False,'labels':LABELS},indent=2)+'\n')
    print('PASS: six selective proposals, editable SVG/PNG, two GIFs and mobile proofs; current README art untouched.')
if __name__=='__main__':main()
