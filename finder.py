"""File: finder.py
Modification: 2026-10-13 — version-locked placement scanning plus asset validation and vanilla geometry audit.

No inferred candidate may be represented as a confirmed Minecraft structure.
"""
from __future__ import annotations

import argparse
from collections import Counter
import csv
from dataclasses import dataclass
from pathlib import Path
import os
import subprocess
import sys
from typing import Iterator
import tempfile
import heapq
from types import SimpleNamespace

from nbt import NBTError, REGION_NAME, Region, load_level, region_filename
from versions import check_version, detect_world_version, SUPPORTED

MASK48 = (1 << 48) - 1
MASK64 = (1 << 64) - 1
MAX_CANDIDATE_REGIONS = 5_000_000
OUTPOST = (32, 8, 165745296)
VILLAGE = (34, 8, 10387312)
FIELDS = ('version', 'seed', 'chunk_x', 'chunk_z', 'x', 'z', 'status', 'base_plate_y',
          'watchtower_min_y', 'watchtower_max_y', 'piece_count',
          'structure_min_y', 'structure_max_y', 'structure_center_y',
          'distance_sq', 'data_version', 'reason')
CANDIDATE_FIELDS = ('version', 'seed', 'chunk_x', 'chunk_z', 'x', 'z', 'classification')


class JavaRandom:
    """Reference-compatible java.util.Random 48-bit LCG (1.21.8 random spread)."""
    def __init__(self, seed: int):
        self.value = (seed ^ 0x5DEECE66D) & MASK48

    def bits(self, count: int) -> int:
        self.value = (self.value * 0x5DEECE66D + 0xB) & MASK48
        return self.value >> (48 - count)

    def bounded(self, bound: int) -> int:
        if not 0 < bound <= 0x7fffffff:
            raise ValueError('invalid Random bound')
        if (bound & (bound - 1)) == 0:
            return (bound * self.bits(31)) >> 31
        while True:
            bits = self.bits(31)
            val = bits % bound
            # Java int32 overflow semantics for rejection.
            if bits - val + (bound - 1) < (1 << 31):
                return val


def to_int32(number: int) -> int:
    number &= 0xffffffff
    return number if number < (1 << 31) else number - (1 << 32)


def region_position(seed: int, rx: int, rz: int, placement: tuple[int, int, int]) -> tuple[int, int]:
    spacing, separation, salt = placement
    rng = JavaRandom(seed + rx * 341873128712 + rz * 132897987541 + salt)
    width = spacing - separation
    return rx * spacing + rng.bounded(width), rz * spacing + rng.bounded(width)


def pass_legacy_frequency(seed: int, cx: int, cz: int) -> bool:
    x, z = to_int32(cx >> 4), to_int32(cz >> 4)
    mix = to_int32(x ^ to_int32(z << 4))
    rng = JavaRandom((seed ^ (mix & MASK64)) & MASK64)
    rng.bits(32)  # one native nextInt, signedness irrelevant
    return rng.bounded(5) == 0


def pass_village_exclusion(seed: int, cx: int, cz: int) -> bool:
    for rz in range((cz - 10) // 34, (cz + 10) // 34 + 1):
        for rx in range((cx - 10) // 34, (cx + 10) // 34 + 1):
            vx, vz = region_position(seed, rx, rz, VILLAGE)
            if abs(vx - cx) <= 10 and abs(vz - cz) <= 10:
                return False
    return True


def candidates(seed: int, radius: int) -> Iterator[dict]:
    if radius < 0 or radius > 30_000_000:
        raise ValueError('--radius must be in 0..30000000')
    rlo, rhi = -radius // 512, radius // 512
    regions = (rhi - rlo + 1) ** 2
    if regions > MAX_CANDIDATE_REGIONS:
        raise ValueError(f'Search covers {regions:,} regions (maximum {MAX_CANDIDATE_REGIONS:,}); '
                         'reduce --radius or split the area into smaller searches')
    for rz in range(rlo, rhi + 1):
        for rx in range(rlo, rhi + 1):
            cx, cz = region_position(seed, rx, rz, OUTPOST)
            x, z = cx * 16, cz * 16
            if not -radius <= x <= radius or not -radius <= z <= radius:
                continue
            if pass_legacy_frequency(seed, cx, cz) and pass_village_exclusion(seed, cx, cz):
                yield dict(seed=seed, chunk_x=cx, chunk_z=cz, x=x, z=z,
                           classification='placement_candidate')


def is_candidate_start(seed: int, cx: int, cz: int) -> bool:
    """Require a complete vanilla placement candidate before generating via RCON."""
    rx, rz = cx // OUTPOST[0], cz // OUTPOST[0]
    return (region_position(seed, rx, rz, OUTPOST) == (cx, cz)
            and pass_legacy_frequency(seed, cx, cz)
            and pass_village_exclusion(seed, cx, cz))


def signed_seed(value: str) -> int:
    try:
        seed = int(value, 10)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f'invalid numeric seed: {value}') from exc
    if not -(1 << 63) <= seed < (1 << 63):
        raise argparse.ArgumentTypeError('seed must be in signed Java long range')
    return seed


def confirmed_world(world: Path, version: str = 'auto') -> tuple[dict, int]:
    if not (world / 'level.dat').is_file() or not (world / 'region').is_dir():
        raise ValueError(f'Not a Minecraft Java Overworld save: {world}')
    data = load_level(world)
    detected, data_version = detect_world_version(data, version)
    seed = data.get('WorldGenSettings', {}).get('seed')
    if not isinstance(seed, int):
        raise ValueError('Cannot read WorldGenSettings.seed from world; cannot verify candidates')
    return data, seed


def structures_start(chunk: dict) -> dict | None:
    starts = chunk.get('structures', {}).get('starts', {})
    if not isinstance(starts, dict):
        raise NBTError('Invalid chunk structures.starts')
    start = starts.get('minecraft:pillager_outpost', starts.get('pillager_outpost'))
    if start is None or start.get('id') == 'INVALID':
        return None
    if start.get('id') != 'minecraft:pillager_outpost':
        raise NBTError('Outpost structure start has unexpected id')
    return start


def pool_locations(value) -> set[str]:
    locations = set()
    if isinstance(value, dict):
        if isinstance(value.get('location'), str):
            locations.add(value['location'])
        for child in value.values():
            if isinstance(child, (dict, list)):
                locations.update(pool_locations(child))
    elif isinstance(value, list):
        for child in value:
            locations.update(pool_locations(child))
    return locations


def inspect_start(start: dict, cx: int, cz: int) -> tuple[dict, str]:
    if start.get('ChunkX') != cx or start.get('ChunkZ') != cz:
        raise NBTError('Structure start chunk coordinates mismatch')
    children = start.get('Children')
    if not isinstance(children, list) or not children:
        raise NBTError('Outpost start contains no pieces')
    base, tower = None, None
    for child in children:
        if not isinstance(child, dict):
            raise NBTError('Invalid structure child')
        bb = child.get('BB')
        if not isinstance(bb, list) or len(bb) != 6 or any(not isinstance(i, int) for i in bb):
            raise NBTError('Invalid structure piece bounding box')
        if not (bb[0] <= bb[3] and bb[1] <= bb[4] and bb[2] <= bb[5]):
            raise NBTError('Backwards structure piece bounding box')
        if child.get('id') not in ('minecraft:jigsaw', 'jigsaw'):
            continue
        names = {str(s).split(':')[-1] for s in pool_locations(child.get('pool_element', {}))}
        if 'pillager_outpost/base_plate' in names:
            base = bb
        if any(name in names for name in ('pillager_outpost/watchtower', 'pillager_outpost/watchtower_overgrown')):
            tower = bb
    structure_boxes = [child['BB'] for child in children if isinstance(child, dict)
                       and isinstance(child.get('BB'), list) and len(child['BB']) == 6]
    structure_min_y = min(bb[1] for bb in structure_boxes) if structure_boxes else ''
    structure_max_y = max(bb[4] for bb in structure_boxes) if structure_boxes else ''
    structure_center_y = ((structure_min_y + structure_max_y) / 2
                          if structure_boxes else '')
    result = {
        'base_plate_y': base[1] if base else '',
        'watchtower_min_y': tower[1] if tower else '',
        'watchtower_max_y': tower[4] if tower else '',
        'piece_count': len(children),
        'structure_min_y': structure_min_y,
        'structure_max_y': structure_max_y,
        'structure_center_y': structure_center_y,
    }
    if tower is not None and base is not None:
        return result, 'verified_tower'
    if base is not None:
        return result, 'verified_start_only'
    return result, 'verified_structure_only'


def base_row(seed: int, cx: int, cz: int, status='unverified', reason='') -> dict:
    return {'seed': seed, 'chunk_x': cx, 'chunk_z': cz, 'x': cx * 16,
            'z': cz * 16, 'status': status, 'base_plate_y': '',
            'watchtower_min_y': '', 'watchtower_max_y': '',
            'piece_count': '', 'structure_min_y': '', 'structure_max_y': '',
            'structure_center_y': '', 'distance_sq': cx * cx * 256 + cz * cz * 256,
            'data_version': '', 'reason': reason}


def examine(chunk: dict | None, seed: int, cx: int, cz: int, *, data_version: int = 4440) -> dict:
    row = base_row(seed, cx, cz)
    if chunk is None:
        row.update(status='not_generated', reason='Missing origin chunk')
        return row
    version = chunk.get('DataVersion')
    row['data_version'] = version
    if version != data_version:
        row.update(status='version_mismatch', reason=f'Chunk DataVersion {version} differs from world {data_version} (mixed-version chunk)')
        return row
    # Only a completed FULL chunk proves actual world blocks were generated.
    if chunk.get('Status') not in ('minecraft:full', 'full'):
        row.update(status='not_full', reason=f'Chunk status {chunk.get("Status")!r}')
        return row
    # A region index is not sufficient evidence if the embedded chunk coordinates
    # disagree. Reject mismatched chunks rather than reporting fabricated positions.
    if ('xPos' in chunk and chunk['xPos'] != cx) or ('zPos' in chunk and chunk['zPos'] != cz):
        row.update(status='invalid_nbt', reason='Stored chunk coordinates differ from region index')
        return row
    try:
        start = structures_start(chunk)
        if start is None:
            row.update(status='absent', reason='FULL origin chunk has no valid pillager_outpost start')
        else:
            piece_data, status = inspect_start(start, cx, cz)
            row.update(**piece_data, status=status)
    except (TypeError, AttributeError, NBTError) as exc:
        row.update(status='invalid_nbt', reason=str(exc))
    return row


class WorldChunks:
    """Read-only index of region files; cache only one open region handle."""
    def __init__(self, world: Path):
        self.root = world / 'region'
        self.current_key = None
        self.region: Region | None = None

    def close(self):
        if self.region is not None:
            self.region.close()
        self.region, self.current_key = None, None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()

    def get(self, cx: int, cz: int):
        key = (cx // 32, cz // 32)
        if self.current_key != key:
            self.close()
            path = self.root / region_filename(*key)
            self.current_key = key
            if path.is_file():
                self.region = Region(path)
        return self.region.read_chunk(cx, cz) if self.region else None


def load_candidates(path: Path, expected_seed: int | None = None, expected_version: str | None = None) -> list[tuple[int, int, int]]:
    output = []
    seen = set()
    with path.open(encoding='utf-8-sig', newline='') as fp:
        for idx, record in enumerate(csv.DictReader(fp), start=2):
            try:
                seed = signed_seed(record['seed'])
                cx, cz = int(record['chunk_x']), int(record['chunk_z'])
                if not -(1 << 26) <= cx <= (1 << 26) or not -(1 << 26) <= cz <= (1 << 26):
                    raise ValueError('out of bounds')
                if 'x' in record and int(record['x']) != cx * 16:
                    raise ValueError('x does not match chunk_x * 16')
                if 'z' in record and int(record['z']) != cz * 16:
                    raise ValueError('z does not match chunk_z * 16')
            except (ValueError, KeyError, argparse.ArgumentTypeError) as exc:
                raise ValueError(f'Invalid candidate CSV at line {idx}: {exc}') from exc
            if expected_seed is not None and seed != expected_seed:
                raise ValueError(f'Seed mismatch in CSV line {idx}: got {seed}, expected {expected_seed}')
            if expected_version:
                if not record.get('version'):
                    raise ValueError(f'Version missing in CSV line {idx}; regenerate candidate CSV for {expected_version}')
                if record['version'] != expected_version:
                    raise ValueError(f'Version mismatch in CSV line {idx}: {record["version"]} != {expected_version}')
            key = (seed, cx, cz)
            if key not in seen:
                output.append(key)
                seen.add(key)
    return output


def write_csv(path: Path | None, rows, fields) -> None:
    """Write CSV atomically: a cancelled or failed search never publishes partial output."""
    if path is None:
        writer = csv.DictWriter(sys.stdout, fieldnames=fields, extrasaction='ignore', lineterminator='\n')
        writer.writeheader()
        writer.writerows(rows)
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile('w', encoding='utf-8', newline='',
                                         dir=path.parent, prefix=f'.{path.name}.',
                                         suffix='.tmp', delete=False) as handle:
            temporary = Path(handle.name)
            writer = csv.DictWriter(handle, fieldnames=fields, extrasaction='ignore',
                                    lineterminator='\n')
            writer.writeheader()
            writer.writerows(rows)
            handle.flush()
            os.fsync(handle.fileno())
        temporary.replace(path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def run_candidates(args):
    check_version(getattr(args, 'version', '1.21.8'))
    if getattr(args, "game_jar", None):
        from placement_assets import validate_placement_assets
        from game_archive import require_matching_game_version
        require_matching_game_version(args.game_jar, args.version)
        validate_placement_assets(args.game_jar)
    write_csv(args.out, (dict(version=args.version, **row) for row in candidates(args.seed, args.radius)), CANDIDATE_FIELDS)


def run_verify(args):
    world = args.world.resolve()
    _info, seed = confirmed_world(world, getattr(args, 'version', 'auto'))
    data_version = _info['DataVersion']
    version_name, _ = detect_world_version(_info)
    selection = load_candidates(args.candidates, seed, version_name)
    rows = []
    with WorldChunks(world) as w:
        for _, cx, cz in sorted(selection, key=lambda t: (t[1] // 32, t[2] // 32, t[1], t[2])):
            try:
                rows.append(dict(version=version_name, **examine(w.get(cx, cz), seed, cx, cz, data_version=data_version)))
            except (NBTError, OSError) as exc:
                rows.append(dict(version=version_name, **base_row(seed, cx, cz, status='invalid_region', reason=str(exc))))
    rows.sort(key=lambda r: (r['status'] not in ('verified_tower', 'verified_start_only', 'verified_structure_only'),
                             int(r['base_plate_y']) if r['base_plate_y'] != '' else 10_000,
                             int(r['chunk_x']), int(r['chunk_z'])))
    write_csv(args.out, rows, FIELDS)
    print('status totals:', dict(Counter(row['status'] for row in rows)), file=sys.stderr)


def run_world(args):
    world = args.world.resolve()
    _info, seed = confirmed_world(world, getattr(args, 'version', 'auto'))
    data_version = _info['DataVersion']
    version_name, _ = detect_world_version(_info)
    rows = []
    checked = 0
    errors = []
    for filename in sorted((world / 'region').iterdir()):
        match = REGION_NAME.fullmatch(filename.name)
        if not match:
            continue
        rx, rz = int(match[1]), int(match[2])
        if args.radius is not None:
            if abs(rx * 512) > args.radius + 512 or abs(rz * 512) > args.radius + 512:
                continue
        try:
            with Region(filename) as region:
                for idx in range(1024):
                    if region.header[idx * 4: idx * 4 + 4] == b'\x00\x00\x00\x00':
                        continue
                    cx, cz = rx * 32 + (idx % 32), rz * 32 + (idx // 32)
                    if args.radius is not None and (abs(cx * 16) > args.radius or abs(cz * 16) > args.radius):
                        continue
                    checked += 1
                    try:
                        chunk = region.read_chunk(cx, cz)
                        row = examine(chunk, seed, cx, cz, data_version=data_version)
                    except (NBTError, OSError) as exc:
                        errors.append(f'chunk {cx},{cz}: {exc}')
                        print(f'[WARN] unreadable chunk {cx},{cz}: {exc}', file=sys.stderr)
                        continue
                    if row['status'] in ('version_mismatch', 'invalid_nbt'):
                        errors.append(f'chunk {cx},{cz}: {row["reason"] or row["status"]}')
                    if row['status'].startswith('verified_') and (args.max_y is None or
                            (row['base_plate_y'] != '' and int(row['base_plate_y']) <= args.max_y)):
                        rows.append(dict(version=version_name, **row))
        except (NBTError, OSError) as exc:
            errors.append(f'region {filename.name}: {exc}')
            print(f'[WARN] unreadable region {filename}: {exc}', file=sys.stderr)
    if errors:
        raise RuntimeError(f'World scan incomplete: {len(errors)} unreadable regions/chunks; '
                           f'first error: {errors[0]}. No results were written.')
    rows.sort(key=lambda row: (int(row['base_plate_y']) if row['base_plate_y'] != '' else 10_000,
                               int(row['chunk_x']), int(row['chunk_z'])))
    write_csv(args.out, rows, FIELDS)
    print(f'FULL chunks scanned among {checked} stored chunks; confirmed starts: {len(rows)}', file=sys.stderr)


def run_commands(args):
    selection = load_candidates(args.candidates)
    if args.max_chunks < 1 or args.max_chunks > 256:
        raise ValueError('--max-chunks must be between 1 and 256')
    subset = selection[:args.max_chunks]
    if not subset:
        raise ValueError('No candidates to generate')
    if len({seed for seed, _, _ in subset}) != 1:
        raise ValueError('One command batch can contain only one world seed')
    out = args.out or Path('forceload_commands.txt')
    out.parent.mkdir(parents=True, exist_ok=True)
    lines = ['# Run from vanilla server console (omit leading /), not via a function file.',
             '# Ensure level.dat seed matches candidate CSV; make a backup first.',
             '# Wait for all selected chunks to load before save-all flush.',
             '# DO NOT remove forceload entries that were previously registered by others.',
             '# Each command below loads exactly one origin chunk; use the matching Java version.']
    lines += [f'forceload add {cx * 16} {cz * 16}' for _, cx, cz in subset]
    lines += ['# After chunks become full:', 'save-all flush',
              '# After reading saved world, optionally release only newly added entries:']
    lines += [f'# forceload remove {cx * 16} {cz * 16}' for _, cx, cz in subset]
    out.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print(f'Wrote {len(subset)} /forceload commands to {out}')


def run_estimate(args):
    if check_version(getattr(args, 'version', '1.21.8')) != '1.21.8':
        raise ValueError('Optional terrain approximation is not version-verified outside 1.21.8')
    if getattr(args, 'game_jar', None):
        from game_archive import require_matching_game_version
        require_matching_game_version(args.game_jar, args.version)
    root = Path(__file__).resolve().parent
    binary = root / 'bin' / 'lowyoutpost'
    if not binary.is_file():
        if not args.core_archive:
            raise ValueError('Build first: sh build.sh /path/LowYSwampHut-2.0.1.tar.gz ; '
                             'or specify --core-archive to compile the optional C approximation')
        subprocess.run(['sh', str(root / 'build.sh'), str(args.core_archive)], check=True)
    cmd = [str(binary), '--seed', str(args.seed), '--radius', str(args.radius),
           '--max-y', str(args.max_y), '--top', str(args.top)]
    if getattr(args, 'game_jar', None):
        from start_geometry import load_outpost_assets
        template = load_outpost_assets(args.game_jar)
        cmd += ['--template-width', str(template.size[0]),
                '--template-depth', str(template.size[2])]
    if not args.approx_biome:
        cmd.append('--skip-biome')
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        cmd += ['--csv', str(args.out)]
    subprocess.run(cmd, check=True)


def run_search_live(args):
    """One-command candidate search -> vanilla generation -> confirmed low-Y only."""
    from live import run_live
    _data, seed = confirmed_world(args.world, getattr(args, 'version', 'auto'))
    world_ver, _ = detect_world_version(_data)
    if args.priority == 'terrain' and world_ver != '1.21.8':
        raise ValueError('Terrain priority is not validated for this version; choose near-origin')
    if not 1 <= args.limit <= 256:
        raise ValueError('--limit must be between 1 and 256 for live generation')
    with tempfile.TemporaryDirectory(prefix='lowyoutpost-') as td:
        candidate_path = Path(td) / 'candidates.csv'
        if args.priority == 'terrain':
            estimated_path = Path(td) / 'terrain-approximation.csv'
            if not 1 <= args.limit <= 100000:
                raise ValueError('Terrain prediction --limit must be in 1..100000')
            native = Path(__file__).resolve().parent / 'bin' / 'lowyoutpost'
            if not native.is_file():
                if not args.core_archive:
                    raise ValueError('Native terrain priority needs --core-archive or a built C scanner')
                subprocess.run(['sh', str(Path(__file__).resolve().parent / 'build.sh'),
                                str(args.core_archive)], check=True)
            # Disable unvalidated biome gating; do not use an estimated max-Y cutoff.
            cmd = [str(native), '--seed', str(seed), '--radius', str(args.radius),
                   '--max-y', '320', '--skip-biome', '--top', str(args.limit),
                   '--csv', str(estimated_path)]
            if getattr(args, 'game_jar', None):
                from game_archive import require_matching_game_version
                require_matching_game_version(args.game_jar, world_ver)
                from start_geometry import load_outpost_assets
                meta = load_outpost_assets(args.game_jar)
                cmd.extend(['--template-width', str(meta.size[0]),
                            '--template-depth', str(meta.size[2])])
            subprocess.run(cmd, check=True)
            # The legacy native core produces an estimates CSV (without a version).
            # Normalize only the coordinates into an explicit version-bound placement CSV.
            with estimated_path.open(encoding='utf-8', newline='') as handle:
                estimates = list(csv.DictReader(handle))
            verified_rows = []
            for row in estimates:
                cx, cz = int(row['chunk_x']), int(row['chunk_z'])
                if int(row['seed']) != seed or not is_candidate_start(seed, cx, cz):
                    raise ValueError('Native terrain ranking returned a non-placement candidate')
                verified_rows.append({'version': world_ver, 'seed': seed,
                        'chunk_x': cx, 'chunk_z': cz, 'x': cx * 16, 'z': cz * 16,
                        'classification': 'placement_candidate'})
            write_csv(candidate_path, verified_rows, CANDIDATE_FIELDS)
        else:
            closest = heapq.nsmallest(args.limit, candidates(seed, args.radius),
                                     key=lambda r: (r['x'] ** 2 + r['z'] ** 2,
                                                    r['chunk_x'], r['chunk_z']))
            write_csv(candidate_path, (dict(version=world_ver, **row) for row in closest), CANDIDATE_FIELDS)
        live_args = SimpleNamespace(**vars(args))
        live_args.candidates = candidate_path
        live_args.out = args.audit
        # CLI commands define -37 explicitly. Programmatic callers that predate
        # this option retain their previous unfiltered behavior.
        live_args.stop_center_y_below = getattr(args, 'center_y_below', None)
        checked = run_live(live_args)
    # Guarantee that the public "hits" file contains no estimates or absent starts.
    center_limit = getattr(args, 'center_y_below', None)
    confirmed = [dict(r, version=world_ver) for r in checked if r['status'] == 'verified_tower'
                 and (center_limit is None or
                      (r['structure_center_y'] != '' and
                       float(r['structure_center_y']) < center_limit))
                 and (args.max_y is None or int(r['base_plate_y']) <= args.max_y)]
    confirmed.sort(key=lambda r: (r['distance_sq'], int(r['chunk_x']), int(r['chunk_z'])))
    write_csv(args.out, confirmed, FIELDS)
    print(f'vanilla-verified towers: {len(confirmed)} / {len(checked)} generated candidates'
          + (f' (structure_center_y < {getattr(args, "center_y_below", None)})'
             if getattr(args, 'center_y_below', None) is not None else '')
          + (f' (base_plate_y <= {args.max_y})' if args.max_y is not None else ''),
          file=sys.stderr)



def run_tower_project(args):
    """Resolve invariant vanilla rigid tower Y from a supplied exact WG sample.

    The caller must obtain WORLD_SURFACE_WG from a version-matched generator;
    reading the *post-carver* existing-world surface is not equivalent.
    """
    import json
    from start_geometry import projection
    from tower_geometry import load_tower_blueprint, predict_vertical
    from geometry_audit import write_json_atomic

    check_version(args.version)
    if not is_candidate_start(args.seed, args.chunk_x, args.chunk_z):
        raise ValueError('Not an outpost placement candidate for this seed')
    from game_archive import require_matching_game_version
    require_matching_game_version(args.game_jar, args.version)
    blueprint = load_tower_blueprint(args.game_jar)
    position = projection(args.seed, args.chunk_x, args.chunk_z, blueprint.base_size)
    base_y, tower_y, tower_max = predict_vertical(blueprint, args.world_surface_wg)
    result = {
        'version': args.version, 'seed': args.seed,
        'chunk_x': args.chunk_x, 'chunk_z': args.chunk_z,
        'sample_x': position.sample_x, 'sample_z': position.sample_z,
        'rotation': position.rotation,
        'world_surface_wg': args.world_surface_wg,
        'base_min_y': base_y, 'tower_min_y': tower_y, 'tower_max_y': tower_max,
        'tower_y_offset': blueprint.tower_min_y_from_base,
        'base_template_sha256': blueprint.base_sha256,
        'tower_template_sha256': blueprint.tower_sha256,
        'vanilla_generated': False,
        'classification': 'conditional_on_external_worldgen_height',
        'warning': 'WORLD_SURFACE_WG is an externally supplied value, not computed or verified by this command. '
                   'Biome success, complete Jigsaw placement and full vanilla generation remain unverified.',
    }
    if args.out:
        write_json_atomic(args.out, result)
    else:
        print(json.dumps(result, ensure_ascii=False, indent=2))


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description='MC Java 1.21–26.3 低 Y 前哨站：候選掃描、已生成存檔核驗')
    commands = parser.add_subparsers(dest='command', required=True)
    a = commands.add_parser('candidates', help='精確演算法求結構嘗試座標（不是確認生成）')
    a.add_argument('--version', choices=sorted(SUPPORTED), default='1.21.8')
    a.add_argument('--seed', type=signed_seed, required=True)
    a.add_argument('--game-jar', type=Path, help='驗證對應遊戲資源 JAR 的結構放置參數與內建算法相符')
    a.add_argument('--radius', type=int, default=8192, help='以世界原點為中心，方塊 X/Z 半徑')
    a.add_argument('--out', type=Path)
    a.set_defaults(run=run_candidates)
    a = commands.add_parser('verify', help='對指定候選逐一讀取已完成生成的原版存檔')
    a.add_argument('--version', choices=['auto', *sorted(SUPPORTED)], default='auto')
    a.add_argument('--world', type=Path, required=True)
    a.add_argument('--candidates', type=Path, required=True)
    a.add_argument('--out', type=Path)
    a.set_defaults(run=run_verify)
    a = commands.add_parser('world', help='從現有世界讀取所有已生成的前哨站及結構 Y')
    a.add_argument('--version', choices=['auto', *sorted(SUPPORTED)], default='auto')
    a.add_argument('--world', type=Path, required=True)
    a.add_argument('--radius', type=int)
    a.add_argument('--max-y', type=int)
    a.add_argument('--out', type=Path)
    a.set_defaults(run=run_world)
    a = commands.add_parser('commands', help='產生 vanilla 伺服器的候選區塊載入命令')
    a.add_argument('--candidates', type=Path, required=True)
    a.add_argument('--max-chunks', type=int, default=64)
    a.add_argument('--out', type=Path)
    a.set_defaults(run=run_commands)
    a = commands.add_parser('estimate', help='可選 1.21.8 專用 C 地形預測（不表示已驗證）')
    a.add_argument('--version', choices=sorted(SUPPORTED), default='1.21.8')
    a.add_argument('--seed', type=signed_seed, required=True)
    a.add_argument('--radius', type=int, default=16384)
    a.add_argument('--max-y', type=int, default=64)
    a.add_argument('--top', type=int, default=50)
    a.add_argument('--approx-biome', action='store_true', help='啟用未經 1.21.8 完整對拍的生態域預篩（可能漏掉真實結構）')
    a.add_argument('--core-archive', type=Path)
    a.add_argument('--game-jar', type=Path, help='同版遊戲 JAR（提取基板尺寸，改用旋轉後取樣點）')
    a.add_argument('--out', type=Path)
    a.set_defaults(run=run_estimate)
    a = commands.add_parser('tower-project',
         help='給定外部精確 WORLD_SURFACE_WG，計算基板與主要塔樓 Y；不計算 Noise，結果需驗證')
    a.add_argument('--version', choices=sorted(SUPPORTED), default='1.21.8')
    a.add_argument('--seed', type=signed_seed, required=True)
    a.add_argument('--chunk-x', type=int, required=True)
    a.add_argument('--chunk-z', type=int, required=True)
    a.add_argument('--game-jar', type=Path, required=True)
    a.add_argument('--world-surface-wg', type=int, required=True)
    a.add_argument('--out', type=Path, help='JSON 結果（可省略，改輸出標準輸出）')
    a.set_defaults(run=run_tower_project)
    from asset_audit import add_command as add_assets_audit_command
    add_assets_audit_command(commands)
    from geometry_audit import add_command as add_geometry_audit_command
    add_geometry_audit_command(commands)
    from noise_witness import add_command as add_noise_witness_command
    add_noise_witness_command(commands)
    from worldgen_contract import add_command as add_worldgen_contract_command
    add_worldgen_contract_command(commands)
    from structure_contract import add_command as add_structure_contract_command
    add_structure_contract_command(commands)
    from certification import add_command as add_certification_command
    add_certification_command(commands)
    from region_certificate import add_command as add_region_certificate_command
    add_region_certificate_command(commands)
    from live import add_live_command
    add_live_command(commands)
    from vanilla_oracle import add_vanilla_command
    add_vanilla_command(commands)
    a = commands.add_parser('search-live', help='候選搜尋 → 同版原版伺服器生成 → NBT 讀取塔樓')
    a.add_argument('--version', choices=['auto', *sorted(SUPPORTED)], default='auto')
    a.add_argument('--world', type=Path, required=True)
    a.add_argument('--radius', type=int, default=8192)
    a.add_argument('--limit', type=int, default=50)
    a.add_argument('--timeout', type=int, default=180)
    a.add_argument('--host', default='127.0.0.1')
    a.add_argument('--port', type=int, default=25575)
    a.add_argument('--password-env', default='MINECRAFT_RCON_PASSWORD')
    a.add_argument('--allow-remote', action='store_true')
    a.add_argument('--max-y', type=int, help='僅輸出經驗證 base_plate_y 小於等於此值的塔')
    a.add_argument('--center-y-below', type=float, default=-37,
                   help='只接受完整結構中心 Y 低於此值；找到最近符合者後停止')
    a.add_argument('--priority', choices=['near-origin', 'terrain'], default='near-origin',
                   help='優先驗證最近候選，或使用未驗證的 C 地表高度排序')
    a.add_argument('--core-archive', type=Path, help='--priority terrain 所需地形核心原始碼壓縮檔')
    a.add_argument('--game-jar', type=Path, help='所選版本的遊戲資源 JAR，供試驗性地形排序投影起始基板')
    a.add_argument('--audit', type=Path, help='將所有已檢查候選的結果保留為稽核記錄')
    a.add_argument('--out', type=Path, required=True)
    a.set_defaults(run=run_search_live)
    args = parser.parse_args(argv)
    try:
        args.run(args)
    except (ValueError, NBTError, OSError, subprocess.CalledProcessError, RuntimeError, ConnectionError) as exc:
        print(f'ERROR: {exc}', file=sys.stderr)
        return 2
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
