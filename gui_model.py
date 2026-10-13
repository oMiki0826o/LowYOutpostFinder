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
    world: str = ''
    candidates: str = ''
    max_y: str = '0'
    limit: str = '50'
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

    if req.version != 'auto':
        check_version(req.version)
    elif req.mode in ('candidates', 'estimate', 'seed-vanilla'):
        raise ValueError(tr(language, 'error_version_candidates'))
    output = Path(req.out.strip()).expanduser()
    if not req.out.strip() or output.suffix.casefold() != '.csv':
        raise ValueError(tr(language, 'error_out'))
    args = [req.mode, '--version', req.version, '--out', str(output)]
    env = {}
    if req.mode in ('candidates', 'estimate', 'seed-vanilla'):
        from finder import signed_seed
        try:
            seed = signed_seed(req.seed.strip())
        except (ValueError, argparse.ArgumentTypeError) as exc:
            raise ValueError(tr(language, 'error_seed')) from exc
        radius = num(req.radius, 'radius', 0, 30_000_000)
        args += ['--seed', str(seed), '--radius', str(radius)]
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
                     '--timeout', str(num(req.timeout, 'timeout', 5, 3600)),
                     '--startup-timeout', str(num(req.startup_timeout, 'startup_timeout', 20, 1800)),
                     '--memory', str(num(req.memory, 'memory', 1024, 16384)),
                     '--audit', str(output.with_name(output.stem + '-audit.csv'))]
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
                 '--limit', str(limit), '--timeout', str(timeout), '--port', str(port),
                 '--priority', 'near-origin',
                 '--audit', str(output.with_name(output.stem + '-audit.csv'))]
        if req.max_y.strip():
            args += ['--max-y', str(num(req.max_y, 'max_y', -2048, 2048))]
        # Fixed environment variable name not derived from untrusted GUI input.
        env['MINECRAFT_RCON_PASSWORD'] = req.password
    else:
        raise ValueError(tr(language, 'error_mode'))
    return args, env
