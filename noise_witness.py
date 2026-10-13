"""File: noise_witness.py
Modification: 2026-10-13 — strict pre-output sample gates; derive vanilla WG observations
and compare them to exploratory seed-model estimates without conflating them.

An observed base plate is a measurement of the original game's Jigsaw
projection at one position. This module does NOT implement seed-only noise.
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from finder import write_csv
from geometry_audit import audit_world, write_json_atomic

WITNESS_FIELDS = ('version', 'seed', 'chunk_x', 'chunk_z', 'sample_x',
                  'sample_z', 'rotation', 'world_surface_wg', 'base_plate_y',
                  'watchtower_min_y', 'watchtower_max_y', 'asset_sha256', 'evidence')
DIFFERENCE_FIELDS = ('version', 'seed', 'chunk_x', 'chunk_z', 'sample_x', 'sample_z',
                     'vanilla_base_plate_y', 'estimated_base_plate_y', 'base_plate_error')


def _integer(record: dict, field: str) -> int:
    try:
        value = record[field]
        if isinstance(value, bool) or isinstance(value, float) or (isinstance(value, str) and not value.lstrip('-').isdigit()):
            raise ValueError('not a signed decimal integer')
        return int(value)
    except (ValueError, KeyError, TypeError) as exc:
        raise ValueError(f'Height witness has an invalid {field}') from exc


def build_witnesses(rows: list[dict], version: str, seed: int,
                    asset_sha256: str) -> tuple[list[dict], dict]:
    """Infer Jigsaw WORLD_SURFACE_WG only when original NBT geometry matches.

    Proof for the inferred height: Jigsaw startHeight=absolute(0), rigid
    baseplate ground_level_delta=1, baseplate template minY=0, so its saved
    bounding-box minY equals original heightmap result minus one. A verified
    watchtower is also required to avoid treating a lone start as an outpost.
    """
    observed: list[dict] = []
    seen: set[tuple[int, int]] = set()
    for row in rows:
        if row.get('version') != version or _integer(row, 'seed') != seed:
            raise ValueError('World version or seed differs from height evidence')
        key = (_integer(row, 'chunk_x'), _integer(row, 'chunk_z'))
        if key in seen:
            raise ValueError(f'Duplicate chunk in source audit: {key}')
        seen.add(key)
        if (row.get('status') != 'verified_tower' or
                row.get('geometry_status') != 'match' or
                row.get('tower_vertical_status') != 'match'):
            continue
        base_y = _integer(row, 'base_plate_y')
        tower_min_y = _integer(row, 'watchtower_min_y')
        tower_max_y = _integer(row, 'watchtower_max_y')
        if not -64 <= base_y <= 320 or not -64 <= tower_min_y <= tower_max_y <= 320:
            raise ValueError('Height evidence outside Minecraft Overworld bounds')
        rot_name = row.get('expected_rotation')
        rotations = {'none': 0, 'clockwise_90': 1,
                     'clockwise_180': 2, 'counterclockwise_90': 3}
        if rot_name not in rotations:
            raise ValueError('Invalid original Jigsaw rotation evidence')
        observed.append(dict(version=version, seed=seed, chunk_x=key[0], chunk_z=key[1],
                             sample_x=_integer(row, 'sample_x'), sample_z=_integer(row, 'sample_z'),
                             rotation=rotations[rot_name], world_surface_wg=base_y + 1,
                             base_plate_y=base_y, watchtower_min_y=tower_min_y,
                             watchtower_max_y=tower_max_y, asset_sha256=asset_sha256,
                             evidence='derived_from_vanilla_saved_jigsaw'))
    summary = dict(version=version, seed=seed, inspected=len(rows),
                   accepted=len(observed), excluded=len(rows) - len(observed),
                   status=('sample_observations_only' if observed else 'no_verified_observations'),
                   global_exactness_proven=False,
                   note=('Observed original-world start height is only a reference for the sampled '
                         'location. This does not implement or validate an independent noise engine.'))
    return observed, summary


def read_witnesses(path: Path) -> list[dict]:
    with Path(path).open(encoding='utf-8-sig', newline='') as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames or not set(WITNESS_FIELDS) <= set(reader.fieldnames):
            raise ValueError('Height witnesses CSV lacks required fields')
        rows = list(reader)
    seen = set()
    for row in rows:
        if row['evidence'] != 'derived_from_vanilla_saved_jigsaw':
            raise ValueError('Unverified witness classification')
        key = (_integer(row, 'seed'), _integer(row, 'chunk_x'), _integer(row, 'chunk_z'))
        if key in seen:
            raise ValueError(f'Duplicate witness {key}')
        seen.add(key)
        if _integer(row, 'world_surface_wg') != _integer(row, 'base_plate_y') + 1:
            raise ValueError('Inconsistent height witness')
        for name in ('seed', 'chunk_x', 'chunk_z', 'sample_x', 'sample_z',
                     'rotation', 'world_surface_wg', 'base_plate_y',
                     'watchtower_min_y', 'watchtower_max_y'):
            row[name] = _integer(row, name)
        if row['rotation'] not in range(4):
            raise ValueError('Witness has invalid template rotation')
    return rows


def compare_witnesses(observed: list[dict], estimates_csv: Path) -> tuple[list[dict], dict]:
    from geometry_audit import load_estimates
    if not observed:
        return [], {'compared': 0, 'maximum_absolute_error': None, 'exact_matches': 0,
                    'global_exactness_proven': False, 'status': 'no_verified_observations'}
    seeds = {_integer(row, 'seed') for row in observed}
    versions = {row['version'] for row in observed}
    if len(seeds) != 1 or len(versions) != 1:
        raise ValueError('Compare a single seed and Minecraft version per report')
    seed, version = seeds.pop(), versions.pop()
    predicted = load_estimates(Path(estimates_csv), seed, version)
    compared = []
    for row in observed:
        cx, cz = _integer(row, 'chunk_x'), _integer(row, 'chunk_z')
        estimate = predicted.get((cx, cz))
        if estimate is None:
            continue
        if (_integer(estimate, 'sample_x') != _integer(row, 'sample_x') or
                _integer(estimate, 'sample_z') != _integer(row, 'sample_z') or
                _integer(estimate, 'rotation') != _integer(row, 'rotation')):
            raise ValueError(f'Mismatched sample coordinate or rotation at chunk {cx},{cz}')
        observed_y = _integer(row, 'base_plate_y')
        predicted_y = _integer(estimate, 'projected_base_plate_y')
        compared.append(dict(version=version, seed=seed, chunk_x=cx, chunk_z=cz,
                             sample_x=_integer(row, 'sample_x'), sample_z=_integer(row, 'sample_z'),
                             vanilla_base_plate_y=observed_y,
                             estimated_base_plate_y=predicted_y,
                             base_plate_error=predicted_y - observed_y))
    errors = [r['base_plate_error'] for r in compared]
    result = dict(compared=len(errors), missing_estimates=len(observed) - len(errors),
                  exact_matches=sum(value == 0 for value in errors),
                  maximum_absolute_error=max(map(abs, errors), default=None),
                  mean_absolute_error=(sum(map(abs, errors)) / len(errors) if errors else None),
                  global_exactness_proven=False,
                  status='sample_comparison_only' if errors else 'no_comparable_estimates')
    return compared, result


def run_witnesses(args: argparse.Namespace) -> None:
    rows, audit = audit_world(args.world, args.candidates, args.game_jar)
    verified, report = build_witnesses(rows, audit['version'], audit['seed'],
                                        audit['game_asset_sha256'])
    if args.require_samples and not verified:
        raise ValueError('No verified vanilla tower samples; cannot infer WORLD_SURFACE_WG')
    write_csv(args.out, verified, WITNESS_FIELDS)
    if args.summary:
        write_json_atomic(args.summary, report)
    print(json.dumps(report, ensure_ascii=False))


def run_compare(args: argparse.Namespace) -> None:
    witnessed = read_witnesses(args.witnesses)
    rows, summary = compare_witnesses(witnessed, args.estimates)
    if args.require_samples and not rows:
        raise ValueError('No comparable vanilla samples')
    write_csv(args.out, rows, DIFFERENCE_FIELDS)
    if args.summary:
        write_json_atomic(args.summary, summary)
    print(json.dumps(summary, ensure_ascii=False))


def add_command(commands) -> None:
    witness = commands.add_parser('height-witness', help='從已生成原版存檔的正確 Jigsaw 起始幾何推回局部高度圖取樣值')
    witness.add_argument('--world', type=Path, required=True)
    witness.add_argument('--candidates', type=Path, required=True)
    witness.add_argument('--game-jar', type=Path, required=True)
    witness.add_argument('--out', type=Path, required=True)
    witness.add_argument('--summary', type=Path)
    witness.add_argument('--require-samples', action='store_true')
    witness.set_defaults(run=run_witnesses)
    compare = commands.add_parser('compare-witness', help='把原版高度樣本與試驗性 C 近似結果對拍（不代表全域精確）')
    compare.add_argument('--witnesses', type=Path, required=True)
    compare.add_argument('--estimates', type=Path, required=True)
    compare.add_argument('--out', type=Path, required=True)
    compare.add_argument('--summary', type=Path)
    compare.add_argument('--require-samples', action='store_true')
    compare.set_defaults(run=run_compare)
