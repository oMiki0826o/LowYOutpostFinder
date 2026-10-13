"""File: seed_geometry.py
Modification: 2026-10-13 — exact seed-only placement/Jigsaw start geometry (NO Y claims).

This isolates the provable seed-only stage from noise/biome predictions. A
successful CSV does not prove the structure spawned or reveal its Y coordinate.
"""
from __future__ import annotations

from pathlib import Path

from .cli import candidates, signed_seed, write_csv
from .game_archive import require_matching_game_version
from .placement_assets import validate_placement_assets
from .start_geometry import load_outpost_assets, projection
from .versions import check_version, SUPPORTED

GEOMETRY_FIELDS = ('version', 'seed', 'chunk_x', 'chunk_z', 'x', 'z',
                   'rotation', 'sample_x', 'sample_z', 'template_sha256', 'classification')


def rows_for_seed(seed: int, version: str, radius: int, center_x: int,
                  center_z: int, game_jar: Path):
    """Stream only independently calculable start geometry from this game JAR."""
    check_version(version)
    require_matching_game_version(game_jar, version)
    validate_placement_assets(game_jar)
    asset = load_outpost_assets(game_jar)
    for point in candidates(seed, radius, center_x=center_x, center_z=center_z):
        p = projection(seed, point['chunk_x'], point['chunk_z'], asset.size)
        yield {'version': version, **point, 'rotation': p.rotation,
               'sample_x': p.sample_x, 'sample_z': p.sample_z,
               'template_sha256': asset.sha256,
               'classification': 'seed_geometry_only'}


def run(args) -> None:
    write_csv(args.out, rows_for_seed(args.seed, args.version, args.radius,
                                       args.center_x, args.center_z, args.game_jar),
              GEOMETRY_FIELDS)
    print('Seed geometry calculated, NOT worldgen height: no Y or biome success is claimed.')


def add_command(commands) -> None:
    p = commands.add_parser('seed-geometry',
        help='不生成區塊：精確計算前哨站放置候選及 Jigsaw 起始模板旋轉／高度圖取樣 X/Z（沒有 Y）')
    p.add_argument('--version', choices=sorted(SUPPORTED), default='1.21.8')
    p.add_argument('--seed', type=signed_seed, required=True)
    p.add_argument('--radius', type=int, default=8192)
    p.add_argument('--center-x', type=int, default=0)
    p.add_argument('--center-z', type=int, default=0)
    p.add_argument('--game-jar', type=Path, required=True)
    p.add_argument('--out', type=Path)
    p.set_defaults(run=run)
