"""File: game_archive.py
Modification: 2026-10-13 — bounded, read-only support for official nested server JAR assets.

A standard Mojang server.jar is a launcher containing one game-data JAR.
No extraction to disk and no execution of the user-supplied archive is needed.
"""
from __future__ import annotations

from contextlib import contextmanager
import io
import json
from pathlib import Path
from typing import Iterator
import zipfile

MAX_INNER_JAR_BYTES = 128 * 1024 * 1024
VERSION_PATH = 'version.json'
WORLDGEN_MARKER = 'data/minecraft/worldgen/structure_set/pillager_outposts.json'
STRUCTURE_MARKER = 'data/minecraft/worldgen/structure/pillager_outpost.json'


def declared_game_version(jar_path: Path) -> dict | None:
    """Read optional top-level version.json; bare game assets have no such metadata."""
    try:
        with zipfile.ZipFile(jar_path) as archive:
            if VERSION_PATH not in archive.namelist():
                return None
            info = archive.getinfo(VERSION_PATH)
            if not 0 < info.file_size <= 16384:
                raise ValueError('Invalid game version.json size')
            obj = json.loads(archive.read(info))
            if not isinstance(obj, dict) or not isinstance(obj.get('id'), str):
                raise ValueError('Invalid game version.json metadata')
            return obj
    except (OSError, zipfile.BadZipFile, zipfile.LargeZipFile, json.JSONDecodeError) as exc:
        raise ValueError(f'Cannot inspect game JAR version: {exc}') from exc


def require_matching_game_version(jar_path: Path, selected_version: str) -> dict | None:
    metadata = declared_game_version(jar_path)
    if metadata is not None and metadata['id'] != selected_version:
        raise ValueError(f'Game JAR version mismatch: {metadata["id"]} != {selected_version}')
    return metadata


@contextmanager
def open_game_assets(jar_path: Path) -> Iterator[zipfile.ZipFile]:
    """Open either unpacked game-data JAR or a Mojang launcher JAR bundle.

    Prevent reading unexpected nested jars or very large objects from
    user-controlled ZIP input. No game files are written to the filesystem.
    """
    try:
        with zipfile.ZipFile(Path(jar_path)) as outer:
            if WORLDGEN_MARKER in outer.namelist() or STRUCTURE_MARKER in outer.namelist():
                yield outer
                return
            entries = [info for info in outer.infolist()
                       if info.filename.startswith('META-INF/versions/')
                       and info.filename.count('/') == 3
                       and info.filename.endswith('.jar')]
            if len(entries) != 1:
                raise ValueError(f'Expected a single embedded game JAR, got {len(entries)}')
            entry = entries[0]
            if not 0 < entry.file_size <= MAX_INNER_JAR_BYTES:
                raise ValueError('Embedded game JAR exceeds safety limit')
            try:
                content = outer.read(entry)
                with zipfile.ZipFile(io.BytesIO(content)) as inner:
                    if WORLDGEN_MARKER not in inner.namelist():
                        raise ValueError('The embedded game JAR is missing worldgen data')
                    yield inner
            except (zipfile.BadZipFile, zipfile.LargeZipFile) as exc:
                raise ValueError('Cannot decode embedded game JAR') from exc
    except (OSError, zipfile.BadZipFile, zipfile.LargeZipFile) as exc:
        raise ValueError(f'Invalid game JAR: {exc}') from exc
