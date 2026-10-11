#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright 2026 TatsunaKyo
# SPDX-License-Identifier: GPL-2.0-or-later
"""Export editable README diagrams in the Crowned Workshop's visual style.

Requires CairoSVG and Pillow. Labels and examples describe the implemented
features; no measurements or performance promises are built into the artwork.
"""
from html import escape
from pathlib import Path
import json
import xml.etree.ElementTree as ET
import cairosvg
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / 'docs/assets'
DEST = ASSETS / 'features'
DEST.mkdir(exist_ok=True)
W, H = 1000, 460
INK, GOLD, MUTED = '#f1e9dc', '#d6c1a1', '#b3a48f'
FONT = '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
SERIF = '/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf'

FEATURES = [
    ('upscaling', 'UPSCALING', 'DLSS, FSR and XeSS rebuild a lower-resolution scene for the display. XeSS has seven dedicated quality choices.',
     [('DLSS', 'Model presets'), ('FSR', 'AMD options'), ('XeSS', '7 quality modes')], 'Render → Reconstruct → Display'),
    ('frame-generation', 'FRAME GENERATION', 'FSR adds one intermediate frame. NVIDIA provides fixed FG/MFG multipliers supported by the GPU and driver. Both paths include SDR and HDR10.',
     [('Real frames', 'Game logic'), ('Extra frames', 'Display updates')], 'FSR x2 · NVIDIA FG / MFG · SDR + HDR10'),
    ('latency', 'INPUT & LATENCY', 'NVIDIA Reflex and AMD Anti-Lag 2 can be used independently of the upscaler on supported hardware.',
     [('Reflex', 'NVIDIA GPUs'), ('Anti-Lag 2', 'Supported Radeon')], 'Before input → CPU → Real presentation'),
    ('fps-limits', 'FPS, YOUR WAY', '75 real FPS with x2 generation can produce 150 output FPS. The optional total output cap is separate from game-frame timing.',
     [('75 real FPS', 'Game frames'), ('150 output', 'With x2 FG')], 'Exact number fields · Optional output cap'),
    ('temporal', 'TEMPORAL HISTORY', 'Camera cuts, loading gaps and resolution changes reset temporal history. Unique object histories are retained; ambiguous mesh instances use camera motion.',
     [('Camera cut', 'Discard old scene'), ('Fresh history', 'Rebuild the image')], 'DLSS · FSR · XeSS · TAA · Frame Generation'),
    ('window', 'WINDOW & BACKGROUND', 'Windowed, borderless and fullscreen choices share a background policy: keep running, pause, or limit real frames to 30 or 60 FPS.',
     [('Borderless', 'Easy Alt-Tab'), ('Background', 'Pause · 30 · 60')], 'Windowed · Borderless · Fullscreen'),
    ('overlay', 'YOUR COMPACT OVERLAY', 'Keep the original FPS overlay, disable it, or add individual preset, resolution, FG and supported latency fields on the same line.',
     [('Choose fields', 'Preset · Size · FG'), ('Keep it small', 'Optional latency')], 'Basic overlay · Custom readout · Off'),
    ('cheats', 'OPTIONAL GAMEPLAY TOOLS', 'The added cheats include damage and reward multipliers, movement speed, infinite stamina, no-consume and no fall damage. Their open checks remain in the cheat guide.',
     [('Combat', 'Damage · Echoes'), ('Movement', 'Speed · Stamina')], 'Consumables · No fall damage · Off by default'),
    ('in-game', 'SETTINGS WHILE PLAYING', 'Insert or L3+R3 opens the English/Russian in-game menu. Its shared preferences are also used by the launcher.',
     [('INSERT', 'Keyboard'), ('L3 + R3', 'Controller')], 'English / Russian · Shared preferences'),
    ('launcher', 'THE CROWNED WORKSHOP', 'The launcher carries TatsunaKyo’s identity, credits the original Windows port and shows dedicated DLSS or XeSS quality controls when selected.',
     [('Play', 'Quick choices'), ('Graphics', 'Fine adjustments')], 'Conditional selectors · Scalable layout'),
    ('diagnostics', 'WHEN SOMETHING BREAKS', 'Opt-in developer profiling records session logs, settings and timings, with Windows crash dumps when available.',
     [('Opt-in', 'Developer profiling'), ('Session logs', 'Settings · Timings')], 'Crash clues · Off by default'),
]

def text(x, y, content, size=40, color=INK, serif=False, anchor='middle'):
    # Keep text large and stable across exports; fail instead of silently shrinking it.
    font = ImageFont.truetype(SERIF if serif else FONT, size)
    assert font.getlength(content) <= (880 if y < 130 or y > 360 else 370), content
    family = 'DejaVu Serif' if serif else 'DejaVu Sans'
    return f'<text x="{x}" y="{y}" text-anchor="{anchor}" fill="{color}" font-family="{family}" font-size="{size}">{escape(content)}</text>'

def panel(x, y=145, width=390, height=194):
    return (f'<rect x="{x}" y="{y}" width="{width}" height="{height}" rx="4" fill="#1b1714" stroke="#5c4e40"/>'
            f'<path d="M{x+16} {y+height-18}V{y+16}H{x+width-16}" fill="none" stroke="#aa8f6e" stroke-opacity=".3"/>')

def emblem():
    root = ET.parse(ASSETS / 'crowned-workshop-emblem.svg').getroot()
    g = next(c for c in root if c.tag.endswith('g'))
    return '<g transform="translate(896 31) scale(.22)" color="'+GOLD+'">'+ET.tostring(g, encoding='unicode')+'</g>'

def render(key, title, description, panels, footer):
    parts = ['<svg xmlns="http://www.w3.org/2000/svg" width="1000" height="460" viewBox="0 0 1000 460" role="img" aria-labelledby="title desc">',
             '<title id="title">'+escape(title)+'</title><desc id="desc">'+escape(description)+'</desc>',
             '<rect width="1000" height="460" fill="#12100f"/>',
             '<rect x="12" y="12" width="976" height="436" rx="4" fill="none" stroke="#655341"/>',
             '<path d="M32 100H968M32 365H968" stroke="#5c4e40"/>', emblem(),
             text(42, 77, title, 44, GOLD, serif=True, anchor='start')]
    if key == 'upscaling':
        for x, (name, subtitle) in zip((60, 370, 680), panels):
            parts.append(panel(x, width=260))
            parts.append(text(x+130, 231, name, 54, GOLD, serif=True))
            parts.append(text(x+130, 294, subtitle, 29, MUTED))
    else:
        for x, (name, subtitle) in zip((60, 550), panels):
            parts.append(panel(x))
            parts.append(text(x+195, 231, name, 44, GOLD, serif=True))
            parts.append(text(x+195, 295, subtitle, 32, MUTED))
        if key in ('fps-limits', 'temporal', 'window', 'overlay', 'launcher', 'diagnostics'):
            parts.append('<path d="M474 238H523M510 226L523 238L510 250" fill="none" stroke="#8d7964" stroke-width="3"/>')
        elif key == 'frame-generation':
            parts.append('<path d="M481 238H519M500 219V257" fill="none" stroke="#8d7964" stroke-width="3"/>')
    parts.append(text(500, 418, footer, 32, INK))
    parts.append('</svg>')
    source = DEST / (key+'.svg'); target = source.with_suffix('.png')
    source.write_text('\n'.join(parts)+'\n', encoding='utf-8')
    cairosvg.svg2png(url=str(source),write_to=str(target))
    with Image.open(target) as image: assert image.size == (W,H)
    print(target.relative_to(ROOT))
    return target

def main():
    files = [render(*feature) for feature in FEATURES]
    # A mobile-width proof sheet is useful when changing the type or spacing.
    proof = Image.new('RGB', (360, len(files)*174), '#12100f')
    for i, path in enumerate(files):
        with Image.open(path) as image:
            proof.paste(image.convert('RGB').resize((360,166),Image.Resampling.LANCZOS),(0,i*174))
    verification = ROOT / 'out/verification'; verification.mkdir(parents=True,exist_ok=True)
    proof.save(verification/'readme-infographics-mobile-revision14.png')
    (verification/'feature-infographics-revision14.json').write_text(json.dumps({'count':len(files),'dimensions':[W,H],'editable_svg':True,'mobile_proof_width':360,'features':[f[0] for f in FEATURES]},indent=2)+'\n')

if __name__ == '__main__': main()
