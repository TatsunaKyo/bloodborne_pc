#!/usr/bin/env python3
"""Export the editable workshop identity. Requires CairoSVG and Pillow.

The original raster paintings stay unchanged. Type and the personal emblem are
editable SVG layers; export them again after changing the lettering or palette.
"""
from pathlib import Path
import cairosvg
from PIL import Image

root = Path(__file__).resolve().parents[1]
assets = root / 'docs/assets'
for source, target in [('tatsunakyo-header.svg', 'crowned-workshop-header.png'),
                       ('crowned-workshop-lantern.svg', 'crowned-workshop-lantern.png')]:
    # These project-owned SVGs load their sibling PNG painting. CairoSVG's safe
    # default blocks local image resources; do not enable this for untrusted SVGs.
    cairosvg.svg2png(url=str(assets / source), write_to=str(assets / target), unsafe=True)
    with Image.open(assets / target) as image:
        assert image.size == (1800, 700)
    print(target)
for size in (64, 256, 512):
    target = assets / f'crowned-workshop-emblem-{size}.png'
    cairosvg.svg2png(url=str(assets / 'crowned-workshop-emblem.svg'),
                    write_to=str(target), output_width=size, output_height=size)
    with Image.open(target) as image:
        assert image.mode == 'RGBA' and image.getpixel((0, 0))[3] == 0
    print(target.name)
for size in (64,256):
    cairosvg.svg2png(url=str(assets / 'crowned-workshop-icon.svg'),
                    write_to=str(assets / f'crowned-workshop-icon-{size}.png'), output_width=size, output_height=size)
with Image.open(assets / 'crowned-workshop-icon-256.png') as image:
    image.save(assets / 'crowned-workshop.ico', sizes=[(16,16),(24,24),(32,32),(48,48),(64,64),(128,128),(256,256)])
print('crowned-workshop.ico')
