"""File: worldgen_contract.py
Modification: 2026-10-13 — inspect version-bound vanilla Noise Router dependencies.

The contract is a lossless reference to the original settings, not a
NoiseChunkGenerator implementation. Unknown/missing references fail closed.
"""
from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path
import zipfile

from game_archive import open_game_assets, require_matching_game_version
from geometry_audit import write_json_atomic
from versions import check_version

BASE = 'data/minecraft/worldgen/'
MAX_JSON = 2 * 1024 * 1024


def _read_json(archive: zipfile.ZipFile, name: str):
    try:
        info = archive.getinfo(name)
    except KeyError as exc:
        raise ValueError(f'Missing vanilla worldgen dependency: {name}') from exc
    if not 0 < info.file_size <= MAX_JSON:
        raise ValueError(f'Unexpected vanilla worldgen asset size: {name}')
    try:
        raw = archive.read(info)
        return json.loads(raw.decode('utf-8')), hashlib.sha256(raw).hexdigest()
    except (UnicodeDecodeError, json.JSONDecodeError, OSError) as exc:
        raise ValueError(f'Unreadable vanilla worldgen dependency: {name}') from exc


def inspect_contract(game_jar: Path, version: str, preset: str = 'overworld') -> dict:
    """Resolve version-specific density and noise references with cycle detection.

    Does not claim to emulate noise, biome selection, or chunk generation.
    """
    check_version(version)
    if preset == 'large_biomes':
        raise ValueError('The large_biomes noise settings are a builtin registry entry, not a serialized vanilla JSON; contract inspection is unavailable')
    if preset != 'overworld':
        raise ValueError('Unsupported worldgen preset')
    require_matching_game_version(Path(game_jar), version)
    settings_name = BASE + 'noise_settings/overworld.json'
    seen: set[str] = set()
    active: set[str] = set()
    visited: dict[str, str] = {}
    operators: Counter[str] = Counter()
    noise_refs: set[str] = set()

    with open_game_assets(Path(game_jar)) as jar:
        settings, settings_sha = _read_json(jar, settings_name)
        if not isinstance(settings, dict) or not isinstance(settings.get('noise'), dict) or not isinstance(settings.get('noise_router'), dict):
            raise ValueError('Malformed vanilla Noise Settings')
        shape = settings['noise']
        min_y, height = shape.get('min_y'), shape.get('height')
        if type(min_y) is not int or type(height) is not int or height <= 0 or height % 16:
            raise ValueError('Invalid vanilla terrain height dimensions')
        if 'final_density' not in settings['noise_router']:
            raise ValueError('Noise Router lacks final_density')

        def walk(node):
            if isinstance(node, dict):
                if isinstance(node.get('type'), str):
                    operators[node['type']] += 1
                for key, child in node.items():
                    if key == 'noise' and isinstance(child, str) and child.startswith('minecraft:'):
                        noise_refs.add(child)
                    elif key != 'noise':
                        walk(child)
            elif isinstance(node, list):
                for child in node:
                    walk(child)
            elif isinstance(node, str) and node.startswith(('minecraft:overworld/', 'minecraft:overworld_large_biomes/')):
                visit_density(node)

        def visit_density(ref: str):
            if ref in active:
                raise ValueError(f'Cyclic vanilla density reference: {ref}')
            if ref in seen:
                return
            active.add(ref)
            path = BASE + 'density_function/' + ref.split(':', 1)[1] + '.json'
            data, digest = _read_json(jar, path)
            visited[path] = digest
            walk(data)
            active.remove(ref)
            seen.add(ref)

        walk(settings['noise_router'])
        for name in sorted(noise_refs):
            path = BASE + 'noise/' + name.split(':', 1)[1] + '.json'
            _data, digest = _read_json(jar, path)
            visited[path] = digest
        checked = '\n'.join(f'{key}:{digest}' for key, digest in sorted(visited.items()))
        return {
            'version': version,
            'preset': preset,
            'noise_settings': {'min_y': min_y, 'height': height,
                               'aquifers_enabled': settings.get('aquifers_enabled')},
            'density_files_visited': len(seen),
            'noise_files_visited': len(noise_refs),
            'density_operators': dict(sorted(operators.items())),
            'sha256': {'worldgen_settings': settings_sha,
                       'transitive_dependencies': hashlib.sha256(checked.encode('utf-8')).hexdigest()},
            'seed_equivalence_proven': False,
            'status': 'resource_graph_verified_only',
            'limitations': 'Resource/reference integrity is not an executable Noise/Biome/Jigsaw simulation.',
        }


def run_contract(args) -> None:
    report = inspect_contract(args.game_jar, args.version, args.preset)
    if args.out:
        write_json_atomic(args.out, report)
    print(json.dumps(report, ensure_ascii=False, indent=2))


def add_command(commands) -> None:
    from versions import SUPPORTED
    parser = commands.add_parser('worldgen-contract', help='核對原版 Noise Router、密度函數與噪聲參數相依；非精確高度搜尋')
    parser.add_argument('--version', required=True, choices=sorted(SUPPORTED))
    parser.add_argument('--game-jar', required=True, type=Path)
    parser.add_argument('--preset', choices=['overworld'], default='overworld')
    parser.add_argument('--out', type=Path)
    parser.set_defaults(run=run_contract)
