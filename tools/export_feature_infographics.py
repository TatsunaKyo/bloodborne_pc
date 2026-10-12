#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright 2026 TatsunaKyo
# SPDX-License-Identifier: GPL-2.0-or-later
"""Regenerate the editable README figures and their mobile proof sheet.

Requires CairoSVG and Pillow. Layout and exact setup examples live in
feature_storyboards.py.
"""
from feature_storyboards import export

if __name__ == '__main__':
    export()
