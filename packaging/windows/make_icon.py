"""Makes the Bloodborne icon (the launcher's emblem on a dark rounded tile) as .ico and .png from
launcher/assets/emblem.png. Needs Pillow.
usage: make_icon.py launcher/bloodborne.ico launcher/bloodborne.png"""
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

EMBLEM = Path(__file__).resolve().parents[2] / 'launcher' / 'assets' / 'emblem.png'
SIZES = (16, 20, 24, 32, 40, 48, 64, 96, 128, 256)  # what Windows asks for at 100-200 % scaling
TILE = (13, 16, 20, 255)  # the launcher's background


def icon(size):
    """The tile drawn four times as large and scaled down (smooth corners), the emblem on it: a
    little larger at the smallest sizes, where every pixel counts, and sharpened there."""
    big = size * 4
    tile = Image.new('RGBA', (big, big), (0, 0, 0, 0))
    ImageDraw.Draw(tile).rounded_rectangle((0, 0, big - 1, big - 1), radius=round(big * 0.2), fill=TILE)
    tile = tile.resize((size, size), Image.LANCZOS)
    emblem = Image.open(EMBLEM).convert('RGBA')
    box = round(size * (0.86 if size <= 24 else 0.8))
    emblem.thumbnail((box, box), Image.LANCZOS)
    if size <= 32:
        emblem = emblem.filter(ImageFilter.UnsharpMask(radius=0.6, percent=60, threshold=1))
    tile.alpha_composite(emblem, ((size - emblem.width) // 2, (size - emblem.height) // 2))
    return tile


images = [icon(size) for size in SIZES]
images[-1].save(sys.argv[1], sizes=[(s, s) for s in SIZES], append_images=images[:-1])
icon(128).save(sys.argv[2])
