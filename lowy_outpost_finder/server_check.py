"""File: server_check.py
Modification: 2026-10-13 — original game JAR and Java preflight without world generation.

This check does not start Minecraft, accept an EULA, or authenticate JAR origin.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from game_archive import declared_game_version
from geometry_audit import write_json_atomic
from placement_assets import validate_placement_assets
from vanilla_oracle import ensure_compatible_java, verify_bundle
from versions import SUPPORTED


def preflight(jar: Path, version: str, java: str) -> dict:
    """Fail before server launch if version, placement or runtime is incompatible."""
    verify_bundle(jar, version)
    info = declared_game_version(jar)
    required = info.get('java_version') if info else None
    major = ensure_compatible_java(java, info)
    placement = validate_placement_assets(jar)
    digest = hashlib.sha256()
    with jar.open('rb') as source:
        for block in iter(lambda: source.read(1024 * 1024), b''):
            digest.update(block)
    return {
        'game_version': version,
        'java_runtime': major,
        'java_required': required,
        'bundle_sha256': digest.hexdigest(),
        'placement_parameters_match': placement.supported,
        'outpost_placement_sha256': placement.outpost_sha256,
        'village_placement_sha256': placement.villages_sha256,
        'vanilla_world_generated': False,
        'exact_seed_only_height_ready': False,
        'notes': 'Preflight only: metadata and structure-set constants. Does not accept EULA, '
                 'execute Java game code, generate world, verify biome/noise/Jigsaw or sign authenticity.',
    }


def run(args) -> None:
    record = preflight(args.server_jar, args.version, args.java)
    if args.out:
        write_json_atomic(args.out, record)
    else:
        print(json.dumps(record, ensure_ascii=False, indent=2))


def add_command(commands) -> None:
    p = commands.add_parser('server-check', help='唯讀檢查伺服器 JAR 版本／原版放置參數／Java 執行環境；不生成世界')
    p.add_argument('--version', required=True, choices=sorted(SUPPORTED))
    p.add_argument('--server-jar', type=Path, required=True)
    p.add_argument('--java', default='java')
    p.add_argument('--out', type=Path, help='JSON 報告，省略則輸出到終端機')
    p.set_defaults(run=run)
