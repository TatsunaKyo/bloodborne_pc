# SPDX-FileCopyrightText: Copyright 2026 TatsunaKyo
# SPDX-License-Identifier: GPL-2.0-or-later
"""Materialize this Python's Tcl/Tk libraries, including Tcl 9's zipfs resources."""
import argparse
import json
from pathlib import Path
import shutil
import tkinter as tk


def prepare(output):
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    marker = output / 'tk-runtime.json'
    root = tk.Tk(); root.withdraw()
    try:
        libraries = {'_tcl_data': root.tk.call('info', 'library'),
                     '_tk_data': root.tk.call('set', 'tk_library')}
        for name, library in libraries.items():
            destination = output / name
            if destination.exists():
                if not marker.is_file():
                    raise RuntimeError('Refusing to replace an unmarked Tcl/Tk staging folder.')
                shutil.rmtree(destination)
            # The Tcl filesystem API can read embedded zipfs paths that Python
            # Path/shutil and the existing PyInstaller discovery hook cannot.
            root.tk.call('file', 'copy', '-force', '--', library, str(destination))
        if not (output / '_tcl_data/init.tcl').is_file() or not (output / '_tk_data/tk.tcl').is_file():
            raise RuntimeError('The materialized Tcl/Tk libraries are incomplete.')
        identity = {'tcl_version': str(root.tk.call('info', 'patchlevel')),
                    'tk_version': str(root.tk.call('set', 'tk_patchLevel')),
                    'source': {k: str(v) for k, v in libraries.items()}}
        marker.write_text(json.dumps(identity, indent=2) + '\n')
        return identity
    finally:
        root.destroy()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=Path('out/tk-runtime'))
    args = parser.parse_args()
    print(json.dumps(prepare(args.output), indent=2))
