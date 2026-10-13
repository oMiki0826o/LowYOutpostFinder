"""File: benchmark.py
Modification: 2026-10-12 — reproducible local speed measurements, never projected runtime promises.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import statistics
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from lowy_outpost_finder.cli import candidates


def parse_radii(value: str) -> list[int]:
    try:
        values = [int(s.strip()) for s in value.split(',')]
    except ValueError as exc:
        raise ValueError('radii must be comma-separated nonnegative integers') from exc
    if not 1 <= len(values) <= 8 or any(not 0 <= n <= 30_000_000 for n in values):
        raise ValueError('provide one to eight radii within 0..30000000')
    return values


def benchmark(seed: int, radii: list[int], *, rounds: int = 3,
              native: Path | None = None) -> list[dict]:
    """Measure placement scan and optional experimental height scan separately."""
    if not 1 <= rounds <= 20:
        raise ValueError('rounds must be 1..20')
    if native is not None and not native.is_file():
        raise FileNotFoundError(f'Native scanner missing: {native}')
    results: list[dict] = []
    for radius in radii:
        elapsed = []
        count = None
        for _ in range(rounds):
            start = time.perf_counter()
            count = sum(1 for _ in candidates(seed, radius))
            elapsed.append(time.perf_counter() - start)
        results.append({'backend': 'python_candidate_placement', 'seed': seed,
                        'radius_blocks': radius, 'candidate_count': count,
                        'rounds': rounds, 'elapsed_seconds_median': round(statistics.median(elapsed), 6),
                        'exact_tower_height': False})
        if native is not None:
            elapsed = []
            for _ in range(rounds):
                with tempfile.TemporaryDirectory(prefix='lowy-bench-') as temp:
                    start = time.perf_counter()
                    subprocess.run([str(native.resolve()), '--seed', str(seed),
                                    '--radius', str(radius), '--max-y', '320',
                                    '--skip-biome', '--top', '25',
                                    '--csv', str(Path(temp) / 'hits.csv')],
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                   check=True)
                    elapsed.append(time.perf_counter() - start)
            results.append({'backend': 'native_1_21_8_experimental_terrain', 'seed': seed,
                            'radius_blocks': radius, 'rounds': rounds,
                            'elapsed_seconds_median': round(statistics.median(elapsed), 6),
                            'exact_tower_height': False})
    return results


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description='Measure seed-only candidate and optional approximate terrain performance. No chunk generation or verified Y.')
    parser.add_argument('--seed', type=int, default=123)
    parser.add_argument('--radii', default='8192,32768')
    parser.add_argument('--rounds', type=int, default=3)
    parser.add_argument('--native', type=Path, help='Optional built experimental scanner bin/lowyoutpost')
    args = parser.parse_args(argv)
    try:
        values = benchmark(args.seed, parse_radii(args.radii), rounds=args.rounds,
                           native=args.native)
    except (ValueError, FileNotFoundError, subprocess.CalledProcessError) as exc:
        parser.error(str(exc))
    print(json.dumps(values, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
