"""File: gui_model.py
Modification: 2026-10-12 — validated, testable commands for desktop workflows.
"""
from __future__ import annotations

from dataclasses import dataclass
import argparse
from pathlib import Path

from versions import check_version
from i18n import tr


@dataclass(frozen=True)
class SearchRequest:
    mode: str
    version: str = '1.21.8'
    seed: str = '123'
    radius: str = '8192'
    center_x: str = '0'
    center_z: str = '0'
    world: str = ''
    candidates: str = ''
    max_y: str = '0'
    center_y_below: str = '-37'
    limit: str = '50'
    offset: str = '0'
    timeout: str = '180'
    port: str = '25575'
    password: str = ''
    out: str = ''
    top: str = '25'
    core_archive: str = ''
    game_jar: str = ''
    server_jar: str = ''
    eula_accepted: bool = False
    memory: str = '2048'
    startup_timeout: str = '300'
    java: str = 'java'
    priority: str = 'near-origin'
    sort_by: str = 'distance'
    scan_strategy: str = 'nearest'
    scan_engine: str = 'auto'
    batch_regions: str = '500000'
    cpu_rest_ms: str = '150'
    resume: bool = False


def natural_number(value: str, label: str, least: int, most: int, *, language: str = 'zh-TW') -> int:
    try:
        number = int(value.strip(), 10)
    except ValueError as exc:
        raise ValueError(tr(language, 'error_integer', label=label)) from exc
    if number < least or number > most:
        raise ValueError(tr(language, 'error_range', label=label, least=least, most=most))
    return number


def build_arguments(req: SearchRequest, *, language: str = 'zh-TW') -> tuple[list[str], dict[str, str]]:
    """Return finder CLI argv, plus secret-only env overrides.

    The GUI never writes the RCON password to command line, disk, or settings.
    """
    def num(value, key, minimum, maximum):
        return natural_number(value, tr(language, 'label_' + key), minimum, maximum, language=language)

    if req.sort_by not in ('distance', 'base-y', 'tower-y'):
        raise ValueError('Invalid verified-result sort order')
    if req.version != 'auto':
        check_version(req.version)
    elif req.mode in ('candidates', 'estimate', 'seed-vanilla', 'seed-geometry', 'full-map'):
        raise ValueError(tr(language, 'error_version_candidates'))
    output = Path(req.out.strip()).expanduser()
    if not req.out.strip() or output.suffix.casefold() != '.csv':
        raise ValueError(tr(language, 'error_out'))
    args = [req.mode, '--version', req.version, '--out', str(output)]
    env = {}
    if req.mode == 'full-map':
        from finder import signed_seed
        try:
            seed = signed_seed(req.seed.strip())
        except (ValueError, argparse.ArgumentTypeError) as exc:
            raise ValueError(tr(language, 'error_seed')) from exc
        if req.scan_strategy not in ('nearest', 'exhaustive'):
            raise ValueError('scan_strategy must be nearest or exhaustive')
        if req.scan_engine not in ('auto', 'python', 'native'):
            raise ValueError('scan_engine must be auto, python or native')
        if req.resume and req.scan_strategy != 'exhaustive':
            raise ValueError('Resume is available only for exhaustive scans')
        args += ['--seed', str(seed),
                 '--center-x', str(num(req.center_x, 'center_x', -29_999_984, 29_999_984)),
                 '--center-z', str(num(req.center_z, 'center_z', -29_999_984, 29_999_984)),
                 '--top', str(num(req.top, 'top', 1, 10000)),
                 '--strategy', req.scan_strategy, '--engine', req.scan_engine,
                 '--batch-regions', str(num(req.batch_regions, 'batch_regions', 1, 5_000_000)),
                 '--cpu-rest-ms', str(num(req.cpu_rest_ms, 'cpu_rest_ms', 0, 5000))]
        if req.resume:
            args.append('--resume')
        return args, env
    if req.mode in ('candidates', 'estimate', 'seed-vanilla'):
        from finder import signed_seed
        try:
            seed = signed_seed(req.seed.strip())
        except (ValueError, argparse.ArgumentTypeError) as exc:
            raise ValueError(tr(language, 'error_seed')) from exc
        radius = num(req.radius, 'radius', 0, 30_000_000)
        args += ['--seed', str(seed), '--radius', str(radius)]
        if req.mode in ('candidates', 'seed-vanilla'):
            args += ['--center-x', str(num(req.center_x, 'center_x', -30_000_000, 30_000_000)),
                     '--center-z', str(num(req.center_z, 'center_z', -30_000_000, 30_000_000))]
        if req.mode == 'seed-vanilla':
            if req.priority not in ('near-origin', 'terrain'):
                raise ValueError(tr(language, 'error_priority'))
            if req.priority == 'terrain' and req.version != '1.21.8':
                raise ValueError(tr(language, 'error_priority_version'))
            if not req.eula_accepted:
                raise ValueError(tr(language, 'error_eula'))
            if not req.server_jar.strip():
                raise ValueError(tr(language, 'error_server_jar'))
            args += ['--server-jar', str(Path(req.server_jar).expanduser()), '--eula-accepted',
                     '--priority', req.priority,
                     '--java', req.java.strip() or 'java',
                     '--limit', str(num(req.limit, 'limit', 1, 256)),
                     '--offset', str(num(req.offset, 'offset', 0, 100_000)),
                     '--timeout', str(num(req.timeout, 'timeout', 5, 3600)),
                     '--startup-timeout', str(num(req.startup_timeout, 'startup_timeout', 20, 1800)),
                     '--memory', str(num(req.memory, 'memory', 1024, 16384)),
                     '--audit', str(output.with_name(output.stem + '-audit.csv')),
                     '--checkpoint', str(output.with_name(output.stem + '-progress.csv')),
                     '--summary', str(output.with_name(output.stem + '-summary.json')),
                     '--sort-by', req.sort_by,
                     '--center-y-below', str(num(req.center_y_below, 'center_y_below', -2048, 2048))]
            if req.priority == 'terrain' and req.core_archive.strip():
                args += ['--core-archive', str(Path(req.core_archive).expanduser())]
            if req.priority == 'terrain' and req.game_jar.strip():
                args += ['--game-jar', str(Path(req.game_jar).expanduser())]
            if req.max_y.strip():
                args += ['--max-y', str(num(req.max_y, 'max_y', -2048, 2048))]
        if req.mode == 'estimate':
            if req.version != '1.21.8':
                raise ValueError(tr(language, 'error_estimate_version'))
            args += ['--max-y', str(num(req.max_y, 'max_y', -64, 320)),
                     '--top', str(num(req.top, 'top', 1, 100000))]
            if req.core_archive.strip():
                args += ['--core-archive', str(Path(req.core_archive).expanduser())]
            if req.game_jar.strip():
                args += ['--game-jar', str(Path(req.game_jar).expanduser())]
    elif req.mode == 'seed-geometry':
        from finder import signed_seed
        try:
            seed = signed_seed(req.seed.strip())
        except (ValueError, argparse.ArgumentTypeError) as exc:
            raise ValueError(tr(language, 'error_seed')) from exc
        if not req.game_jar.strip():
            raise ValueError(tr(language, 'error_game_jar_required'))
        args += ['--seed', str(seed), '--radius', str(num(req.radius, 'radius', 0, 30_000_000)),
                 '--center-x', str(num(req.center_x, 'center_x', -30_000_000, 30_000_000)),
                 '--center-z', str(num(req.center_z, 'center_z', -30_000_000, 30_000_000)),
                 '--game-jar', str(Path(req.game_jar).expanduser())]
    elif req.mode == 'world':
        if not req.world.strip():
            raise ValueError(tr(language, 'error_world'))
        args += ['--world', str(Path(req.world).expanduser())]
        if req.max_y.strip():
            args += ['--max-y', str(num(req.max_y, 'max_y', -2048, 2048))]
    elif req.mode == 'verify':
        if not req.world.strip() or not req.candidates.strip():
            raise ValueError(tr(language, 'error_verify'))
        args += ['--world', str(Path(req.world).expanduser()),
                 '--candidates', str(Path(req.candidates).expanduser())]
    elif req.mode == 'search-live':
        if not req.world.strip():
            raise ValueError(tr(language, 'error_world'))
        if not req.password:
            raise ValueError(tr(language, 'error_password'))
        radius = num(req.radius, 'radius', 0, 30_000_000)
        limit = num(req.limit, 'limit', 1, 256)
        timeout = num(req.timeout, 'timeout', 5, 3600)
        port = num(req.port, 'port', 1, 65535)
        args += ['--world', str(Path(req.world).expanduser()), '--radius', str(radius),
                 '--center-x', str(num(req.center_x, 'center_x', -30_000_000, 30_000_000)),
                 '--center-z', str(num(req.center_z, 'center_z', -30_000_000, 30_000_000)),
                 '--limit', str(limit), '--offset', str(num(req.offset, 'offset', 0, 100_000)),
                 '--timeout', str(timeout), '--port', str(port),
                 '--priority', 'near-origin',
                 '--audit', str(output.with_name(output.stem + '-audit.csv')),
                 '--checkpoint', str(output.with_name(output.stem + '-progress.csv')),
                 '--summary', str(output.with_name(output.stem + '-summary.json')),
                 '--sort-by', req.sort_by]
        if req.max_y.strip():
            args += ['--max-y', str(num(req.max_y, 'max_y', -2048, 2048))]
        args += ['--center-y-below', str(num(req.center_y_below, 'center_y_below', -2048, 2048))]
        # Fixed environment variable name not derived from untrusted GUI input.
        env['MINECRAFT_RCON_PASSWORD'] = req.password
    else:
        raise ValueError(tr(language, 'error_mode'))
    return args, env
