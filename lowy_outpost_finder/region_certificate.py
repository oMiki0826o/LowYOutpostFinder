"""File: region_certificate.py
Modification: 2026-10-13 — fail-closed, finite-area lowest-Y audit over saved chunks.

A complete saved-world audit is *not* independent seed-only worldgen. It proves
only the minimum among naturally generated starts in the specified finite
area, conditional on the world's provenance and completeness of origin chunks.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

from .cli import (FIELDS, CANDIDATE_FIELDS, WorldChunks, base_row, candidates, confirmed_world,
                    examine, structures_start, write_csv)
from .geometry_audit import (audit_piece, audit_tower_relation, find_base_piece,
                            write_json_atomic)
from .nbt import NBTError, region_filename
from .start_geometry import load_outpost_assets, projection
from .tower_geometry import load_tower_blueprint
from .versions import detect_world_version

AUDIT_FIELDS = (*FIELDS, 'geometry_status', 'tower_vertical_status')
COMPLETE_STATUSES = frozenset({'absent', 'verified_tower'})


def _decimal(value, name: str) -> int:
    if isinstance(value, bool) or (isinstance(value, str) and not value.lstrip('-').isdigit()):
        raise ValueError(f'Invalid {name} in region coverage')
    try:
        result = int(value)
    except (ValueError, TypeError, OverflowError) as exc:
        raise ValueError(f'Invalid {name} in region coverage') from exc
    if isinstance(value, float) and value != result:
        raise ValueError(f'Invalid {name} in region coverage')
    return result


def summarize_region(expected: list[dict], rows: list[dict], seed: int,
                     version: str, *, radius: int) -> dict:
    """Compute a certificate only if every *expected* origin is conclusively read.

    A report with any indeterminate result may show an OBSERVED minimum,
    but never a certified one. Any suspicious data fails closed.
    """
    if radius < 0 or radius > 30_000_000:
        raise ValueError('Invalid region radius')
    allowed = {(int(r['chunk_x']), int(r['chunk_z'])) for r in expected}
    if len(allowed) != len(expected):
        raise ValueError('Duplicate expected placement candidate')
    seen: set[tuple[int, int]] = set()
    statuses: Counter[str] = Counter()
    lowest = []
    unresolved = []
    for row in rows:
        if row.get('version') != version:
            raise ValueError('Wrong version in region coverage evidence')
        if _decimal(row.get('seed'), 'seed') != seed:
            raise ValueError('Wrong seed in region coverage evidence')
        cx = _decimal(row.get('chunk_x'), 'chunk_x')
        cz = _decimal(row.get('chunk_z'), 'chunk_z')
        key = (cx, cz)
        if key not in allowed:
            raise ValueError(f'Origin outside requested placement candidate region: {key}')
        if key in seen:
            raise ValueError(f'Duplicate origin in region coverage evidence: {key}')
        seen.add(key)
        if (_decimal(row.get('x'), 'x') != cx * 16 or
                _decimal(row.get('z'), 'z') != cz * 16):
            raise ValueError(f'Wrong world coordinate for origin {key}')
        status = row.get('status', '')
        if not isinstance(status, str) or not status:
            raise ValueError('Missing chunk status in region evidence')
        statuses[status] += 1
        if status == 'verified_tower':
            by = _decimal(row.get('base_plate_y'), 'base_plate_y')
            ty = _decimal(row.get('watchtower_min_y'), 'watchtower_min_y')
            tmax = _decimal(row.get('watchtower_max_y'), 'watchtower_max_y')
            if not (-64 <= by <= 320 and -64 <= ty <= tmax <= 320):
                raise ValueError('Saved tower bounding box is outside Overworld height range')
            if (row.get('geometry_status') != 'match' or
                    row.get('tower_vertical_status') != 'match'):
                unresolved.append(dict(chunk_x=cx, chunk_z=cz,
                                       reason='geometry_not_confirmed'))
            else:
                lowest.append((by, ty, cx, cz))
        elif status != 'absent':
            unresolved.append(dict(chunk_x=cx, chunk_z=cz, reason=status))
    missing = len(allowed - seen)
    all_read = missing == 0 and not unresolved
    lowest.sort()
    # Do not certify any minimum while even one origin remains unresolved.
    best = min(lowest, key=lambda t: (t[0], t[2], t[3])) if lowest else None
    best_tower = min(lowest, key=lambda t: (t[1], t[2], t[3])) if lowest else None
    status = ('finite_region_incomplete' if not all_read else
              'finite_region_complete' if lowest else
              'finite_region_complete_no_towers')
    return {
        'scope': 'axis_aligned_origin_chunk_square_centered_at_zero',
        'world_seed': seed, 'minecraft_version': version,
        'radius_blocks': radius,
        'expected_candidates': len(expected), 'checked_candidates': len(seen),
        'missing_candidates': missing, 'incomplete_count': missing + len(unresolved),
        'status_counts': dict(sorted(statuses.items())),
        'coverage_complete': all_read, 'status': status,
        'lowest_observed_base_plate_y': best[0] if best else None,
        'lowest_confirmed_base_plate_y': best[0] if all_read and best else None,
        'lowest_confirmed_watchtower_y': best_tower[1] if all_read and best_tower else None,
        'lowest_confirmed_base_plate_origin': (
            {'chunk_x': best[2], 'chunk_z': best[3]} if all_read and best else None),
        'lowest_confirmed_tower_origin': (
            {'chunk_x': best_tower[2], 'chunk_z': best_tower[3]} if all_read and best_tower else None),
        'unresolved': unresolved[:100], 'unresolved_truncated': len(unresolved) > 100,
        'independent_seed_only_exactness_proven': False,
        'global_world_minimum_proven': False,
        'limitations': ('This is a saved-world, finite-area audit. It does not predict '
                        'ungenerated terrain, prove source-world authenticity, or establish '
                        'the global lowest pillager spawning block. For certified results '
                        'use a quiescent, unmodified vanilla-generated world and the '
                        'matching original version asset JAR.'),
    }


def _hash_optional(path: Path) -> str | None:
    if not path.is_file():
        return None
    sha = hashlib.sha256()
    with path.open('rb') as fp:
        for chunk in iter(lambda: fp.read(1024 * 1024), b''):
            sha.update(chunk)
    return sha.hexdigest()


def _file_state(path: Path):
    try:
        st = path.stat()
    except FileNotFoundError:
        return None
    return (st.st_size, st.st_mtime_ns, st.st_ino)


def certify_world_region(world: Path, radius: int, output: Path,
                         audit_output: Path | None = None,
                         *, pending_output: Path | None = None, game_jar: Path | None = None,
                         max_candidates: int = 10000) -> dict:
    """Read ALL candidate origin chunks within a radius; reject silent truncation.

    Does not generate any chunk or modify the source world. Geometric
    certification of saved towers requires matching original JAR assets.
    """
    if not 1 <= max_candidates <= 100000:
        raise ValueError('--max-candidates must be 1..100000')
    world = Path(world).resolve()
    exports = [Path(output).resolve()]
    if audit_output is not None:
        exports.append(Path(audit_output).resolve())
    if pending_output is not None:
        exports.append(Path(pending_output).resolve())
    if len(set(exports)) != len(exports):
        raise ValueError('Each report, audit and pending output must be a distinct file')
    for path in exports:
        if (path in (world / 'level.dat', world / 'server.properties',
                     world / 'eula.txt') or
                path.is_relative_to(world / 'region')):
            raise ValueError('Refusing to overwrite Minecraft world data; choose a report path outside region/')
    data, seed = confirmed_world(world, 'auto')
    version, dv = detect_world_version(data)
    expected = []
    for row in candidates(seed, radius):
        expected.append(row)
        if len(expected) > max_candidates:
            raise ValueError(f'Scope exceeds --max-candidates={max_candidates}; '
                             'split the search instead of silently truncating results')
    # Bound the archive to a stable snapshot; a live server can rewrite .mca
    # while the reader is between two origin chunks. Stop, do not certify.
    related_files = {world / 'level.dat'}
    related_files.update(world / 'region' / region_filename(
        row['chunk_x'] // 32, row['chunk_z'] // 32) for row in expected)
    initial_state = {path: _file_state(path) for path in related_files}
    assets, blueprint = None, None
    if game_jar is not None:
        from .game_archive import require_matching_game_version
        game_jar = Path(game_jar).resolve()
        require_matching_game_version(game_jar, version)
        assets = load_outpost_assets(game_jar)
        blueprint = load_tower_blueprint(game_jar)
    rows = []
    with WorldChunks(world) as source:
        for row in expected:
            cx, cz = row['chunk_x'], row['chunk_z']
            chunk = None
            try:
                chunk = source.get(cx, cz)
                verified = examine(chunk, seed, cx, cz, data_version=dv)
            except (NBTError, OSError, TypeError, ValueError) as exc:
                verified = base_row(seed, cx, cz, status='invalid_region', reason=str(exc))
            verified['version'] = version
            verified.update(geometry_status='not_checked', tower_vertical_status='not_checked')
            if verified['status'] == 'absent':
                verified.update(geometry_status='not_applicable', tower_vertical_status='not_applicable')
            elif verified['status'] == 'verified_tower' and assets and blueprint:
                try:
                    start = structures_start(chunk)
                    base = find_base_piece(start)
                    if base is None:
                        raise ValueError('Saved tower has no base plate')
                    proj = projection(seed, cx, cz, assets.size)
                    geometry = audit_piece(base, proj, cx, cz, assets.size)
                    tower = audit_tower_relation(start, base, blueprint)
                    verified['geometry_status'] = geometry['geometry_status']
                    verified['tower_vertical_status'] = tower['tower_vertical_status']
                except (NBTError, TypeError, ValueError, KeyError) as exc:
                    verified['geometry_status'] = 'invalid_geometry'
                    verified['reason'] = str(exc)
            rows.append(verified)
    if any(_file_state(path) != state for path, state in initial_state.items()):
        raise RuntimeError('World files changed during the certificate scan; use an offline world copy')
    summary = summarize_region(expected, rows, seed, version, radius=radius)
    summary['source_level_dat_sha256'] = _hash_optional(world / 'level.dat')
    summary['game_jar_sha256'] = _hash_optional(game_jar) if game_jar else None
    summary['geometric_asset_verification'] = 'enabled' if assets else 'not_provided'
    # A disconnected read of a concurrently running server is not a snapshot.
    # Publish safely and instruct callers to use a quiescent world backup.
    if pending_output:
        # A new run may load ONLY missing/not-FULL origin chunks. Corrupt or
        # geometrically mismatched full chunks need investigation, not retries.
        incomplete_origins = {
            (row['chunk_x'], row['chunk_z']) for row in rows
            if row['status'] in ('not_generated', 'not_full', 'timeout')
        }
        pending = [dict(version=version, **row) for row in expected
                   if (row['chunk_x'], row['chunk_z']) in incomplete_origins]
        write_csv(Path(pending_output), pending, CANDIDATE_FIELDS)
    if audit_output:
        write_csv(Path(audit_output), rows, AUDIT_FIELDS)
    write_json_atomic(Path(output), summary)
    return summary


def run_region_certificate(args: argparse.Namespace):
    report = certify_world_region(args.world, args.radius, args.out, args.audit,
                                  pending_output=args.pending, game_jar=args.game_jar,
                                  max_candidates=args.max_candidates)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if args.require_complete and not report['coverage_complete']:
        raise ValueError('World coverage is incomplete; no bounded-region minimum has been certified')


def add_command(commands) -> None:
    p = commands.add_parser('region-certificate',
        help='掃描有限區域內全部候選起始區塊，證明已生成原版存檔範圍的最低塔樓 Y；非純種子演算法')
    p.add_argument('--world', type=Path, required=True)
    p.add_argument('--radius', type=int, required=True)
    p.add_argument('--game-jar', type=Path, help='同版遊戲 JAR；沒有它就不會將已找到的塔樓列為幾何已核對')
    p.add_argument('--max-candidates', type=int, default=10000)
    p.add_argument('--audit', type=Path, help='可選逐個候選的完整審核 CSV')
    p.add_argument('--pending', type=Path, help='匯出尚未 FULL 的候選 CSV，可交給 live 指令生成（不含已壞損的區塊）')
    p.add_argument('--require-complete', action='store_true', help='若有任何區塊未生成或幾何未證實，回傳非零狀態')
    p.add_argument('--out', type=Path, required=True)
    p.set_defaults(run=run_region_certificate)
