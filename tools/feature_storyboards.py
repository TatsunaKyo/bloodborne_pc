# SPDX-FileCopyrightText: Copyright 2026 TatsunaKyo
# SPDX-License-Identifier: GPL-2.0-or-later
"""Export explanatory, editable README figures. Values are setup examples."""
from html import escape
from pathlib import Path
import json
import xml.etree.ElementTree as ET
import cairosvg
from PIL import Image, ImageFont

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / 'docs/assets'
DEST = ASSETS / 'features'
W, H = 1000, 500
BG, PANEL, LINE, GOLD, INK, MUTED = '#0c0f12', '#171c21', '#49453d', '#d6c1a1', '#efe6d8', '#b9b0a2'
FONT = '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
SERIF = '/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf'
LABELS = []


def text(x, y, value, size=32, anchor='start', color=INK, serif=False, limit=910):
    width = ImageFont.truetype(SERIF if serif else FONT, size).getlength(value)
    assert width <= limit, (value, width, limit)
    LABELS.append({'text': value, 'font_px': size, 'width': width, 'limit': limit})
    family = 'DejaVu Serif' if serif else 'DejaVu Sans'
    return f'<text x="{x}" y="{y}" font-family="{family}" font-size="{size}" text-anchor="{anchor}" fill="{color}">{escape(value)}</text>'


def box(x, y, w, h):
    return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="5" fill="{PANEL}" stroke="{LINE}"/>'


def arrow(x, y, w=45):
    return f'<path d="M{x} {y}h{w}m-12-10l12 10-12 10" fill="none" stroke="{GOLD}" stroke-width="3"/>'


def pill(x, y, w, value):
    return box(x, y, w, 46) + text(x+w/2, y+33, value, 30, 'middle', GOLD, limit=w-10)


def emblem():
    group = next(c for c in ET.parse(ASSETS/'crowned-workshop-emblem.svg').getroot() if c.tag.endswith('g'))
    return '<g transform="translate(895 24) scale(.23)" color="'+GOLD+'">'+ET.tostring(group, encoding='unicode')+'</g>'


def write(key, title, desc, content):
    svg = f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" aria-labelledby="title desc"><title id="title">{escape(title)}</title><desc id="desc">{escape(desc)}</desc>'
    svg += f'<rect width="{W}" height="{H}" fill="{BG}"/><rect x="12" y="12" width="976" height="476" rx="5" fill="none" stroke="{LINE}"/>'
    svg += emblem() + text(34, 77, title, 39, color=GOLD, serif=True, limit=825)
    svg += f'<path d="M34 103H966" stroke="{LINE}"/>' + content + '</svg>\n'
    source = DEST/(key+'.svg')
    source.write_text(svg)
    cairosvg.svg2png(bytestring=svg.encode(), write_to=str(source.with_suffix('.png')))
    return source.with_suffix('.png')


def cards(items, y=132, h=258, font=32):
    count = len(items); w = (932-(count-1)*32)/count; c = ''
    for i, (name, lines) in enumerate(items):
        x = 34+i*(w+32)
        c += box(x, y, w, h)+text(x+20, y+50, name, font+4, color=GOLD, serif=True, limit=w-40)
        for n, line in enumerate(lines):
            c += text(x+20, y+104+n*49, line, font, limit=w-40)
    return c


def export():
    DEST.mkdir(exist_ok=True); LABELS.clear(); files=[]
    def add(k, t, d, c): files.append(write(k, t, d, c))
    c=cards([('DLSS', ['Choose quality', 'Choose model']), ('FSR', ['3.1 / 4 / 4.1.1', 'GPU choices']), ('XeSS', ['7 quality modes', 'Its own ratios'])], h=226, font=29)
    for i, letter in enumerate(('E', 'F', 'J', 'K', 'M', 'L')): c+=pill(41+i*47, 302, 40, letter)
    c+=text(34, 414, 'Same choices in Image and while playing', 32, color=GOLD)
    c+=text(34, 462, 'Lower-resolution scene', 32)+arrow(433, 451, 44)+text(497, 462, 'Reconstructed output', 32)
    add('upscaling', 'MORE UPSCALING CHOICES', 'Quality and DLSS model presets are independent. XeSS adds seven dedicated modes with different ratios. Choose the same settings in Image in both interfaces.', c)

    c=text(34, 156, 'Real frames keep the game moving', 32, color=GOLD)
    for i, kind in enumerate(('REAL', 'FG', 'REAL', 'FG', 'REAL', 'FG')):
        x=34+i*157;c+=box(x, 181, 142, 70)+text(x+71, 227, kind, 32, 'middle', INK if kind=='REAL' else GOLD, limit=132)
    c+=text(34, 297, 'FG adds display updates between them', 32)
    c+=pill(34, 330, 220, 'FSR ×2')+pill(270, 330, 390, 'NVIDIA ×2–×6')+pill(676, 330, 290, 'SDR + HDR10')
    c+=text(34, 427, 'Combine FG with your chosen upscaler', 32, color=GOLD)+text(34, 470, 'Modes depend on supported GPU / driver', 30, color=MUTED)
    add('frame-generation', 'FRAME GENERATION + HDR', 'Extra display frames do not advance game logic. FSR x2 and supported NVIDIA x2–x6 modes support SDR and HDR10.', c)

    c=cards([('NVIDIA Reflex', ['Off / On / On + Boost', 'FG enables On']), ('AMD Anti-Lag 2', ['Supported Radeon driver', 'Input / presentation pacing'])], h=225, font=28)
    c+=text(34, 415, 'Available separately from upscaling', 32, color=GOLD)+text(34, 463, 'Find both controls in Frames', 32)
    add('latency', 'LATENCY CONTROLS, TOGETHER', 'Reflex and Anti-Lag 2 are in Frames in both interfaces and work independently of upscaling. NVIDIA FG enables Reflex automatically.', c)

    c=box(34, 126, 932, 184)+text(54, 167, 'Real cap 75 FPS + ×2 FG', 34, color=GOLD)
    for y, left, right in [(217, 'Output cap off', 'Up to 150 output FPS'), (271, 'Output cap 120', 'Up to 60 real + 60 FG')]:
        c+=text(54, y, left, 32)+arrow(374, y-11, 48)+text(447, y, right, 32)
    c+=text(34, 359, 'Drag gently, use arrows, or type the number', 32, color=GOLD)
    for i, label in enumerate(('Pause', '30 FPS', '60 FPS')): c+=pill(34+i*243, 387, 220, label)
    c+=text(34, 472, 'Background policy returns to your foreground cap', 30, color=MUTED)
    add('fps-limits', 'FRAME CAPS + BACKGROUND', 'Real and optional output caps work together. Exact entries complement relative dragging. Background pause or 30/60 FPS is optional; generated frames are disabled under a background cap.', c)

    c=cards([('Teleport / camera cut', ['Old scene history', 'is reset']), ('Fresh scene history', ['Rebuild from the', 'current scene'])], h=205, font=29)
    c+=text(34, 401, 'Ordinary movement keeps accumulation', 32, color=GOLD)+text(34, 463, 'Shared reset: DLSS / FSR / XeSS / TAA / FG', 30, color=MUTED)
    add('temporal', 'HISTORY AFTER A SCENE CHANGE', 'Camera cuts, teleports and resolution changes reset temporal history. Ordinary movement retains accumulation.', c)

    c=cards([('Borderless fullscreen', ['Desktop resolution', 'Fast Alt-Tab', 'Optional V-sync']), ('When unfocused', ['Keep running / Pause', 'or cap to 30 / 60 FPS', 'Resume your settings'])], font=30)
    c+=text(34, 463, 'Window controls live in Window in both interfaces', 30, color=MUTED)
    add('window', 'ALT-TAB ON YOUR TERMS', 'Borderless uses the desktop mode. Unfocused game work can continue, pause or run at 30/60 FPS. Foreground settings return on focus.', c)

    c=text(34, 155, 'Keep the basic readout, customize it, or hide it', 32, color=GOLD)
    c+=box(34, 183, 932, 80)+text(54, 235, '120fps  DLSS (L)  1920×1080>3840×2160', 32)
    for i, value in enumerate(('FG mode', 'PC latency', 'Real-frame graph')): c+=pill(34+i*317, 298, 297, value)
    c+=text(34, 405, 'Optional text stays on one line', 32, color=GOLD)+text(34, 466, 'The graph adds a small row only when enabled', 30, color=MUTED)
    add('overlay', 'THE INFORMATION YOU WANT', 'Optional preset, resolution, active FG, Reflex PC latency and a raw real-frame trace keep the overlay compact. Displayed values illustrate formatting.', c)

    c=cards([('Multipliers', ['Damage / damage reduction', 'Blood Echoes / movement']), ('Optional toggles', ['Stamina / consumables', 'No fall damage'])], font=28)
    c+=text(34, 427, 'Together with the original startup cheats', 32, color=GOLD)+text(34, 473, 'Off by default · Open reports are tracked in the guide', 29, color=MUTED)
    add('cheats', 'CHOOSE HOW YOU PLAY', 'Runtime multipliers and stamina, consumable and fall-damage options sit alongside original startup patches. The guide records unresolved reports.', c)

    c=text(34, 161, 'Insert on keyboard  /  L3+R3 on controller', 32, color=GOLD)
    for row, names in enumerate((('Image', 'Frames', 'Window'), ('Overlay', 'Cheats', 'Effects'))):
        for i, name in enumerate(names): c+=pill(34+i*317, 207+row*75, 270, name)
    c+=pill(34, 357, 270, 'Advanced')+text(340, 389, 'English / Russian', 32, color=GOLD)+text(34, 463, 'Same categories and saved choices as the launcher', 30, color=MUTED)
    add('in-game', 'FIND SETTINGS WHILE PLAYING', 'Seven menu tabs match the launcher. English/Russian controls and saved preferences are shared.', c)

    c=box(34, 132, 310, 258)+box(394, 132, 572, 258)+arrow(355, 258, 26)
    c+=text(55, 185, 'PLAY', 39, color=GOLD, serif=True, limit=270)+text(55, 243, 'Quick choices', 32, limit=270)+text(55, 301, 'Start the game', 32, limit=270)
    c+=text(415, 183, 'SEVEN SETTINGS PAGES', 32, color=GOLD, limit=526)
    for i, line in enumerate(('Image / Frames / Window', 'Overlay / Cheats / Effects', 'Advanced')): c+=text(415, 237+i*52, line, 31, limit=526)
    c+=text(34, 463, 'One full page per option · Shared preferences', 30, color=MUTED)
    add('launcher', 'QUICK START, CLEAR SETTINGS', 'Play retains quick choices. Full settings have one category each, grouped sections and matching in-game names.', c)

    c=box(34, 131, 932, 167)+text(54, 181, 'Enable developer profiling for a session', 34, color=GOLD)+text(54, 239, 'Then reproduce the problem', 32)
    for i, name in enumerate(('Logs', 'Settings', 'Timings')): c+=pill(34+i*318, 349, 296, name)
    c+=text(34, 464, 'Crash dump when available · Off for normal play', 30, color=MUTED)
    add('diagnostics', 'MAKE A BUG REPORT USEFUL', 'Opt-in session diagnostics retain logs, settings, timings and crash dumps when available.', c)

    v=ROOT/'out/verification';v.mkdir(parents=True, exist_ok=True)
    proof=Image.new('RGB', (720, 6*190), BG)
    for i, p in enumerate(files):
        with Image.open(p) as im:
            proof.paste(im.convert('RGB').resize((360, 180), Image.Resampling.LANCZOS), ((i%2)*360, (i//2)*190))
    proof.save(v/'readme-infographics-mobile-revision21.png')
    (v/'feature-infographics-revision21.json').write_text(json.dumps({'count':len(files), 'dimensions':[W,H], 'editable_svg':True, 'mobile_preview_width':360, 'illustrative_examples':True, 'labels':LABELS}, indent=2)+'\n')
    print(f'PASS: {len(files)} explanatory SVG/PNG figures; {len(LABELS)} measured labels; mobile proof exported.')


if __name__ == '__main__':
    export()
