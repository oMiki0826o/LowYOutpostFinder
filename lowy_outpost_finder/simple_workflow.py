"""Seed-only low-Y estimated search contract and stable user-facing CSV format."""
from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime
import math
from pathlib import Path
import tempfile
from uuid import uuid4

from .full_map import WORLD_EDGE


PUBLIC_FIELDS = (
    'version', 'seed', 'index', 'x', 'estimated_y', 'z',
    'distance_from_center', 'distance_from_origin', 'chunk_x', 'chunk_z',
    'status',
)


@dataclass(frozen=True)
class SimpleRequest:
    seed: str
    version: str = '1.21.8'
    max_y: str = '-37'
    top: str = '25'
    radius: str = '30000000'
    center_x: str = '0'
    center_z: str = '0'


def _integer(value: str, label: str, low: int, high: int) -> int:
    try:
        if not value.strip() or not value.strip().lstrip('+-').isdigit():
            raise ValueError
        number = int(value)
    except (AttributeError, ValueError, TypeError) as exc:
        raise ValueError(f'{label} must be an integer') from exc
    if not low <= number <= high:
        raise ValueError(f'{label} must be within {low}..{high}')
    return number


def validated_request(req: SimpleRequest) -> dict[str, int]:
    if req.version != '1.21.8':
        raise ValueError('Native estimated height is currently available for Minecraft 1.21.8 only')
    return {
        'seed': _integer(req.seed, 'Seed', -(1 << 63), (1 << 63) - 1),
        'max_y': _integer(req.max_y, 'Structure centre Y', -64, 320),
        'top': _integer(req.top, 'Result count', 1, 10000),
        'radius': _integer(req.radius, 'Radius', 0, 30000000),
        'center_x': _integer(req.center_x, 'Search centre X', -WORLD_EDGE, WORLD_EDGE),
        'center_z': _integer(req.center_z, 'Search centre Z', -WORLD_EDGE, WORLD_EDGE),
    }


def build_search_arguments(req: SimpleRequest, raw_csv: Path) -> list[str]:
    """Build an estimated centre-height nearest search; never use placement-only fallback."""
    q = validated_request(req)
    radius = q['radius']
    return [
        'full-map', '--version', req.version, '--seed', str(q['seed']),
        '--height-engine', 'estimate', '--strategy', 'nearest',
        '--engine', 'native', '--max-y', str(q['max_y']),
        '--top', str(q['top']), '--center-x', str(q['center_x']),
        '--center-z', str(q['center_z']),
        '--x-min', str(max(-WORLD_EDGE, q['center_x'] - radius)),
        '--x-max', str(min(WORLD_EDGE, q['center_x'] + radius)),
        '--z-min', str(max(-WORLD_EDGE, q['center_z'] - radius)),
        '--z-max', str(min(WORLD_EDGE, q['center_z'] + radius)),
        '--threads', '0', '--batch-regions', '500000', '--cpu-rest-ms', '150',
        '--out', str(raw_csv),
    ]


def unique_output_paths(results: Path) -> tuple[Path, Path]:
    """Raw C output is retained separately from the stable eleven-column public CSV."""
    stem = datetime.now().strftime('%Y%m%d-%H%M%S-%f') + '-' + uuid4().hex[:8]
    raw = results / '.engine' / ('estimate-' + stem + '.csv')
    public = results / ('low-y-outposts-' + stem + '.csv')
    return raw, public


def export_results(raw_csv: Path, public_csv: Path, req: SimpleRequest) -> list[dict]:
    """Export only validated estimated heights; never elevate them to verified towers."""
    q = validated_request(req)
    raw_csv, public_csv = Path(raw_csv), Path(public_csv)
    if public_csv.exists():
        raise ValueError('Refusing to overwrite existing result CSV')
    records = []
    positions = set()
    with raw_csv.open('r', newline='', encoding='utf-8-sig') as source:
        reader = csv.DictReader(source)
        required = {'version', 'seed', 'chunk_x', 'chunk_z', 'x', 'z',
                    'projected_structure_center_y', 'classification'}
        if not required.issubset(set(reader.fieldnames or [])):
            raise ValueError('Native scan returned an incomplete CSV schema')
        for row in reader:
            try:
                cx, cz = int(row['chunk_x']), int(row['chunk_z'])
                x, z = int(row['x']), int(row['z'])
                y = int(row['projected_structure_center_y'])
                seed = int(row['seed'])
            except (TypeError, ValueError, KeyError) as exc:
                raise ValueError('Native scan returned malformed coordinate data') from exc
            if (row['version'] != req.version or seed != q['seed']
                    or row['classification'] != 'estimated_only'
                    or x != cx * 16 or z != cz * 16
                    or y >= q['max_y']
                    or abs(x - q['center_x']) > q['radius']
                    or abs(z - q['center_z']) > q['radius']
                    or not (-WORLD_EDGE <= x <= WORLD_EDGE and
                            -WORLD_EDGE <= z <= WORLD_EDGE)
                    or (cx, cz) in positions):
                raise ValueError('Native estimate failed version, coordinate, Y or evidence checks')
            positions.add((cx, cz))
            records.append({
                'version': req.version, 'seed': seed, 'x': x,
                'estimated_y': y, 'z': z,
                'distance_from_center': f"{math.hypot(x-q['center_x'], z-q['center_z']):.2f}",
                'distance_from_origin': f"{math.hypot(x, z):.2f}",
                'chunk_x': cx, 'chunk_z': cz, 'status': 'estimated_only',
            })
            if len(records) > q['top']:
                raise ValueError('Native engine returned too many results')
    records.sort(key=lambda row: (float(row['distance_from_center']),
                                  row['x'], row['z']))
    for i, row in enumerate(records, 1):
        row['index'] = i
    public_csv.parent.mkdir(parents=True, exist_ok=True)
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(
                mode='w', encoding='utf-8', newline='',
                prefix='.' + public_csv.stem + '-', suffix='.tmp',
                dir=public_csv.parent, delete=False) as tmp:
            temp_path = Path(tmp.name)
            writer = csv.DictWriter(tmp, fieldnames=PUBLIC_FIELDS)
            writer.writeheader()
            writer.writerows(records)
        if public_csv.exists():
            raise ValueError('Refusing to overwrite existing result CSV')
        temp_path.replace(public_csv)
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)
    return records
