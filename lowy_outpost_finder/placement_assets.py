"""File: placement_assets.py
Modification: 2026-10-13 — fail-closed vanilla placement rule compatibility checks.

The Java seed-only candidate algorithm has fixed spacing/offsets. When a
matching-version assets archive is available, reject any placement rules
that do not match the algorithm; never silently mislabel the output.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import zipfile
from game_archive import open_game_assets


@dataclass(frozen=True)
class PlacementCheck:
    supported: bool
    outpost_sha256: str
    villages_sha256: str


def _read_json(archive: zipfile.ZipFile, member: str) -> tuple[dict, str]:
    try:
        info = archive.getinfo(member)
    except KeyError as exc:
        raise ValueError(f'Game JAR lacks {member}') from exc
    if not 0 < info.file_size < 256 * 1024:
        raise ValueError(f'Game JAR has invalid size for {member}')
    try:
        data = archive.read(info)
        value = json.loads(data)
    except (UnicodeDecodeError, json.JSONDecodeError, RuntimeError, OSError) as exc:
        raise ValueError(f'Cannot parse {member}: {exc}') from exc
    if not isinstance(value, dict):
        raise ValueError(f'{member} is not a JSON object')
    return value, hashlib.sha256(data).hexdigest()


def _require_placement(data: dict, expected: dict, name: str) -> None:
    got = data.get('placement')
    if not isinstance(got, dict):
        raise ValueError(f'{name} missing placement object')
    # Allow Minecraft's JSON defaults (absent) and explicit defaults (present).
    got = dict(got)
    got.setdefault('spread_type', 'linear')
    got.setdefault('frequency', 1.0)
    got.setdefault('frequency_reduction_method', 'default')
    expected = dict(expected)
    expected.setdefault('spread_type', 'linear')
    expected.setdefault('frequency', 1.0)
    expected.setdefault('frequency_reduction_method', 'default')
    for key, want in expected.items():
        if got.get(key) != want:
            raise ValueError(f'{name} incompatible {key}: expected {want!r}, got {got.get(key)!r}')
    # Unknown directives (offsets, proprietary placement extensions) might alter results.
    allowed = set(expected) | {'locate_offset'}
    extras = set(got) - allowed
    if extras:
        raise ValueError(f'{name} unsupported placement keys: {sorted(extras)}')
    if 'locate_offset' in got and got['locate_offset'] != [0, 0, 0]:
        raise ValueError(f'{name} unsupported locate_offset')


def validate_placement_assets(jar_path: Path) -> PlacementCheck:
    """Validate the two structure sets against hardcoded Java 1.21+ placement.

    Does not check biome/terrain/Jigsaw, certify archive signature, or prove
    this archive is the version the user claims it is.
    """
    root = 'data/minecraft/worldgen/structure_set/'
    try:
        with open_game_assets(Path(jar_path)) as archive:
            outposts, out_hash = _read_json(archive, root + 'pillager_outposts.json')
            villages, village_hash = _read_json(archive, root + 'villages.json')
    except (OSError, zipfile.BadZipFile, zipfile.LargeZipFile) as exc:
        raise ValueError(f'Cannot open worldgen assets JAR: {exc}') from exc
    if outposts.get('structures') != [{'structure': 'minecraft:pillager_outpost', 'weight': 1}]:
        raise ValueError('Unsupported pillager_outposts structures/weights')
    _require_placement(outposts, {
        'type': 'minecraft:random_spread', 'spacing': 32, 'separation': 8,
        'salt': 165745296, 'frequency': 0.2,
        'frequency_reduction_method': 'legacy_type_1',
        'exclusion_zone': {'chunk_count': 10, 'other_set': 'minecraft:villages'},
    }, 'pillager_outposts')
    entries = villages.get('structures')
    if not isinstance(entries, list) or not entries or any(
        not isinstance(x, dict) or x.get('weight') != 1 or
        x.get('structure') not in {
            'minecraft:village_plains', 'minecraft:village_desert',
            'minecraft:village_savanna', 'minecraft:village_snowy',
            'minecraft:village_taiga'} for x in entries):
        raise ValueError('Unsupported villages structure set')
    _require_placement(villages, {
        'type': 'minecraft:random_spread', 'spacing': 34, 'separation': 8,
        'salt': 10387312,
    }, 'villages')
    return PlacementCheck(True, out_hash, village_hash)
