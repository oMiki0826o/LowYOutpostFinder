"""File: build_region_scan.py
Modification: 2026-10-13 — build standalone fast scanner (no Minecraft dependencies).
"""
from __future__ import annotations

from pathlib import Path
import os
import shutil
import subprocess


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    compiler = next((shutil.which(c) for c in ('cc', 'clang', 'gcc') if shutil.which(c)), None)
    if not compiler:
        raise SystemExit('A C11 compiler (cc / clang / gcc) is required. Use --engine python otherwise.')
    dest = root / 'bin' / ('region_scan.exe' if os.name == 'nt' else 'region_scan')
    dest.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run([compiler, '-O2', '-std=c11', '-Wall', '-Wextra', '-Werror',
                    str(root / 'src' / 'region_scan.c'), '-o', str(dest)], check=True)
    print(f'Built: {dest}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
