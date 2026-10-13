#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright 2026 TatsunaKyo
# SPDX-License-Identifier: GPL-2.0-or-later
"""Regenerate the editable README figures and their mobile proof sheet.

Requires CairoSVG and Pillow. Layout and exact setup examples live in
feature_storyboards.py.
"""
import argparse
from feature_storyboards import export, export_save_manager

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--only', choices=['save-manager'], help='Export just this figure.')
    args = parser.parse_args()
    if args.only == 'save-manager':
        export_save_manager()
    else:
        export()
