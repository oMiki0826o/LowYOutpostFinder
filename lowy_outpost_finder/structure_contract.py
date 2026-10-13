"""File: structure_contract.py
Modification: 2026-10-13 — audit a complete reachable vanilla outpost pool/template graph.

This checks data dependencies and guards unsupported pool elements; it does
not replay Jigsaw RNG order, collision, heights, or successful placement.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from collections import Counter

from .game_archive import open_game_assets, require_matching_game_version
from .tower_geometry import _read_nbt
from .geometry_audit import write_json_atomic
from .versions import check_version
from .worldgen_contract import _read_json, BASE


def inspect_structure_contract(game_jar: Path, version: str) -> dict:
    check_version(version)
    require_matching_game_version(Path(game_jar), version)
    pools: dict[str, str] = {}
    templates: dict[str, str] = {}
    operators: Counter[str] = Counter()
    references = set()

    with open_game_assets(Path(game_jar)) as jar:
        structure, struct_sha = _read_json(jar, BASE + 'structure/pillager_outpost.json')
        if not isinstance(structure, dict) or structure.get('type') != 'minecraft:jigsaw':
            raise ValueError('Unexpected vanilla outpost structure type')
        size = structure.get('size')
        if type(size) is not int or not 0 <= size <= 32:
            raise ValueError('Invalid vanilla Jigsaw depth')
        start_pool = structure.get('start_pool')
        if not isinstance(start_pool, str):
            raise ValueError('Outpost missing start_pool')

        def visit_template(name: str):
            if name in templates:
                return
            nbt, digest = _read_nbt(jar, name)
            templates[name] = digest
            palette = nbt.get('palette')
            blocks = nbt.get('blocks')
            if not isinstance(palette, list) or not isinstance(blocks, list):
                raise ValueError(f'Unexpected Jigsaw template palette/blocks: {name}')
            for block in blocks:
                if not isinstance(block, dict):
                    raise ValueError(f'Malformed NBT template block: {name}')
                state_idx = block.get('state')
                if type(state_idx) is not int or not 0 <= state_idx < len(palette):
                    raise ValueError(f'Malformed NBT template state: {name}')
                state = palette[state_idx]
                if not isinstance(state, dict):
                    raise ValueError(f'Malformed NBT template palette state: {name}')
                if state.get('Name', state.get('id')) == 'minecraft:jigsaw':
                    metadata = block.get('nbt')
                    if not isinstance(metadata, dict):
                        raise ValueError(f'Missing Jigsaw connector metadata: {name}')
                    next_pool = metadata.get('pool')
                    if not isinstance(next_pool, str):
                        raise ValueError(f'Missing Jigsaw pool name: {name}')
                    references.add((name, next_pool))
                    visit_pool(next_pool)

        def visit_element(element: dict):
            if not isinstance(element, dict):
                raise ValueError('Malformed vanilla Jigsaw pool element')
            kind = element.get('element_type')
            if not isinstance(kind, str):
                raise ValueError('Missing vanilla Jigsaw pool element_type')
            operators[kind] += 1
            if kind == 'minecraft:empty_pool_element':
                return
            if kind in ('minecraft:legacy_single_pool_element', 'minecraft:single_pool_element'):
                loc = element.get('location')
                if not isinstance(loc, str):
                    raise ValueError('Missing Jigsaw single_pool template location')
                visit_template(loc)
            elif kind == 'minecraft:list_pool_element':
                children = element.get('elements')
                if not isinstance(children, list) or not 1 <= len(children) <= 512:
                    raise ValueError('Malformed vanilla list pool element')
                for child in children:
                    visit_element(child)
            elif kind == 'minecraft:feature_pool_element':
                # Feature identifiers are resolved by the game's configured
                # feature registry. Record a dependency, without simulating it.
                name = element.get('feature')
                if not isinstance(name, str):
                    raise ValueError('Malformed feature_pool_element')
                references.add(('feature', name))
            else:
                raise ValueError(f'Unsupported vanilla Jigsaw pool element type: {kind}')

        def visit_pool(identifier: str):
            if identifier == 'minecraft:empty':
                return
            if not identifier.startswith('minecraft:pillager_outpost/') or '..' in identifier:
                raise ValueError(f'Unknown/non-vanilla outpost Jigsaw pool: {identifier}')
            if identifier in pools:
                return
            pool_path = BASE + 'template_pool/' + identifier.split(':', 1)[1] + '.json'
            pool, digest = _read_json(jar, pool_path)
            if not isinstance(pool, dict):
                raise ValueError(f'Malformed Jigsaw pool {identifier}')
            pools[identifier] = digest
            fallback = pool.get('fallback')
            if not isinstance(fallback, str):
                raise ValueError(f'Pool lacks fallback: {identifier}')
            visit_pool(fallback)
            elems = pool.get('elements')
            if not isinstance(elems, list) or not 1 <= len(elems) <= 512:
                raise ValueError(f'Pool lacks weighted elements: {identifier}')
            for record in elems:
                if not isinstance(record, dict) or type(record.get('weight')) is not int or not 1 <= record['weight'] <= 150:
                    raise ValueError(f'Invalid weighted Jigsaw pool element: {identifier}')
                visit_element(record.get('element'))

        visit_pool(start_pool)
        digest = '\n'.join(f'{key}:{value}' for key, value in sorted({**pools, **templates}.items()))
        return {
            'version': version, 'start_pool': start_pool, 'size': size,
            'project_start_to_heightmap': structure.get('project_start_to_heightmap'),
            'template_pools_visited': len(pools), 'templates_visited': len(templates),
            'pool_elements': dict(sorted(operators.items())),
            'connector_dependencies': len(references),
            'sha256': {'structure_settings': struct_sha, 'pool_template_graph': hashlib.sha256(digest.encode('utf-8')).hexdigest()},
            'complete_jigsaw_simulation_proven': False,
            'status': 'pool_and_template_graph_verified_only',
            'limitations': 'Jigsaw RNG, connectors alignment, collision and successful world generation have not been simulated.',
        }


def run_contract(args) -> None:
    report = inspect_structure_contract(args.game_jar, args.version)
    if args.out:
        write_json_atomic(args.out, report)
    print(json.dumps(report, ensure_ascii=False, indent=2))


def add_command(commands) -> None:
    from .versions import SUPPORTED
    parser = commands.add_parser('jigsaw-contract', help='核對原版前哨站所有可達的 Jigsaw 池與模板（資料驗證，不等於生成模擬）')
    parser.add_argument('--version', required=True, choices=sorted(SUPPORTED))
    parser.add_argument('--game-jar', required=True, type=Path)
    parser.add_argument('--out', type=Path)
    parser.set_defaults(run=run_contract)
