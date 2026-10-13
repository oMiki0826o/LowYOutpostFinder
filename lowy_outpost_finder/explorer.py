"""File: explorer.py
Modification: 2026-10-13 — region-grid seed search and cancellable batch engine.

This module distinguishes structure-placement candidates, approximate seed-only
surface samples, and verified saved-world structures. Neither candidates nor
approximate samples establish an actual vanilla-generated outpost.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED
import csv
from dataclasses import dataclass
import io
from pathlib import Path
import subprocess
import threading
import time
from typing import Callable, Iterable

from .cli import OUTPOST, pass_legacy_frequency, pass_village_exclusion, region_position, signed_seed, write_csv, is_candidate_start
from .paths import native_binary
from .versions import check_version

MAX_REGIONS = 5_000_000
MAX_SEEDS = 10_000
MAX_ROWS_PER_SEED = 50_000
FIELDS = ('version', 'seed', 'chunk_x', 'chunk_z', 'x', 'z',
          'projected_surface_y', 'biome_id', 'classification')


@dataclass(frozen=True)
class RegionBounds:
    """Bounds in 32×32-chunk regions (= 512 blocks), inclusive."""
    min_x: int
    max_x: int
    min_z: int
    max_z: int

    def __post_init__(self) -> None:
        for x in (self.min_x, self.max_x, self.min_z, self.max_z):
            if not isinstance(x, int) or not -58_594 <= x <= 58_594:
                raise ValueError('Region bounds must be in -58594..58594')
        if self.min_x > self.max_x or self.min_z > self.max_z:
            raise ValueError('Minimum region coordinates must not exceed maximum')
        if self.count > MAX_REGIONS:
            raise ValueError(f'{self.count:,} regions exceeds the safety limit ({MAX_REGIONS:,})')

    @property
    def count(self) -> int:
        return (self.max_x - self.min_x + 1) * (self.max_z - self.min_z + 1)


def load_seeds(path: Path) -> list[int]:
    """Read signed 64-bit seeds, preserving first appearance and rejecting errors."""
    seen: set[int] = set()
    seeds: list[int] = []
    with path.open('r', encoding='utf-8-sig') as file:
        for line_number, line in enumerate(file, 1):
            item = line.partition('#')[0].strip()
            if not item:
                continue
            try:
                seed = signed_seed(item)
            except argparse.ArgumentTypeError as exc:
                raise ValueError(f'{path}:{line_number}: {exc}') from exc
            if seed not in seen:
                seeds.append(seed)
                seen.add(seed)
            if len(seeds) > MAX_SEEDS:
                raise ValueError(f'At most {MAX_SEEDS:,} distinct seeds per search')
    if not seeds:
        raise ValueError(f'The seed file {path} has no valid seeds')
    return seeds


def candidate_area(seed: int, bounds: RegionBounds, *, cancel: threading.Event | None = None,
                   pause: threading.Event | None = None, progress=None):
    """Stream placement-only candidates inside a region rectangle without Y claims."""
    total = bounds.max_z - bounds.min_z + 1
    for rz in range(bounds.min_z, bounds.max_z + 1):
        if cancel is not None and cancel.is_set():
            return
        if pause is not None:
            while not pause.wait(0.12):
                if cancel is not None and cancel.is_set():
                    return
        for rx in range(bounds.min_x, bounds.max_x + 1):
            cx, cz = region_position(seed, rx, rz, OUTPOST)
            if not (-29_999_984 <= cx * 16 <= 29_999_984
                    and -29_999_984 <= cz * 16 <= 29_999_984):
                continue
            if pass_legacy_frequency(seed, cx, cz) and pass_village_exclusion(seed, cx, cz):
                yield {'seed': seed, 'chunk_x': cx, 'chunk_z': cz,
                       'x': cx * 16, 'z': cz * 16,
                       'projected_surface_y': '', 'biome_id': '',
                       'classification': 'placement_candidate'}
        if progress is not None:
            progress(rz - bounds.min_z + 1, total)


class Explorer:
    """Safe, seed-only search with explicit provisional-result metadata."""

    def __init__(self, version: str, *, mode: str = 'candidates',
                 bounds: RegionBounds | None = None, radius: int = 8192,
                 max_y: int = 64, top_per_seed: int = 500,
                 threads: int = 1, binary: Path | None = None):
        check_version(version)
        if mode not in ('candidates', 'estimate'):
            raise ValueError('Search mode must be candidates or estimate')
        if mode == 'estimate' and version != '1.21.8':
            raise ValueError('Seed-only approximate Y is experimental and limited to 1.21.8')
        if mode == 'estimate' and not -64 <= max_y <= 320:
            raise ValueError('Experimental maximum Y must be in -64..320')
        if not 1 <= threads <= 16:
            raise ValueError('Thread count must be in 1..16')
        if not 1 <= top_per_seed <= MAX_ROWS_PER_SEED:
            raise ValueError(f'Per-seed result limit must be in 1..{MAX_ROWS_PER_SEED}')
        if not 0 <= radius <= 30_000_000:
            raise ValueError('Radius must be in 0..30000000')
        self.version = version
        self.mode = mode
        self.bounds = bounds or RegionBounds(-16, 16, -16, 16)
        self.radius = radius
        self.max_y = max_y
        self.top_per_seed = top_per_seed
        self.threads = threads
        self.binary = binary or native_binary('lowyoutpost')

    def _one(self, seed: int, cancel: threading.Event, pause: threading.Event, region_progress=None) -> list[dict]:
        if cancel.is_set():
            return []
        while not pause.wait(0.12):
            if cancel.is_set():
                return []
        if self.mode == 'candidates':
            rows = []
            for row in candidate_area(seed, self.bounds, cancel=cancel, pause=pause, progress=region_progress):
                rows.append({'version': self.version, **row})
                if len(rows) > self.top_per_seed:
                    raise ValueError(f'{seed}: more than {self.top_per_seed} candidates; '
                                     'increase the per-seed result limit or reduce the area')
            return rows
        if not self.binary.is_file():
            raise ValueError('Native terrain sampler is missing. Build it first using build.sh '
                             'and your supplied LowYSwampHut 2.0.1 source archive')
        cmd = [str(self.binary), '--seed', str(seed), '--radius', str(self.radius),
               '--max-y', str(self.max_y), '--top', str(self.top_per_seed), '--skip-biome']
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                                   encoding='utf-8')
        try:
            while True:
                if cancel.is_set():
                    process.terminate()
                    try:
                        process.communicate(timeout=2)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.communicate()
                    return []
                try:
                    stdout, stderr = process.communicate(timeout=0.2)
                    break
                except subprocess.TimeoutExpired:
                    pass
            if process.returncode:
                raise RuntimeError(f'Native seed {seed} failed: {stderr.strip()}')
            items = list(csv.DictReader(io.StringIO(stdout)))
            if len(items) > self.top_per_seed:
                raise RuntimeError('Native terrain sampler exceeded the requested result limit')
            seen: set[tuple[int, int]] = set()
            for item in items:
                if item.get('classification') not in ('estimated_only', 'approximate_surface'):
                    raise RuntimeError('Unrecognized terrain sampler classification')
                if item.get('version') != self.version:
                    raise RuntimeError('Native sampler returned a different Minecraft version')
                try:
                    native_seed = int(item['seed'])
                    cx, cz = int(item['chunk_x']), int(item['chunk_z'])
                    x, z = int(item['x']), int(item['z'])
                    y = int(item['projected_surface_y'])
                except (ValueError, TypeError, KeyError) as exc:
                    raise RuntimeError('Native sampler returned malformed numeric fields') from exc
                if native_seed != seed:
                    raise RuntimeError('Native sampler returned the wrong seed')
                if not (x == cx * 16 and z == cz * 16 and
                        is_candidate_start(seed, cx, cz) and
                        -self.radius <= x <= self.radius and
                        -self.radius <= z <= self.radius):
                    raise RuntimeError('Native sampler returned a non-candidate or out-of-range position')
                if not -64 <= y <= self.max_y:
                    raise RuntimeError('Native sampler returned an invalid height')
                if (cx, cz) in seen:
                    raise RuntimeError('Native sampler returned duplicate candidates')
                seen.add((cx, cz))
                item['classification'] = 'estimated_only'
            return items
        finally:
            if process.poll() is None:
                process.kill()
                process.communicate()

    @staticmethod
    def sort_rows(rows: list[dict], mode: str) -> list[dict]:
        if mode == 'y':
            if any(r.get('classification') != 'estimated_only' and r.get('status') != 'verified_tower'
                   for r in rows):
                raise ValueError('Cannot sort placement-only rows by Y; they have no Y')
            return sorted(rows, key=lambda r: (int(r.get('projected_surface_y') or r.get('base_plate_y')),
                                               int(r['seed']), int(r['x']), int(r['z'])))
        if mode == 'distance':
            return sorted(rows, key=lambda r: (int(r['x'])**2 + int(r['z'])**2,
                                               int(r['seed']), int(r['x']), int(r['z'])))
        if mode == 'seed':
            return sorted(rows, key=lambda r: (int(r['seed']), int(r['x']), int(r['z'])))
        raise ValueError('Sort must be y, distance or seed')

    def run(self, seeds: Iterable[int], *, pause: threading.Event | None = None,
            cancel: threading.Event | None = None,
            progress: Callable[[int, int, int, float | None], None] | None = None,
            region_progress: Callable[[int, int], None] | None = None) -> list[dict]:
        seeds = list(seeds)
        if not seeds or len(seeds) > MAX_SEEDS:
            raise ValueError(f'Supply 1..{MAX_SEEDS} seeds')
        if any(not -(1 << 63) <= s < (1 << 63) for s in seeds):
            raise ValueError('All seeds must be signed 64-bit integers')
        if pause is None:
            pause = threading.Event()
            pause.set()
        cancel = cancel or threading.Event()
        started = time.monotonic()
        rows: list[dict] = []
        completed = 0
        with ThreadPoolExecutor(max_workers=self.threads) as executor:
            work: dict = {}
            remaining = iter(seeds)
            def submit() -> None:
                if cancel.is_set():
                    return
                try:
                    seed = next(remaining)
                except StopIteration:
                    return
                work[executor.submit(self._one, seed, cancel, pause,
                                     region_progress if len(seeds) == 1 else None)] = seed
            for _ in range(min(self.threads, len(seeds))):
                submit()
            while work:
                finished, _ = wait(work, timeout=0.15, return_when=FIRST_COMPLETED)
                for future in finished:
                    work.pop(future)
                    rows.extend(future.result())
                    completed += 1
                    if progress:
                        eta = (time.monotonic() - started) / completed * (len(seeds) - completed)
                        progress(completed, len(seeds), len(rows), eta)
                    if not cancel.is_set():
                        submit()
        return rows


def export_seed_list(path: Path, rows: Iterable[dict]) -> None:
    seen: set[int] = set()
    items = []
    for row in rows:
        seed = int(row['seed'])
        if seed not in seen:
            seen.add(seed)
            items.append(str(seed))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(''.join(s + '\n' for s in items), encoding='utf-8')


def export_teleports(path: Path, rows: Iterable[dict]) -> None:
    """Never fabricate a Y for candidate or approximate results."""
    lines = ['# Verified saved-world base plate heights only. Verify safety before teleporting.',
             '# Candidates and approximate heights are listed as coordinates only.']
    for row in rows:
        if row.get('status') == 'verified_tower' and str(row.get('base_plate_y', '')).strip():
            lines.append(f"/tp {int(row['x'])} {int(row['base_plate_y'])} {int(row['z'])}")
        else:
            lines.append(f"# seed={int(row['seed'])} x={int(row['x'])} z={int(row['z'])} Y=unverified")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('\n'.join(lines) + '\n', encoding='utf-8')


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description='1.21+ batch placement/approximation explorer; never asserts exact Y')
    seeds = parser.add_mutually_exclusive_group(required=True)
    seeds.add_argument('--seed', type=signed_seed)
    seeds.add_argument('--seeds-file', type=Path)
    parser.add_argument('--version', default='1.21.8')
    parser.add_argument('--mode', choices=['candidates', 'estimate'], default='candidates')
    for key, default in [('min-x', -16), ('max-x', 16), ('min-z', -16), ('max-z', 16)]:
        parser.add_argument('--' + key, type=int, default=default, help='512-block region index, inclusive')
    parser.add_argument('--radius', type=int, default=8192, help='Estimate mode only: square search radius in blocks')
    parser.add_argument('--max-y', type=int, default=64, help='Estimate mode only: exploratory height threshold')
    parser.add_argument('--top', type=int, default=500, help='Max rows retained per seed')
    parser.add_argument('--threads', type=int, default=1, help='Parallel seed workers (1..16)')
    parser.add_argument('--sort', choices=['distance', 'seed', 'y'], default='distance')
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--export-seeds', type=Path)
    parser.add_argument('--export-tp', type=Path)
    a = parser.parse_args(argv)
    try:
        selected = [a.seed] if a.seeds_file is None else load_seeds(a.seeds_file)
        explore = Explorer(a.version, mode=a.mode,
                           bounds=RegionBounds(a.min_x, a.max_x, a.min_z, a.max_z),
                           radius=a.radius, max_y=a.max_y, top_per_seed=a.top, threads=a.threads)
        ready = threading.Event()
        ready.set()
        def update(done, total, count, eta):
            print(f'SEEDS {done}/{total} | results={count} | eta={eta:.1f}s', flush=True)
        rows = explore.run(selected, pause=ready, progress=update)
        rows = explore.sort_rows(rows, a.sort)
        write_csv(a.out, rows, FIELDS)
        if a.export_seeds:
            export_seed_list(a.export_seeds, rows)
        if a.export_tp:
            export_teleports(a.export_tp, rows)
        print(f'Saved {len(rows)} rows to {a.out}')
        return 0
    except (ValueError, OSError, RuntimeError, subprocess.SubprocessError) as exc:
        parser.exit(2, f'ERROR: {exc}\n')


if __name__ == '__main__':
    raise SystemExit(main())
