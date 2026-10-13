#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright 2026 TatsunaKyo
# SPDX-License-Identifier: GPL-2.0-or-later
"""Render maintained feature SVGs, preserving approved designs and existing GIFs.

Requires CairoSVG and Pillow. Regenerate the FG animation with export_fg_toggle.py
following the actual UI capture fixture; its values are illustrative.
"""
import argparse
from pathlib import Path
import cairosvg
from feature_storyboards import export_save_manager

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--only', choices=['save-manager'], help='Export just this figure.')
    args = parser.parse_args()
    if args.only == 'save-manager':
        export_save_manager()
    else:
        directory = Path(__file__).resolve().parents[1] / 'docs/assets/features'
        for source in sorted(directory.glob('*.svg')):
            cairosvg.svg2png(url=str(source), write_to=str(source.with_suffix('.png')))
        print('Rendered current editable SVG designs; animated GIFs retained.')
