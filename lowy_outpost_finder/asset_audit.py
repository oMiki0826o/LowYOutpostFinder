"""File: asset_audit.py
Modification: 2026-10-13 — read actual server bundle's outpost placement,
biome tag and rigid tower geometry without executing its code.
"""
from __future__ import annotations

import json
from pathlib import Path

from .game_archive import open_game_assets, require_matching_game_version
from .biome_assets import expand_biome_tag
from .placement_assets import validate_placement_assets
from .start_geometry import load_outpost_assets
from .tower_geometry import load_tower_blueprint

BIOME_TAG = 'data/minecraft/tags/worldgen/biome/has_structure/pillager_outpost.json'


def audit_assets(server_jar: Path, version: str) -> dict:
    metadata = require_matching_game_version(server_jar, version)
    placement = validate_placement_assets(server_jar)
    base = load_outpost_assets(server_jar)
    tower = load_tower_blueprint(server_jar)
    with open_game_assets(server_jar) as jar:
        resolved_biomes = expand_biome_tag(jar, 'minecraft:has_structure/pillager_outpost')
        try:
            info = jar.getinfo(BIOME_TAG)
            if not 0 < info.file_size <= 256 * 1024:
                raise ValueError('Invalid pillager outpost biome tag size')
            obj = json.loads(jar.read(info))
        except KeyError as exc:
            raise ValueError('Game JAR lacks pillager outpost biome tag') from exc
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError('Invalid pillager outpost biome tag') from exc
    biomes = obj.get('values') if isinstance(obj, dict) else None
    if not isinstance(biomes, list) or not biomes or not all(isinstance(b, str) and b for b in biomes):
        raise ValueError('Unsupported outpost biome tag definition')
    return {
        'game_version': version,
        'jar_declared_version': metadata['id'] if metadata else None,
        'java_version_required': metadata.get('java_version') if metadata else None,
        'world_data_version': metadata.get('world_version') if metadata else None,
        'placement_validated': placement.supported,
        'outpost_structure_set_sha256': placement.outpost_sha256,
        'villages_structure_set_sha256': placement.villages_sha256,
        'base_size': base.size,
        'tower_size': tower.tower_size,
        'tower_y_offset': tower.tower_min_y_from_base,
        'base_template_sha256': tower.base_sha256,
        'tower_template_sha256': tower.tower_sha256,
        'biomes': biomes,
        'expanded_biomes': resolved_biomes,
        'biome_sampling_verified': False,
        'terrain_noise_verified': False,
        'vanilla_e2e_verified': False,
        'classification': 'version_checked_assets_only',
        'note': 'Assets and rigid tower offset inspected without executing Minecraft. '
                'This does not calculate WORLD_SURFACE_WG or verify that a structure spawns.',
    }


def run_assets_audit(args) -> None:
    from .geometry_audit import write_json_atomic
    report = audit_assets(args.server_jar, args.version)
    if args.out:
        write_json_atomic(args.out, report)
    else:
        print(json.dumps(report, indent=2, ensure_ascii=False))


def add_command(commands) -> None:
    from .versions import SUPPORTED
    from pathlib import Path
    parser = commands.add_parser('assets-audit', help='Inspect matching-version original JAR assets; no world generation')
    parser.add_argument('--version', choices=sorted(SUPPORTED), required=True)
    parser.add_argument('--server-jar', type=Path, required=True)
    parser.add_argument('--out', type=Path)
    parser.set_defaults(run=run_assets_audit)
