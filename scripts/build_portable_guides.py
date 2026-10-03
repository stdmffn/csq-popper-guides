#!/usr/bin/env python3
"""Build a self-contained Windows guide installer from a verified Python runtime ZIP."""
from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[1]
RUNTIME_SHA256 = 'f6cca216a359be84797cabb54149ce5e062afb16cc7567eb7fc51cacb2d86b65'


def build(runtime: Path, output: Path) -> None:
    if hashlib.sha256(runtime.read_bytes()).hexdigest() != RUNTIME_SHA256:
        raise ValueError('Runtime checksum does not match the official Python 3.13.7 x64 ZIP.')
    source = ROOT / 'portable/popper-guides'
    files = ['guides.py', 'catalog.json', 'README.txt', 'Install.cmd', 'Preview.cmd',
             'Install mappings.cmd', 'Uninstall.cmd']
    output.parent.mkdir(parents=True, exist_ok=True)
    prefix = 'Curious-Side-Quests-Popper-Guides/'
    with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as target:
        for name in files:
            target.write(source / name, prefix + name)
        with zipfile.ZipFile(runtime) as embedded:
            for info in embedded.infolist():
                if info.filename.startswith('/') or '..' in Path(info.filename).parts:
                    raise ValueError('Unsafe runtime archive path.')
                target.writestr(prefix + 'runtime/' + info.filename, embedded.read(info))
    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    output.with_suffix('.zip.sha256').write_text(f'{digest}  {output.name}\n')
    print(f'{output} ({output.stat().st_size:,} bytes)\nSHA-256: {digest}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('runtime', type=Path)
    parser.add_argument('--output', type=Path,
                        default=ROOT / 'releases/Curious-Side-Quests-Popper-Guides.zip')
    args = parser.parse_args()
    build(args.runtime, args.output)
