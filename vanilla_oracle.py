"""File: vanilla_oracle.py
Modification: 2026-10-12 — isolated, on-demand vanilla verification from a seed.

This is NOT a mathematical/no-generation terrain predictor. The official
Minecraft Java server must generate chunks. Only original saved Jigsaw
bounding boxes can be reported as verified Y values.
"""
from __future__ import annotations

from contextlib import contextmanager
import csv
import json
import os
import re
from pathlib import Path
import secrets
import signal
import socket
import subprocess
import sys
import tempfile
import time
import zipfile

from versions import check_version
from game_archive import declared_game_version


class VanillaStartupError(RuntimeError):
    """A temporary vanilla server failed to start or shut down safely."""


def verify_bundle(server_jar: Path, version: str) -> str:
    """Reject JARs whose declared Minecraft version cannot be identified.

    This is a version *consistency* check, not a digital signature and not a
    guarantee that a file is an unmodified official Mojang distribution.
    """
    check_version(version)
    if not server_jar.is_file():
        raise ValueError(f'Server JAR not found: {server_jar}')
    try:
        with zipfile.ZipFile(server_jar) as jar:
            paths = jar.namelist()
            bundles = [p.split('/')[2] for p in paths
                       if p.startswith('META-INF/versions/') and
                       p.endswith('.jar') and len(p.split('/')) == 4]
            if len(set(bundles)) == 1:
                found = bundles[0]
            elif 'version.json' in paths:
                meta = json.loads(jar.read('version.json').decode('utf-8'))
                found = meta.get('id')
            else:
                raise ValueError('Cannot identify the Minecraft version in server JAR; use an official versioned JAR')
    except (zipfile.BadZipFile, zipfile.LargeZipFile) as exc:
        raise ValueError('Server JAR is not a valid Java archive') from exc
    if found != version:
        raise ValueError(f'Server JAR version mismatch: {found!r} != requested {version!r}')
    return str(found)


def ensure_compatible_java(command: str, jar_metadata: dict | None) -> int:
    """Fail before world creation if the selected Java cannot load this server.

    The bundled Mojang version.json declares its minimum required Java release.
    This does not establish the entire runtime's fitness for game execution.
    """
    try:
        result = subprocess.run([command, '-version'], capture_output=True,
                                text=True, timeout=15, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ValueError(f'Cannot run Java executable {command!r}: {exc}') from exc
    output = (result.stderr or '') + '\n' + (result.stdout or '')
    match = re.search(r'(?:openjdk|java) version "(\d+)(?:[.\-_]|"|\+)', output, re.IGNORECASE)
    if result.returncode or not match:
        raise ValueError(f'Cannot identify Java runtime from {command!r} -version')
    major = int(match.group(1))
    if major == 1:  # Legacy 1.8 etc. are never suitable for Minecraft 1.21+.
        raise ValueError('Unsupported Java runtime; use a modern Java release')
    required = jar_metadata.get('java_version') if jar_metadata else None
    if type(required) is int and major < required:
        raise ValueError(f'This server requires Java {required} or later, '
                         f'but {command!r} is Java {major}. Select a matching Java binary with --java.')
    return major


def server_properties(seed: int, password: str, server_port: int, rcon_port: int) -> str:
    """Confine both Minecraft and RCON to loopback, without a public listener."""
    return '\n'.join((
        '# Generated in a temporary directory by LowYOutpostFinder',
        'level-name=world', f'level-seed={seed}',
        'level-type=minecraft:normal',
        'server-ip=127.0.0.1', f'server-port={server_port}',
        'enable-rcon=true', 'broadcast-rcon-to-ops=false',
        f'rcon.port={rcon_port}', f'rcon.password={password}',
        'enable-query=false', 'white-list=true',
        'view-distance=2', 'simulation-distance=2',
        'spawn-protection=0', 'max-players=1',
        'motd=LowYOutpostFinder temporary test',
        '',
    ))


def _unused_port() -> int:
    with socket.socket() as connection:
        connection.bind(('127.0.0.1', 0))
        return connection.getsockname()[1]


def classify_run(statuses: list[str]) -> dict[str, object]:
    """Only actual tower NBT is verified. A finite scan never proves a global minimum."""
    successes = sum(status == 'verified_tower' for status in statuses)
    incomplete = any(s in ('timeout', 'not_full', 'not_generated', 'invalid_region',
                           'invalid_nbt', 'version_mismatch') for s in statuses)
    confidence = ('incomplete' if incomplete else
                  'verified' if successes and successes == len(statuses) else
                  'partial' if successes else 'no_confirmed_towers')
    return {'confidence': confidence, 'confirmed_towers': successes,
            'checked': len(statuses), 'contains_incomplete': incomplete}


def _tail_log(log_file: Path) -> str:
    try:
        # Do not expose any generated temporary credentials in user-visible logs.
        content = log_file.read_text(encoding='utf-8', errors='replace')
        return '\n'.join(content.splitlines()[-12:])[:2500]
    except OSError:
        return '<log unavailable>'


def _wait_ready(process: subprocess.Popen, folder: Path, port: int, seconds: int) -> None:
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        if process.poll() is not None:
            raise VanillaStartupError(f'Vanilla server exited with code {process.returncode}. '
                                      f'Last server output:\n{_tail_log(folder / "server.log")}')
        if (folder / 'world' / 'level.dat').is_file() and (folder / 'world' / 'region').is_dir():
            try:
                with socket.create_connection(('127.0.0.1', port), timeout=1):
                    return
            except OSError:
                pass
        time.sleep(0.5)
    raise VanillaStartupError(f'Vanilla server startup exceeded {seconds} seconds. '
                              f'Last server output:\n{_tail_log(folder / "server.log")}')


def _stop_server(process: subprocess.Popen, port: int, password: str) -> None:
    if process.poll() is not None:
        return
    try:
        from live import RCON
        with RCON('127.0.0.1', port, password) as server:
            server.command('stop')
    except (OSError, RuntimeError, ValueError):
        # The server may not yet have finished booting. Terminate below.
        pass
    try:
        process.wait(timeout=35)
    except subprocess.TimeoutExpired:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)


@contextmanager
def _trap_termination():
    """Convert GUI SIGTERM into unwind to ensure the child server is stopped."""
    previous = None
    if hasattr(signal, 'SIGTERM'):
        previous = signal.getsignal(signal.SIGTERM)
        def stop(_signum, _frame):
            raise KeyboardInterrupt('Vanilla search cancelled')
        signal.signal(signal.SIGTERM, stop)
    try:
        yield
    finally:
        if previous is not None:
            signal.signal(signal.SIGTERM, previous)


def run_vanilla(args) -> None:
    """Generate an isolated throwaway world and extract actual saved NBT Y.

    An experimental terrain oracle never filters out possible real outposts.
    Verified results survive the deletion of the temporary world as CSV.
    """
    if not args.eula_accepted:
        raise ValueError('Minecraft EULA acceptance is required (explicit --eula-accepted)')
    check_version(args.version)
    if not 0 <= args.radius <= 30_000_000 or not 1 <= args.limit <= 256:
        raise ValueError('radius must be 0..30000000 and limit must be 1..256')
    if not 5 <= args.timeout <= 3600 or not 20 <= args.startup_timeout <= 1800:
        raise ValueError('timeout must be 5..3600 and startup-timeout must be 20..1800')
    if not 1024 <= args.memory <= 16384:
        raise ValueError('memory must be in 1024..16384 MiB')
    priority = getattr(args, 'priority', 'near-origin')
    if priority not in ('near-origin', 'terrain'):
        raise ValueError('priority must be near-origin or terrain')
    if priority == 'terrain' and args.version != '1.21.8':
        raise ValueError('Terrain priority is experimental and only supported for 1.21.8')
    jar = Path(args.server_jar).expanduser().resolve(strict=True)
    verify_bundle(jar, args.version)
    from finder import candidates, run_search_live
    # Validate search size before any world generation or output modification.
    if next(candidates(args.seed, args.radius), None) is None:
        raise ValueError('No placement candidates within this radius; expand --radius')
    if args.out is None:
        raise ValueError('A .csv output path is required')
    if not str(args.out).lower().endswith('.csv'):
        raise ValueError('Output path must end in .csv')
    ensure_compatible_java(args.java, declared_game_version(jar))
    print(f'Preparing temporary vanilla world: Minecraft {args.version}, seed={args.seed}', file=sys.stderr)
    with _trap_termination(), tempfile.TemporaryDirectory(prefix='lowyoutpost-vanilla-') as temp:
        root = Path(temp)
        password = secrets.token_urlsafe(32)
        server_port = _unused_port()
        rcon_port = _unused_port()
        if rcon_port == server_port:
            rcon_port = _unused_port()
        (root / 'server.properties').write_text(server_properties(args.seed, password,
                                    server_port, rcon_port), encoding='utf-8')
        (root / 'eula.txt').write_text('# User explicitly accepted the EULA for this run\neula=true\n',
                                      encoding='utf-8')
        with (root / 'server.log').open('wb') as log:
            process = subprocess.Popen([args.java, f'-Xmx{args.memory}M', '-jar',
                                        str(jar), 'nogui'], cwd=root,
                                       stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT)
            try:
                _wait_ready(process, root, rcon_port, args.startup_timeout)
                from types import SimpleNamespace
                # Existing live command handles seed check, candidate selection,
                # force-load ownership, saved FULL status, and audit rows.
                options = SimpleNamespace(**vars(args))
                options.world = root / 'world'
                options.host = '127.0.0.1'
                options.port = rcon_port
                options.password_env = 'LOWYOUTPOST_TEMP_RCON'
                options.allow_remote = False
                options.priority = priority
                options.core_archive = getattr(args, 'core_archive', None)
                if priority == 'terrain':
                    print('Experimental terrain ranking: approximations may omit real low-Y outposts.', file=sys.stderr)
                if args.audit is None:
                    options.audit = args.out.with_name(args.out.stem + '-audit.csv')
                old_password = os.environ.get('LOWYOUTPOST_TEMP_RCON')
                os.environ['LOWYOUTPOST_TEMP_RCON'] = password
                try:
                    run_search_live(options)
                    with options.audit.open(encoding='utf-8', newline='') as audit_fp:
                        audit_rows = list(csv.DictReader(audit_fp))
                    report = classify_run([row['status'] for row in audit_rows])
                    print(f"Audited {report['checked']} candidate(s): "
                          f"{report['confirmed_towers']} saved towers; "
                          f"sample_status={report['confidence']}. "
                          'This sample does not establish the global lowest Y.',
                          file=sys.stderr)
                finally:
                    if old_password is None:
                        os.environ.pop('LOWYOUTPOST_TEMP_RCON', None)
                    else:
                        os.environ['LOWYOUTPOST_TEMP_RCON'] = old_password
            finally:
                _stop_server(process, rcon_port, password)
    print('Temporary Minecraft world removed; verified CSV and audit CSV preserved.', file=sys.stderr)


def add_vanilla_command(commands) -> None:
    from finder import signed_seed
    from versions import SUPPORTED
    parser = commands.add_parser('seed-vanilla', help='從種子建立暫存原版世界、生成區塊，再讀取實際結構 Y；非免生成模擬')
    parser.add_argument('--version', choices=sorted(SUPPORTED), required=True)
    parser.add_argument('--seed', type=signed_seed, required=True)
    parser.add_argument('--radius', type=int, default=8192)
    parser.add_argument('--limit', type=int, default=50)
    parser.add_argument('--center-y-below', type=float, default=-37,
                        help='找到最近的已驗證前哨站結構中心低於此 Y 後停止')
    parser.add_argument('--timeout', type=int, default=180)
    parser.add_argument('--startup-timeout', type=int, default=300)
    parser.add_argument('--memory', type=int, default=2048, help='最大 Java heap MiB')
    parser.add_argument('--server-jar', type=Path, required=True, help='自行提供與版號一致的原版 server.jar')
    parser.add_argument('--java', default='java', help='已安裝的 Java 執行檔')
    parser.add_argument('--eula-accepted', action='store_true', help='必須自行閱讀並明確同意 Minecraft EULA')
    parser.add_argument('--max-y', type=int)
    parser.add_argument('--audit', type=Path, help='保留所有候選的檢查紀錄（含未生成／無結構）')
    parser.add_argument('--priority', choices=['near-origin', 'terrain'], default='near-origin',
                        help='種子原版驗證優先順序：最近候選／1.21.8 試驗性低地形排序（可能漏掉低 Y）')
    parser.add_argument('--core-archive', type=Path, help='terrain 排序需提供的 LowYSwampHut 2.0.1 原始碼')
    parser.add_argument('--game-jar', type=Path, help='遊戲資源 JAR，供 terrain 起始模板旋轉定位')
    parser.add_argument('--out', type=Path, required=True)
    parser.set_defaults(run=run_vanilla)
