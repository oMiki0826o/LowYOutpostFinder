"""File: height_audit.py
Modification: 2026-10-12 — strictly compare seed-only estimates to saved vanilla towers.

An exact match for a finite sample is NOT proof the model is generally exact.
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


REQUIRED_ESTIMATE = {'version', 'seed', 'chunk_x', 'chunk_z', 'projected_surface_y', 'classification'}
REQUIRED_VERIFIED = {'version', 'seed', 'chunk_x', 'chunk_z', 'base_plate_y', 'status'}


def read_rows(path: Path, required: set[str]):
    with path.open('r', newline='', encoding='utf-8-sig') as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames or not required <= set(reader.fieldnames):
            raise ValueError(f'Missing required CSV columns in {path}: {sorted(required - set(reader.fieldnames or []))}')
        return list(reader)


def _identity(rows: list[dict], label: str) -> tuple[str, int]:
    if not rows:
        raise ValueError(f'{label} is empty; cannot compare heights')
    identities = set()
    for row in rows:
        identities.add((row['version'], int(row['seed'])))
    if len(identities) != 1:
        raise ValueError(f'{label} contains multiple versions or seeds')
    return identities.pop()


def compare_heights(estimated_csv: Path, verified_csv: Path) -> dict:
    """Calculate observed errors against saved base plate Y without claiming exactness."""
    estimates = read_rows(estimated_csv, REQUIRED_ESTIMATE)
    observed = read_rows(verified_csv, REQUIRED_VERIFIED)
    version_seed = _identity(estimates, 'estimate CSV')
    if version_seed != _identity(observed, 'verified CSV'):
        raise ValueError('CSV seed/version mismatch')
    positions = {}
    for row in estimates:
        if row['classification'] != 'estimated_only':
            raise ValueError('estimate CSV must contain estimated_only rows')
        position = (int(row['chunk_x']), int(row['chunk_z']))
        if position in positions:
            raise ValueError(f'duplicate estimated chunk coordinates: {position}')
        positions[position] = int(row['projected_surface_y'])
    verified_positions = set()
    errors = []
    missing_estimate = 0
    skipped = 0
    for row in observed:
        position = (int(row['chunk_x']), int(row['chunk_z']))
        if position in verified_positions:
            raise ValueError(f'duplicate verified chunk coordinates: {position}')
        verified_positions.add(position)
        if row['status'] != 'verified_tower' or not row['base_plate_y']:
            skipped += 1
            continue
        if position not in positions:
            missing_estimate += 1
            continue
        errors.append(positions[position] - int(row['base_plate_y']))
    count = len(errors)
    return {
        'version': version_seed[0], 'seed': version_seed[1],
        'estimate_count': len(estimates), 'verified_rows': len(observed),
        'matched_verified': count,
        'missing_estimate': missing_estimate,
        'skipped_not_verified': skipped,
        'mean_absolute_error': sum(abs(err) for err in errors)/count if count else None,
        'maximum_absolute_error': max(map(abs, errors)) if count else None,
        'mean_signed_error': sum(errors)/count if count else None,
        'exact_matches': sum(err == 0 for err in errors),
        # Finite comparisons never prove all worldgen cases.
        'estimator_proven_exact': False,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description='Audit projected surface Y against verified tower base Y (not a proof of global exactness)')
    parser.add_argument('--estimated', required=True, type=Path)
    parser.add_argument('--verified', required=True, type=Path)
    parser.add_argument('--out', type=Path)
    args = parser.parse_args(argv)
    try:
        report = compare_heights(args.estimated, args.verified)
    except (ValueError, OSError, csv.Error) as exc:
        parser.error(str(exc))
    result = json.dumps(report, indent=2, ensure_ascii=False) + '\n'
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(result, encoding='utf-8')
    else:
        print(result, end='')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
