"""File: certification.py
Modification: 2026-10-13 — sample-level reproducible provenance and pass/fail gate.

Never promotes a finite comparison to global seed-only equivalence.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from noise_witness import compare_witnesses, read_witnesses
from geometry_audit import write_json_atomic


def _sha(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open('rb') as f:
        for data in iter(lambda: f.read(1024 * 1024), b''):
            digest.update(data)
    return digest.hexdigest()


def certify_samples(witness_file: Path, estimates_csv: Path, *,
                    expected_asset_sha256: str) -> dict:
    observations = read_witnesses(Path(witness_file))
    if not observations:
        raise ValueError('No verified vanilla observations; cannot certify an empty sample set')
    hashes = {str(row['asset_sha256']) for row in observations}
    if hashes != {expected_asset_sha256}:
        raise ValueError('Witnesses do not all match the expected original game asset digest')
    compared, summary = compare_witnesses(observations, Path(estimates_csv))
    no_missing = summary['missing_estimates'] == 0
    matches = bool(compared) and no_missing and summary['maximum_absolute_error'] == 0
    return {
        'minecraft_version': observations[0]['version'],
        'seed': observations[0]['seed'],
        'witness_count': len(observations),
        'game_asset_sha256': expected_asset_sha256,
        'input_sha256': {'witnesses': _sha(Path(witness_file)),
                         'estimates': _sha(Path(estimates_csv))},
        'comparison': summary,
        'all_compared_samples_match': matches,
        'global_exactness_proven': False,
        'status': 'finite_samples_match' if matches else 'finite_samples_mismatch_or_missing',
        'limitations': 'A finite comparison cannot prove ungenerated worldgen, biome, or complete Jigsaw equivalence.',
    }


def run_certification(args) -> None:
    # Incomplete/mismatching samples fail BEFORE touching any previous report.
    from game_archive import require_matching_game_version
    from start_geometry import load_outpost_assets
    observed = read_witnesses(args.witnesses)
    if not observed:
        raise ValueError('No verified vanilla observations; cannot certify an empty sample set')
    version = observed[0]['version']
    require_matching_game_version(args.game_jar, version)
    asset_hash = load_outpost_assets(args.game_jar).sha256
    result = certify_samples(args.witnesses, args.estimates,
                             expected_asset_sha256=asset_hash)
    result['input_sha256']['game_jar'] = _sha(Path(args.game_jar))
    if args.require_matches and not result['all_compared_samples_match']:
        raise ValueError('Vanilla comparison did not match all verified samples')
    if args.out:
        write_json_atomic(args.out, result)
    print(json.dumps(result, ensure_ascii=False, indent=2))


def add_command(commands) -> None:
    parser = commands.add_parser('certify-samples', help='簽核有限原版高度樣本並記錄證據雜湊；不代表全世界精確')
    parser.add_argument('--witnesses', type=Path, required=True)
    parser.add_argument('--estimates', type=Path, required=True)
    parser.add_argument('--game-jar', required=True, type=Path, help='必須提供與見證同版本的原版遊戲 JAR，從中獨立核對資源雜湊')
    parser.add_argument('--out', type=Path)
    parser.add_argument('--require-matches', action='store_true')
    parser.set_defaults(run=run_certification)
