"""File: geometry_audit.py
Modification: 2026-10-13 — differential vanilla Jigsaw footprint and seed-height audit.

Only compares original saved structure NBT with the independently derived
baseplate footprint. A successful audit never proves version-wide exact Y.
"""
from __future__ import annotations

import argparse
from collections import Counter
import csv
import json
from pathlib import Path
import os
import tempfile

from finder import (WorldChunks, confirmed_world, examine, load_candidates,
                    pool_locations, structures_start, write_csv)
from nbt import NBTError
from start_geometry import StartProjection, load_outpost_assets, projection
from tower_geometry import TowerBlueprint, TowerGeometryError, load_tower_blueprint
from versions import detect_world_version

ROTATION_NAMES = ('none', 'clockwise_90', 'clockwise_180', 'counterclockwise_90')
FIELDS = ('version', 'seed', 'chunk_x', 'chunk_z', 'status', 'geometry_status',
          'height_status', 'expected_rotation', 'actual_rotation',
          'sample_x', 'sample_z', 'expected_min_x', 'expected_min_z',
          'expected_max_x', 'expected_max_z', 'actual_bbox',
          'base_plate_y', 'watchtower_min_y', 'watchtower_max_y',
          'projected_base_plate_y', 'height_error',
          'tower_vertical_status', 'expected_tower_min_y', 'expected_tower_max_y', 'reason')


def expected_base_box(x: int, z: int, width: int, depth: int,
                      rotation: int) -> tuple[int, int, int, int]:
    """Replicate StructureTemplate.calculateBoundingBox, mirror NONE, pivot ORIGIN.

    Return inclusive world X/Z min and max after rotation. No noise needed.
    """
    if not (1 <= width <= 128 and 1 <= depth <= 128) or rotation not in range(4):
        raise ValueError('Invalid template dimensions or rotation')
    dx, dz = width - 1, depth - 1
    extents = ((0, dx, 0, dz), (-dz, 0, 0, dx), (-dx, 0, -dz, 0), (0, dz, -dx, 0))
    minx, maxx, minz, maxz = extents[rotation]
    return x + minx, z + minz, x + maxx, z + maxz


def find_base_piece(start: dict) -> dict | None:
    for piece in start.get('Children', []):
        if not isinstance(piece, dict) or piece.get('id') not in ('minecraft:jigsaw', 'jigsaw'):
            continue
        names = {name.split(':')[-1] for name in pool_locations(piece.get('pool_element', {}))}
        if 'pillager_outpost/base_plate' in names:
            return piece
    return None


def audit_piece(piece: dict, projected: StartProjection, chunk_x: int, chunk_z: int,
                size: tuple[int, int, int], estimated: dict | None = None) -> dict:
    """Compare the actual NBT placement to expected horizontal geometry and height.

    Expected Y is NOT computed by this function: it can only compare a clearly
    labeled external estimate against observed saved structure Y.
    """
    ex = expected_base_box(chunk_x * 16, chunk_z * 16, size[0], size[2], projected.rotation)
    bb = piece.get('BB')
    result = dict(expected_rotation=ROTATION_NAMES[projected.rotation],
                  actual_rotation=str(piece.get('rotation', '')).lower(),
                  sample_x=projected.sample_x, sample_z=projected.sample_z,
                  expected_min_x=ex[0], expected_min_z=ex[1],
                  expected_max_x=ex[2], expected_max_z=ex[3],
                  actual_bbox=str(bb), geometry_status='invalid_piece',
                  height_status='not_compared', projected_base_plate_y='',
                  height_error='', reason='')
    if not isinstance(bb, list) or len(bb) != 6 or any(type(v) is not int for v in bb):
        result['reason'] = 'Invalid baseplate BB'
        return result
    if result['actual_rotation'] not in ROTATION_NAMES:
        result['geometry_status'] = 'rotation_unknown'
        result['reason'] = 'Saved NBT does not contain a recognized rotation'
    elif result['actual_rotation'] != ROTATION_NAMES[projected.rotation]:
        result['geometry_status'] = 'rotation_mismatch'
        result['reason'] = 'Saved NBT rotation differs from expected seed rotation'
    elif (bb[0], bb[2], bb[3], bb[5]) != ex or bb[4] - bb[1] + 1 != size[1]:
        result['geometry_status'] = 'footprint_mismatch'
        result['reason'] = 'Saved NBT BB differs from rotated baseplate template'
    else:
        result['geometry_status'] = 'match'
    if estimated is not None:
        try:
            est_x, est_z = int(estimated['sample_x']), int(estimated['sample_z'])
            est_rot = int(estimated['rotation'])
            est_y = int(estimated['projected_base_plate_y'])
        except (KeyError, ValueError, TypeError) as exc:
            raise ValueError('Estimate must include integer sample_x, sample_z, rotation and projected_base_plate_y') from exc
        if (est_x, est_z, est_rot) != (projected.sample_x, projected.sample_z, projected.rotation):
            result['height_status'] = 'sample_mismatch'
        elif result['geometry_status'] != 'match':
            result['height_status'] = 'geometry_unverified'
        else:
            result['projected_base_plate_y'] = est_y
            result['height_error'] = est_y - bb[1]
            result['height_status'] = 'match' if est_y == bb[1] else 'model_error'
    return result


def audit_tower_relation(start: dict, base: dict, blueprint: TowerBlueprint) -> dict:
    """Check only the invariant *vertical* attachment to the primary tower.

    Derived from vanilla template jigsaw Y coordinates, not from a noise model.
    The X/Z connection, secondary overgrowth and external features are not
    reproduced by this check; a match is not a complete Jigsaw proof.
    """
    output = {'tower_vertical_status': 'missing', 'expected_tower_min_y': '',
              'expected_tower_max_y': ''}
    bb = base.get('BB')
    if (not isinstance(bb, list) or len(bb) != 6 or
            any(type(v) is not int for v in bb)):
        output['tower_vertical_status'] = 'invalid_base'
        return output
    expected_min = bb[1] + blueprint.tower_min_y_from_base
    expected_max = expected_min + blueprint.tower_height - 1
    output.update(expected_tower_min_y=expected_min, expected_tower_max_y=expected_max)
    found = []
    for piece in start.get('Children', []):
        if not isinstance(piece, dict) or piece.get('id') not in ('minecraft:jigsaw', 'jigsaw'):
            continue
        names = {str(x).split(':')[-1] for x in pool_locations(piece.get('pool_element', {}))}
        if 'pillager_outpost/watchtower' in names:
            found.append(piece)
    if len(found) > 1:
        output['tower_vertical_status'] = 'ambiguous'
        return output
    if len(found) == 1:
        tower_bb = found[0].get('BB')
        if (not isinstance(tower_bb, list) or len(tower_bb) != 6 or
                any(type(v) is not int for v in tower_bb)):
            output['tower_vertical_status'] = 'invalid_tower'
        elif (tower_bb[1], tower_bb[4]) == (expected_min, expected_max):
            output['tower_vertical_status'] = 'match'
        else:
            output['tower_vertical_status'] = 'mismatch'
    return output


def load_estimates(path: Path, seed: int, version: str) -> dict[tuple[int, int], dict]:
    out: dict[tuple[int, int], dict] = {}
    with path.open(encoding='utf-8-sig', newline='') as f:
        reader = csv.DictReader(f)
        required = {'version', 'seed', 'chunk_x', 'chunk_z', 'classification',
                    'sample_x', 'sample_z', 'rotation', 'projected_base_plate_y'}
        if not reader.fieldnames or not required <= set(reader.fieldnames):
            raise ValueError(f'Estimate CSV missing fields: {sorted(required - set(reader.fieldnames or []))}')
        for line, row in enumerate(reader, 2):
            try:
                if row['version'] != version or int(row['seed']) != seed:
                    raise ValueError('world version/seed differs from estimate')
                if row['classification'] != 'estimated_only':
                    raise ValueError('classification is not estimated_only')
                key = (int(row['chunk_x']), int(row['chunk_z']))
                if key in out:
                    raise ValueError(f'duplicate chunk {key}')
                # Reject wrong native inputs early; do not silently bless old chunk-center sampling.
                for field in ('sample_x', 'sample_z', 'rotation', 'projected_base_plate_y'):
                    int(row[field])
            except (ValueError, TypeError, KeyError) as exc:
                raise ValueError(f'Invalid estimate CSV line {line}: {exc}') from exc
            out[key] = row
    return out


def audit_world(world: Path, candidate_csv: Path, game_jar: Path,
                estimate_csv: Path | None = None) -> tuple[list[dict], dict]:
    """Read vanilla save without modification and return item-level evidence.

    Mismatched / incomplete chunks remain explicit in audit output. The report
    intentionally NEVER marks any version's terrain generator as proven exact.
    """
    meta, seed = confirmed_world(Path(world))
    version, dv = detect_world_version(meta)
    selection = load_candidates(Path(candidate_csv), seed, version)
    from game_archive import require_matching_game_version
    require_matching_game_version(Path(game_jar), version)
    assets = load_outpost_assets(Path(game_jar))
    estimates = load_estimates(Path(estimate_csv), seed, version) if estimate_csv else {}
    try:
        tower_blueprint = load_tower_blueprint(Path(game_jar))
    except (TowerGeometryError, ValueError) as exc:
        tower_blueprint = None
        tower_unavailable_reason = str(exc)
    else:
        tower_unavailable_reason = ''
    rows = []
    with WorldChunks(Path(world)) as source:
        for _seed, cx, cz in selection:
            p = projection(seed, cx, cz, assets.size)
            row = dict(version=version, seed=seed, chunk_x=cx, chunk_z=cz,
                       expected_rotation=ROTATION_NAMES[p.rotation],
                       sample_x=p.sample_x, sample_z=p.sample_z,
                       geometry_status='not_checked', height_status='not_compared',
                       height_error='', projected_base_plate_y='', reason='',
                       tower_vertical_status='not_checked',
                       expected_tower_min_y='', expected_tower_max_y='')
            try:
                chunk = source.get(cx, cz)
                examined = examine(chunk, seed, cx, cz, data_version=dv)
                row.update(examined)
                if not examined['status'].startswith('verified_'):
                    row['reason'] = examined['reason']
                else:
                    piece = find_base_piece(structures_start(chunk))
                    if piece is None:
                        row['geometry_status'] = 'baseplate_missing'
                    else:
                        row.update(audit_piece(piece, p, cx, cz, assets.size,
                                               estimates.get((cx, cz))))
                        if row['geometry_status'] == 'match' and tower_blueprint is not None:
                            row.update(audit_tower_relation(structures_start(chunk), piece, tower_blueprint))
                        elif tower_blueprint is None:
                            row['tower_vertical_status'] = 'template_unavailable'
            except (NBTError, OSError, ValueError, TypeError) as exc:
                row.update(status='invalid_region', geometry_status='not_checked', reason=str(exc))
            rows.append(row)
    counts = Counter(r['geometry_status'] for r in rows)
    height_errors = [r['height_error'] for r in rows if isinstance(r['height_error'], int)]
    report = dict(version=version, seed=seed, game_asset_sha256=assets.sha256,
                  checked=len(rows), geometry_match=counts['match'],
                  geometry_mismatch=sum(counts[x] for x in
                      ('rotation_mismatch', 'footprint_mismatch', 'rotation_unknown',
                       'invalid_piece', 'baseplate_missing')),
                  not_checked=counts['not_checked'], height_compared=len(height_errors),
                  exact_height_matches=sum(x == 0 for x in height_errors),
                  maximum_absolute_height_error=max(map(abs, height_errors), default=None),
                  tower_vertical_match=sum(r['tower_vertical_status'] == 'match' for r in rows),
                  tower_vertical_mismatch=sum(r['tower_vertical_status'] in
                      ('mismatch', 'ambiguous', 'invalid_tower', 'missing') for r in rows),
                  tower_template_unavailable=tower_unavailable_reason,
                  full_version_height_exact=False)
    return rows, report


def write_json_atomic(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = None
    try:
        with tempfile.NamedTemporaryFile('w', encoding='utf-8', dir=path.parent,
                                         prefix=f'.{path.name}.', suffix='.tmp',
                                         delete=False) as file:
            temp = Path(file.name)
            json.dump(value, file, ensure_ascii=False, indent=2)
            file.write('\n')
            file.flush()
            os.fsync(file.fileno())
        temp.replace(path)
    finally:
        if temp is not None:
            temp.unlink(missing_ok=True)


def run(args) -> None:
    rows, report = audit_world(args.world, args.candidates, args.game_jar, args.estimates)
    write_csv(args.out, rows, FIELDS)
    if args.summary:
        write_json_atomic(args.summary, report)
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))


def add_command(commands) -> None:
    p = commands.add_parser('geometry-audit', help='逐筆對照實際 NBT 的 Jigsaw 起始基板 X/Z 及近似高度誤差；不宣稱跨版 Y 精確')
    p.add_argument('--world', type=Path, required=True)
    p.add_argument('--candidates', type=Path, required=True)
    p.add_argument('--game-jar', type=Path, required=True, help='對應版的 Minecraft 遊戲資源 JAR')
    p.add_argument('--estimates', type=Path, help='選用含旋轉與投影 Y 的試驗性推算 CSV')
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--summary', type=Path, help='可選 JSON 統計報告')
    p.set_defaults(run=run)
