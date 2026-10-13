"""File: full_map.py
Modification: 2026-10-13 — bounded-memory, resumable, no-chunk-generation placement scan.

This enumerates *placement attempts*, not actual outposts or their Y. Every
region is checked only if the checkpoint reaches status='complete'.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import hashlib
import heapq
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

from .cli import (OUTPOST, CANDIDATE_FIELDS, is_candidate_start, pass_legacy_frequency,
                    pass_village_exclusion, region_position, signed_seed, write_csv)
from .versions import check_version

WORLD_EDGE = 29_999_984
MAX_TOP = 10000
OUTPUT_FIELDS = (*CANDIDATE_FIELDS, 'distance_sq')


@dataclass(frozen=True)
class RegionGrid:
    """Inclusive x/z rectangle indexed in deterministic row-major placement cells."""
    x_min: int
    x_max: int
    z_min: int
    z_max: int

    def __post_init__(self):
        if (any(type(v) is not int or abs(v) > WORLD_EDGE for v in
                (self.x_min, self.x_max, self.z_min, self.z_max))
                or self.x_min > self.x_max or self.z_min > self.z_max):
            raise ValueError(f'World bounds must be increasing integer blocks inside ±{WORLD_EDGE}')

    @property
    def rx_min(self) -> int:
        return (self.x_min - (OUTPOST[0] - OUTPOST[1] - 1) * 16) // (OUTPOST[0] * 16)

    @property
    def rx_max(self) -> int:
        return self.x_max // (OUTPOST[0] * 16)

    @property
    def rz_min(self) -> int:
        return (self.z_min - (OUTPOST[0] - OUTPOST[1] - 1) * 16) // (OUTPOST[0] * 16)

    @property
    def rz_max(self) -> int:
        return self.z_max // (OUTPOST[0] * 16)

    @property
    def width(self) -> int:
        return self.rx_max - self.rx_min + 1

    @property
    def total(self) -> int:
        return self.width * (self.rz_max - self.rz_min + 1)

    def row_col(self, index: int) -> tuple[int, int]:
        if not 0 <= index < self.total:
            raise ValueError('Region index outside grid')
        row, col = divmod(index, self.width)
        return self.rx_min + col, self.rz_min + row


def rank(cx: int, cz: int, center_x: int, center_z: int) -> tuple[int, int, int]:
    x, z = cx * 16, cz * 16
    return ((x - center_x) ** 2 + (z - center_z) ** 2, cx, cz)


def _add(heap: list[tuple[int, int, int]], cx: int, cz: int, top: int,
         center_x: int, center_z: int) -> None:
    """Retain exactly the smallest top ranks; max heap via negated tuple."""
    key = tuple(-v for v in rank(cx, cz, center_x, center_z))
    if len(heap) < top:
        heapq.heappush(heap, key)
    elif key > heap[0]:
        heapq.heapreplace(heap, key)


def scan_python(grid: RegionGrid, seed: int, start: int, end: int, top: int,
                center_x: int, center_z: int) -> tuple[list[tuple[int, int]], int]:
    if not 0 <= start <= end <= grid.total:
        raise ValueError('Invalid region slice')
    heap: list[tuple[int, int, int]] = []
    matches = 0
    width = grid.width
    for index in range(start, end):
        row, col = divmod(index, width)
        cx, cz = region_position(seed, grid.rx_min + col, grid.rz_min + row, OUTPOST)
        x, z = cx * 16, cz * 16
        if not (grid.x_min <= x <= grid.x_max and grid.z_min <= z <= grid.z_max):
            continue
        if pass_legacy_frequency(seed, cx, cz) and pass_village_exclusion(seed, cx, cz):
            matches += 1
            _add(heap, cx, cz, top, center_x, center_z)
    return [(-key[1], -key[2]) for key in heap], matches


def scan_native(grid: RegionGrid, seed: int, start: int, end: int, top: int,
                center_x: int, center_z: int, binary: Path) -> tuple[list[tuple[int, int]], int]:
    command = [str(binary), '--seed', str(seed), '--start', str(start),
               '--count', str(end - start), '--x-min', str(grid.x_min),
               '--x-max', str(grid.x_max), '--z-min', str(grid.z_min),
               '--z-max', str(grid.z_max), '--center-x', str(center_x),
               '--center-z', str(center_z), '--top', str(top)]
    result = subprocess.run(command, capture_output=True, text=True, timeout=3600, check=False)
    if result.returncode:
        raise RuntimeError(f'Native placement scan failed (exit={result.returncode}): {result.stderr[-1200:]}')
    try:
        payload = json.loads(result.stdout)
        hits = payload['hits']
        matched = payload['matches']
        if (type(matched) is not int or not 0 <= matched <= end - start
                or not isinstance(hits, list) or len(hits) > top):
            raise ValueError('Invalid native result header')
        output = []
        seen = set()
        for entry in hits:
            if (not isinstance(entry, list) or len(entry) != 2
                    or any(type(c) is not int for c in entry)):
                raise ValueError('Invalid native candidate')
            cx, cz = entry
            rx, rz = cx // OUTPOST[0], cz // OUTPOST[0]
            idx = (rz - grid.rz_min) * grid.width + (rx - grid.rx_min)
            if (cx, cz) in seen or not is_candidate_start(seed, cx, cz) or not start <= idx < end:
                raise ValueError('Untrusted native candidate mismatch or wrong region slice')
            if not grid.x_min <= cx * 16 <= grid.x_max or not grid.z_min <= cz * 16 <= grid.z_max:
                raise ValueError('Native candidate outside selected rectangle')
            seen.add((cx, cz))
            output.append((cx, cz))
        if len(output) != min(top, matched):
            raise ValueError('Native result count differs from matches')
        return output, matched
    except (KeyError, TypeError, json.JSONDecodeError) as exc:
        raise RuntimeError('Native scan returned an invalid JSON response') from exc


def _cell_min_distance(grid: RegionGrid, rx: int, rz: int,
                       center_x: int, center_z: int) -> int | None:
    """Admissible Euclidean lower bound on the start-block position.

    Java spread offsets are 0..23 chunks. All possible candidate starts are
    inside the following rectangles, even if most offsets are not attainable.
    """
    xlo = max(rx * 512, grid.x_min)
    xhi = min(rx * 512 + 368, grid.x_max)
    zlo = max(rz * 512, grid.z_min)
    zhi = min(rz * 512 + 368, grid.z_max)
    if xlo > xhi or zlo > zhi:
        return None
    dx = max(xlo - center_x, 0, center_x - xhi)
    dz = max(zlo - center_z, 0, center_z - zhi)
    return dx * dx + dz * dz


def scan_nearest(grid: RegionGrid, seed: int, top: int,
                 center_x: int, center_z: int) -> tuple[list[tuple[int, int]], dict]:
    """Provably nearest *placement* top-K without enumerating the whole world.

    Priority-first grid expansion uses an admissible lower bound. A complete
    radius of possible candidate origin boxes is exhausted before returning.
    The proof excludes unvisited boxes from containing a nearer candidate.
    This does not establish actual generated structures or vertical heights.
    """
    if not 1 <= top <= MAX_TOP:
        raise ValueError('Nearest top limit must be 1..10000')
    rx_start = min(max(center_x // 512, grid.rx_min), grid.rx_max)
    rz_start = min(max(center_z // 512, grid.rz_min), grid.rz_max)
    frontier: list[tuple[int, int, int]] = []
    seen: set[tuple[int, int]] = set()

    def add(rx: int, rz: int) -> None:
        if not grid.rx_min <= rx <= grid.rx_max or not grid.rz_min <= rz <= grid.rz_max:
            return
        if (rx, rz) in seen:
            return
        seen.add((rx, rz))
        lower_bound = _cell_min_distance(grid, rx, rz, center_x, center_z)
        if lower_bound is not None:
            heapq.heappush(frontier, (lower_bound, rz, rx))

    for rx in (rx_start-1, rx_start, rx_start+1):
        for rz in (rz_start-1, rz_start, rz_start+1):
            add(rx, rz)
    heap: list[tuple[int, int, int]] = []
    matched = 0
    visited = 0
    proof_bound: int | None = None
    while frontier:
        if len(heap) == top and frontier[0][0] > -heap[0][0]:
            proof_bound = frontier[0][0]
            break
        bound, rz, rx = heapq.heappop(frontier)
        visited += 1
        cx, cz = region_position(seed, rx, rz, OUTPOST)
        if (grid.x_min <= cx * 16 <= grid.x_max
                and grid.z_min <= cz * 16 <= grid.z_max
                and pass_legacy_frequency(seed, cx, cz)
                and pass_village_exclusion(seed, cx, cz)):
            matched += 1
            _add(heap, cx, cz, top, center_x, center_z)
        # 4-connected neighbours suffice: distance to the rectangular cell
        # intervals is monotone when moving towards the center interval.
        for nx, nz in ((rx-1, rz), (rx+1, rz), (rx, rz-1), (rx, rz+1)):
            add(nx, nz)
        if len(seen) > 250_000:
            raise RuntimeError('Nearest frontier memory guard reached; use --strategy exhaustive')
    hits = sorted(((-key[1], -key[2]) for key in heap),
                  key=lambda t: rank(t[0], t[1], center_x, center_z))
    return hits, {
        'status': 'proven_nearest_placement_only',
        'scope': 'placement_only_no_y',
        'visited_regions': visited,
        'total_regions': grid.total,
        'visited_candidates': matched,
        'nearest_lower_bound_sq': proof_bound,
        'maximum_retained_distance_sq': (rank(*hits[-1], center_x, center_z)[0] if hits else None),
        'proof': 'unvisited cells cannot have smaller distance than the kth retained placement candidate'
                 if proof_bound is not None else 'all intersecting cells exhausted',
    }


def run_nearest(cfg: 'ScanConfig', out: Path) -> dict:
    grid = cfg.validate()
    out = Path(out)
    if out.suffix.lower() != '.csv':
        raise ValueError('Output must be .csv')
    if out.exists() or out.with_suffix('.state.json').exists():
        raise ValueError('Refusing to overwrite existing output; use another file')
    hits, evidence = scan_nearest(grid, cfg.seed, cfg.top, cfg.center_x, cfg.center_z)
    rows = [{'version': cfg.version, 'seed': cfg.seed, 'chunk_x': cx,
             'chunk_z': cz, 'x': cx * 16, 'z': cz * 16,
             'distance_sq': rank(cx, cz, cfg.center_x, cfg.center_z)[0],
             'classification': 'placement_candidate'} for cx, cz in hits]
    write_csv(out, rows, OUTPUT_FIELDS)
    evidence.update({'seed': cfg.seed, 'version': cfg.version,
                     'retained_candidates': len(hits), 'configuration_sha256': _digest(cfg)})
    _atomic_json(out.with_suffix('.state.json'), evidence)
    return evidence


@dataclass(frozen=True)
class ScanConfig:
    version: str
    seed: int
    x_min: int = -WORLD_EDGE
    x_max: int = WORLD_EDGE
    z_min: int = -WORLD_EDGE
    z_max: int = WORLD_EDGE
    center_x: int = 0
    center_z: int = 0
    top: int = 100
    batch_regions: int = 500_000
    sleep_ms: int = 150
    engine: str = 'auto'

    def validate(self) -> RegionGrid:
        check_version(self.version)
        if type(self.seed) is not int or not -(1 << 63) <= self.seed < (1 << 63):
            raise ValueError('World seed must be a signed Java 64-bit integer')
        if (not 1 <= self.top <= MAX_TOP or not 1 <= self.batch_regions <= 5_000_000
                or not 0 <= self.sleep_ms <= 5000):
            raise ValueError('top must be 1..10000; batch-regions 1..5000000; cpu-rest-ms 0..5000')
        if self.engine not in ('auto', 'python', 'native'):
            raise ValueError('Unknown engine')
        if not all(type(n) is int and -WORLD_EDGE <= n <= WORLD_EDGE
                   for n in (self.center_x, self.center_z)):
            raise ValueError('Center outside world border')
        return RegionGrid(self.x_min, self.x_max, self.z_min, self.z_max)


def _atomic_json(path: Path, object_: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = None
    try:
        with tempfile.NamedTemporaryFile('w', encoding='utf-8', dir=path.parent,
                                         prefix='.' + path.name, suffix='.tmp', delete=False) as handle:
            temp = Path(handle.name)
            json.dump(object_, handle, ensure_ascii=False, sort_keys=True, indent=2)
            handle.write('\n')
            handle.flush()
            os.fsync(handle.fileno())
        temp.replace(path)
    finally:
        if temp is not None:
            temp.unlink(missing_ok=True)


def _digest(cfg: ScanConfig) -> str:
    # batch and sleep affect scheduling, not the actual result; changing engine
    # mid-flight must be allowed for users who add a compiler later.
    params = {k: v for k, v in asdict(cfg).items()
              if k not in ('batch_regions', 'sleep_ms', 'engine')}
    return hashlib.sha256(json.dumps(params, sort_keys=True).encode('utf-8')).hexdigest()


def scan(cfg: ScanConfig, out: Path, *, resume: bool = False,
         max_batches: int = 0, progress=None, binary: Path | None = None) -> dict:
    grid = cfg.validate()
    if max_batches < 0:
        raise ValueError('max-batches must not be negative')
    out = Path(out)
    if out.suffix.casefold() != '.csv':
        raise ValueError('Output must be a .csv file')
    state_path = out.with_suffix('.state.json')
    fingerprint = _digest(cfg)
    if resume:
        if not state_path.is_file():
            raise ValueError('No checkpoint found; run without --resume for a new scan')
        state = json.loads(state_path.read_text(encoding='utf-8'))
        if state.get('configuration_sha256') != fingerprint or state.get('total_regions') != grid.total:
            raise ValueError('checkpoint does not match the selected search parameters')
        if not 0 <= state['processed_regions'] <= grid.total:
            raise ValueError('Invalid saved checkpoint progress')
        if (type(state.get('placement_candidates')) is not int or not 0 <= state['placement_candidates'] <= state['processed_regions']
                or (state.get('status') == 'complete') != (state['processed_regions'] == grid.total)):
            raise ValueError('Invalid checkpoint candidate count or completion marker')
        retained = state.get('retained', [])
        if not isinstance(retained, list) or len(retained) > cfg.top:
            raise ValueError('Invalid checkpoint retained set')
        heap = []
        restored = set()
        for item in retained:
            if not isinstance(item, list) or len(item) != 2 or any(type(v) is not int for v in item):
                raise ValueError('Invalid saved candidate tuple')
            cx, cz = item
            rx, rz = cx // OUTPOST[0], cz // OUTPOST[0]
            offset = (rz - grid.rz_min) * grid.width + (rx - grid.rx_min)
            if (cx, cz) in restored or not 0 <= offset < state['processed_regions']:
                raise ValueError('Invalid checkpoint candidate region or duplicate')
            if (not is_candidate_start(cfg.seed, cx, cz)
                    or not grid.x_min <= cx * 16 <= grid.x_max
                    or not grid.z_min <= cz * 16 <= grid.z_max):
                raise ValueError('Invalid checkpoint placement candidate')
            restored.add((cx, cz))
            _add(heap, *item, cfg.top, cfg.center_x, cfg.center_z)
        if len(restored) > state['placement_candidates']:
            raise ValueError('Invalid checkpoint retained candidate count')
    else:
        if out.exists() or state_path.exists():
            raise ValueError('Refusing to overwrite existing output/checkpoint; use --resume or choose another path')
        state = {'configuration_sha256': fingerprint, 'seed': cfg.seed, 'version': cfg.version,
                 'total_regions': grid.total, 'processed_regions': 0, 'placement_candidates': 0,
                 'status': 'incomplete', 'classification': 'placement_candidate', 'retained': [],
                 'bounds': {'x_min': cfg.x_min, 'x_max': cfg.x_max,
                            'z_min': cfg.z_min, 'z_max': cfg.z_max}}
        heap = []
        _atomic_json(state_path, state)

    if binary is None:
        from .paths import native_binary
        binary = native_binary('region_scan')
    engine = 'native' if cfg.engine == 'native' or (cfg.engine == 'auto' and binary.is_file()) else 'python'
    if engine == 'native' and not binary.is_file():
        raise ValueError('Native scanner not compiled; run: python3 scripts/build_region_scan.py')
    if grid.total > 5_000_000 and engine == 'python' and state['processed_regions'] == 0:
        print('WARNING: Python fallback for world-size scans is very slow. Build the optional native scanner.', file=sys.stderr)

    index = state['processed_regions']
    batches = 0
    while index < grid.total and (max_batches == 0 or batches < max_batches):
        end = min(index + cfg.batch_regions, grid.total)
        if engine == 'native':
            hits, matched = scan_native(grid, cfg.seed, index, end, cfg.top,
                                        cfg.center_x, cfg.center_z, binary)
        else:
            hits, matched = scan_python(grid, cfg.seed, index, end, cfg.top,
                                        cfg.center_x, cfg.center_z)
        for cx, cz in hits:
            _add(heap, cx, cz, cfg.top, cfg.center_x, cfg.center_z)
        index = end
        batches += 1
        state.update(processed_regions=index,
                     placement_candidates=state['placement_candidates'] + matched,
                     retained=[[-h[1], -h[2]] for h in heap],
                     status='complete' if index == grid.total else 'incomplete',
                     engine_last_used=engine)
        # Publish checkpoint before output CSV. After a crash, --resume
        # reconstructs the CSV from the checkpoint even if this write failed.
        _atomic_json(state_path, state)
        rows = []
        for cx, cz in sorted(((-h[1], -h[2]) for h in heap),
                             key=lambda pair: rank(*pair, cfg.center_x, cfg.center_z)):
            rows.append({'version': cfg.version, 'seed': cfg.seed, 'chunk_x': cx,
                         'chunk_z': cz, 'x': cx * 16, 'z': cz * 16,
                         'classification': 'placement_candidate',
                         'distance_sq': rank(cx, cz, cfg.center_x, cfg.center_z)[0]})
        write_csv(out, rows, OUTPUT_FIELDS)
        if progress is not None:
            progress(state)
        if cfg.sleep_ms and index != grid.total:
            time.sleep(cfg.sleep_ms / 1000)
    # Crash recovery: the checkpoint is authoritative; ensure final CSV matches
    # checkpoint even when --resume had no further regions to process.
    if batches == 0:
        rows = []
        for cx, cz in sorted(((-h[1], -h[2]) for h in heap),
                             key=lambda pair: rank(*pair, cfg.center_x, cfg.center_z)):
            rows.append({'version': cfg.version, 'seed': cfg.seed, 'chunk_x': cx,
                         'chunk_z': cz, 'x': cx * 16, 'z': cz * 16,
                         'classification': 'placement_candidate',
                         'distance_sq': rank(cx, cz, cfg.center_x, cfg.center_z)[0]})
        write_csv(out, rows, OUTPUT_FIELDS)
    return state


def run_command(args) -> None:
    cfg = ScanConfig(args.version, args.seed, args.x_min, args.x_max,
                     args.z_min, args.z_max, args.center_x, args.center_z,
                     args.top, args.batch_regions, args.cpu_rest_ms, args.engine)
    if args.game_jar:
        from .game_archive import require_matching_game_version
        from .placement_assets import validate_placement_assets
        require_matching_game_version(args.game_jar, args.version)
        validate_placement_assets(args.game_jar)

    def announce(state):
        print(f"FULLMAP_PROGRESS {state['processed_regions']} {state['total_regions']} "
              f"{state['placement_candidates']} {state['status']}", file=sys.stderr, flush=True)

    if args.strategy == 'nearest':
        if args.resume or args.max_batches:
            raise ValueError('--resume and --max-batches only apply to exhaustive scans')
        result = run_nearest(cfg, args.out)
        print(f"Nearest whole-world placement proof: {result['visited_regions']:,}/"
              f"{result['total_regions']:,} cells visited; {result['retained_candidates']} candidate(s) retained. "
              'No biome, Y, or generated tower validation.', file=sys.stderr)
        return
    result = scan(cfg, args.out, resume=args.resume, max_batches=args.max_batches,
                  progress=announce)
    print(f"Full-map placement scan: {result['status']} "
          f"{result['processed_regions']:,}/{result['total_regions']:,} grid cells; "
          f"{result['placement_candidates']:,} candidate attempts; no biome/Noise/Jigsaw/Y verification",
          file=sys.stderr)


def add_command(commands) -> None:
    from .versions import SUPPORTED
    a = commands.add_parser('full-map', help='No-chunk-generation, bounded-memory, resumable whole-world placement scan (NO Y)')
    a.add_argument('--version', choices=sorted(SUPPORTED), default='1.21.8')
    a.add_argument('--seed', type=signed_seed, required=True)
    a.add_argument('--x-min', type=int, default=-WORLD_EDGE)
    a.add_argument('--x-max', type=int, default=WORLD_EDGE)
    a.add_argument('--z-min', type=int, default=-WORLD_EDGE)
    a.add_argument('--z-max', type=int, default=WORLD_EDGE)
    a.add_argument('--center-x', type=int, default=0)
    a.add_argument('--center-z', type=int, default=0)
    a.add_argument('--top', type=int, default=100, help='Keep only the nearest N placement candidates (1..10000)')
    a.add_argument('--batch-regions', type=int, default=500_000, help='Cells per resumable checkpoint')
    a.add_argument('--cpu-rest-ms', type=int, default=150, help='Sleep after each batch to reduce sustained CPU load')
    a.add_argument('--engine', choices=('auto', 'python', 'native'), default='auto')
    a.add_argument('--game-jar', type=Path, help='Optional version-matched vanilla asset placement check')
    a.add_argument('--strategy', choices=('nearest', 'exhaustive'), default='nearest',
                   help='nearest = provably nearest placement top K with spatial pruning; exhaustive = check all cells with checkpoint')
    a.add_argument('--resume', action='store_true', help='Resume matching .state.json checkpoint')
    a.add_argument('--max-batches', type=int, default=0, help='Optional finite-run limit; incomplete scan is clearly marked')
    a.add_argument('--out', type=Path, required=True)
    a.set_defaults(run=run_command)
