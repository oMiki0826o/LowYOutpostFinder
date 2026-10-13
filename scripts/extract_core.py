"""File: extract_core.py
Modification: 2026-10-13 — safely unpack an optional upstream C source ZIP.
"""
from __future__ import annotations

import argparse
from pathlib import Path, PurePosixPath
import stat
import zipfile

MAX_TOTAL_UNCOMPRESSED = 250_000_000
MAX_ENTRY_UNCOMPRESSED = 35_000_000
MAX_ENTRIES = 20000


def extract_zip_source(source: Path, destination: Path) -> None:
    """Reject traversal, symbolic links and oversized members before extraction."""
    with zipfile.ZipFile(source) as archive:
        members = archive.infolist()
        if len(members) > MAX_ENTRIES:
            raise ValueError('Unsafe ZIP: too many entries')
        size = 0
        for entry in members:
            relative = PurePosixPath(entry.filename)
            mode = (entry.external_attr >> 16) & 0xffff
            if (relative.is_absolute() or not entry.filename or '\\' in entry.filename
                    or '..' in relative.parts or not relative.parts[0]
                    or stat.S_ISLNK(mode)):
                raise ValueError(f'Unsafe ZIP path or symbolic link: {entry.filename!r}')
            if entry.file_size > MAX_ENTRY_UNCOMPRESSED:
                raise ValueError('Unsafe ZIP: entry too large')
            size += entry.file_size
            if size > MAX_TOTAL_UNCOMPRESSED:
                raise ValueError('Unsafe ZIP: expanded archive too large')
        for entry in members:
            output = destination.joinpath(*PurePosixPath(entry.filename).parts)
            if entry.is_dir():
                output.mkdir(parents=True, exist_ok=True)
            else:
                output.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(entry) as read, output.open('wb') as write:
                    while block := read.read(1024 * 1024):
                        write.write(block)


def main() -> int:
    parser = argparse.ArgumentParser(description='Unpack a vetted source ZIP into the build tree')
    parser.add_argument('archive', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    extract_zip_source(args.archive, args.output)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
