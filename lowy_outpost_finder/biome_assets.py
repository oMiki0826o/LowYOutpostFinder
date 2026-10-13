"""File: biome_assets.py
Modification: 2026-10-13 — resolve nested vanilla biome tags from same-version
JAR metadata without claiming to predict the seed's actual biome.
"""
from __future__ import annotations

import json
import re
from zipfile import ZipFile

_VALID_ID = re.compile(r'^(?:[a-z0-9_.-]+:)?[a-z0-9_./-]+$')
_PREFIX = 'data/{namespace}/tags/worldgen/biome/{path}.json'


class MissingBiomeTag(ValueError):
    pass


def expand_biome_tag(archive: ZipFile, tag: str) -> list[str]:
    """Expand `#namespace:tag` references with explicit missing/cycle errors."""
    resolved: set[str] = set()
    visiting: set[str] = set()
    visited: set[str] = set()

    def parse_id(raw: str) -> tuple[str, str]:
        if not isinstance(raw, str) or not _VALID_ID.fullmatch(raw) or '..' in raw or '\\' in raw:
            raise ValueError(f'Invalid biome identifier: {raw!r}')
        namespace, sep, path = raw.partition(':')
        return (namespace, path) if sep else ('minecraft', namespace)

    def visit(name: str) -> None:
        namespace, path = parse_id(name)
        key = f'{namespace}:{path}'
        if key in visited:
            return
        if key in visiting:
            raise ValueError(f'Biome tag cycle at {key}')
        visiting.add(key)
        filename = _PREFIX.format(namespace=namespace, path=path)
        try:
            info = archive.getinfo(filename)
            if not 0 < info.file_size < 256 * 1024:
                raise ValueError(f'Invalid tag size: {filename}')
            entry = json.loads(archive.read(info))
        except KeyError as exc:
            raise MissingBiomeTag(f'Missing required biome tag {key}') from exc
        except (ValueError, UnicodeDecodeError) as exc:
            raise ValueError(f'Invalid biome tag {key}: {exc}') from exc
        values = entry.get('values') if isinstance(entry, dict) else None
        if not isinstance(values, list) or len(values) > 1024:
            raise ValueError(f'Invalid biome tag list {key}')
        for item in values:
            required = True
            if isinstance(item, dict):
                required = item.get('required', True)
                if not isinstance(required, bool):
                    raise ValueError('Invalid biome tag optionality')
                item = item.get('id')
            if not isinstance(item, str):
                raise ValueError('Invalid biome tag entry')
            if item.startswith('#'):
                try:
                    visit(item[1:])
                except MissingBiomeTag:
                    if required:
                        raise
            else:
                bi_ns, bi_path = parse_id(item)
                resolved.add(f'{bi_ns}:{bi_path}')
        visiting.remove(key)
        visited.add(key)

    visit(tag)
    return sorted(resolved)
