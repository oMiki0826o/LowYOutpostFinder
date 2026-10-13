"""File: live.py
Modification: 2026-10-12 — optional read-only-by-default world checking with vanilla RCON.

The generation mode loads one candidate origin chunk at a time, flushes saves,
reads its original structure NBT, and releases only newly force-loaded chunks.
Requires an existing same-version vanilla server and explicit authorization.
"""
from __future__ import annotations

import os
from pathlib import Path
import re
import signal
import threading
import socket
import struct
import sys
import time

from .cli import FIELDS, WorldChunks, confirmed_world, examine, is_candidate_start, load_candidates, write_csv


class RCONError(RuntimeError):
    pass


class RCON:
    def __init__(self, host: str, port: int, password: str):
        self.connection = socket.create_connection((host, port), timeout=10)
        self.connection.settimeout(15)
        try:
            self.send(13, 3, password)
            # Some servers send an empty packet before the authentication result.
            for _ in range(3):
                rid, kind, _body = self.receive()
                if kind == 2:
                    if rid != 13:
                        raise RCONError('Server rejected RCON authentication')
                    break
            else:
                raise RCONError('No RCON authentication response')
        except Exception:
            self.close()
            raise

    def close(self):
        self.connection.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    def exact(self, n: int) -> bytes:
        output = bytearray()
        while len(output) < n:
            data = self.connection.recv(n - len(output))
            if not data:
                raise RCONError('RCON connection closed unexpectedly')
            output.extend(data)
        return bytes(output)

    def receive(self):
        length, = struct.unpack('<i', self.exact(4))
        if not 10 <= length <= 1024 * 1024:
            raise RCONError('Invalid RCON response size')
        packet = self.exact(length)
        rid, kind = struct.unpack_from('<ii', packet)
        if packet[-2:] != b'\0\0':
            raise RCONError('Malformed RCON response')
        return rid, kind, packet[8:-2].decode('utf-8', 'replace')

    def send(self, request_id: int, kind: int, body: str):
        contents = struct.pack('<ii', request_id, kind) + body.encode('utf-8') + b'\0\0'
        self.connection.sendall(struct.pack('<i', len(contents)) + contents)

    def command(self, command: str) -> str:
        self.send(23, 2, command)
        rid, _kind, text = self.receive()
        if rid != 23:
            raise RCONError('Wrong RCON response id; command result cannot be trusted')
        return text


def query_marked(text: str) -> bool | None:
    """Match known vanilla English /forceload query variants; otherwise be safe."""
    response = re.sub(r'§.', '', text).casefold()
    if ('not marked' in response or 'not force loaded' in response or
            'not forceloaded' in response or 'not loaded' in response):
        return False
    if ('marked' in response or 'force loaded' in response or 'forceloaded' in response):
        return True
    return None


def _graceful_stop(_signum, _frame):
    raise KeyboardInterrupt('Stopped; releasing newly added force-load entries')


def run_live(args):
    """Restore process-global SIGTERM behavior after live verification finishes."""
    change_handler = hasattr(signal, 'SIGTERM') and threading.current_thread() is threading.main_thread()
    previous = signal.getsignal(signal.SIGTERM) if change_handler else None
    if change_handler:
        signal.signal(signal.SIGTERM, _graceful_stop)
    try:
        return _run_live(args)
    finally:
        if change_handler:
            signal.signal(signal.SIGTERM, previous)


def check_checkpoint_path(checkpoint: Path | None, output: Path | None) -> None:
    """Avoid colliding with the final result file during interrupted searches."""
    if checkpoint is not None and output is not None and Path(checkpoint).resolve() == Path(output).resolve():
        raise ValueError('checkpoint path must differ from output path')


def _run_live(args):
    password = os.environ.get(args.password_env)
    if not password:
        raise ValueError(f'No RCON password in environment variable {args.password_env}')
    if args.host not in ('127.0.0.1', 'localhost', '::1') and not args.allow_remote:
        raise ValueError('Remote RCON transmits passwords without encryption. Use a local connection or a secured tunnel.')
    _info, seed = confirmed_world(args.world, getattr(args, 'version', 'auto'))
    data_version = _info['DataVersion']
    from .versions import detect_world_version
    version_name, _ = detect_world_version(_info)
    selection = load_candidates(args.candidates, seed, version_name)
    for _, cx, cz in selection[:args.limit]:
        if not is_candidate_start(seed, cx, cz):
            raise ValueError(f'CSV contains a non-candidate start at chunk {cx},{cz}; refusing to generate')
    if not 1 <= args.limit <= 256 or args.timeout < 5:
        raise ValueError('--limit must be between 1 and 256 and --timeout >= 5')
    from .search_conditions import accepted_tower
    checkpoint = getattr(args, 'checkpoint', None)
    check_checkpoint_path(checkpoint, args.out)
    out = []

    def record(row):
        out.append(row)
        if checkpoint is not None:
            # The checkpoint is a provisional audit, not a completion certificate.
            # Recheck saved NBT on restart; never trust a checkpoint as vanilla evidence.
            write_csv(Path(checkpoint), (dict(version=version_name, **r) for r in out), FIELDS)
    with WorldChunks(args.world) as saved, RCON(args.host, args.port, password) as server:
        seed_reply = re.sub(r'§.', '', server.command('seed'))
        seed_match = re.search(r'\bSeed\s*:\s*\[?(-?\d+)\]?', seed_reply, re.I)
        if seed_match is None or int(seed_match[1]) != seed:
            raise RCONError('RCON server seed does not match the selected world, or cannot be verified. Refusing to generate chunks.')
        if checkpoint is not None:
            # This file belongs to the current run. The persistent world, not
            # a stale CSV from a different run, is the resume evidence.
            write_csv(Path(checkpoint), [], FIELDS)
        for number, (_, cx, cz) in enumerate(selection[:args.limit], 1):
            x, z = cx * 16, cz * 16
            command_pos = f'{x} {z}'
            saved.close()
            try:
                previous = examine(saved.get(cx, cz), seed, cx, cz, data_version=data_version)
            except (OSError, ValueError) as exc:
                raise RCONError(f'Failed to read cached origin chunk {command_pos}: {exc}') from exc
            if previous['status'] not in ('not_generated', 'not_full'):
                record(previous)
                print(f'[{number}/{min(len(selection), args.limit)}] {cx},{cz} : '
                      f'{previous["status"]} (already saved)', file=sys.stderr)
                if accepted_tower(previous, center_below=getattr(args, 'stop_center_y_below', None),
                                  max_y=getattr(args, 'stop_max_y', None)) and (
                                      getattr(args, 'stop_center_y_below', None) is not None):
                    break
                continue
            already = query_marked(server.command(f'execute in minecraft:overworld run forceload query {command_pos}'))
            if already is None:
                raise RCONError(f'Unrecognized /forceload query response; no changes made: {command_pos}')
            loaded_by_us = False
            try:
                if not already:
                    response = server.command(f'execute in minecraft:overworld run forceload add {command_pos}')
                    # Cleanup is guaranteed even if the second query fails.
                    loaded_by_us = True
                    now_marked = query_marked(server.command(f'execute in minecraft:overworld run forceload query {command_pos}'))
                    if now_marked is not True:
                        raise RCONError(f'Cannot verify force-load for {command_pos}: {response}')
                deadline = time.monotonic() + args.timeout
                row = None
                while time.monotonic() < deadline:
                    response = server.command('save-all flush')
                    # A chunk might still be generating asynchronously when flush runs.
                    # Disk-only verification avoids mistaking loaded tickets for actual structure generation.
                    saved.close()
                    try:
                        row = examine(saved.get(cx, cz), seed, cx, cz, data_version=data_version)
                    except OSError as exc:
                        raise RCONError(f'World save could not be read: {exc}') from exc
                    if row['status'] not in ('not_generated', 'not_full'):
                        break
                    time.sleep(2)
                if row is None or row['status'] in ('not_generated', 'not_full'):
                    row = examine(None, seed, cx, cz, data_version=data_version)
                    row.update(status='timeout', reason='Chunk failed to become FULL on disk by timeout')
                record(row)
                print(f'[{number}/{min(len(selection), args.limit)}] {cx},{cz} : {row["status"]}', file=sys.stderr)
                accepted = (getattr(args, 'stop_center_y_below', None) is not None and
                            accepted_tower(row, center_below=args.stop_center_y_below,
                                           max_y=getattr(args, 'stop_max_y', None)))
            finally:
                if loaded_by_us:
                    server.command(f'execute in minecraft:overworld run forceload remove {command_pos}')
            if accepted:
                print(f'Accepted verified tower at chunk {cx},{cz}; '
                      'all requested thresholds satisfied.', file=sys.stderr)
                break
    # The caller's completeness proof relies on the ORIGINAL candidate order.
    # Sort only the human-readable CSV; never reorder the returned audit rows.
    out = [dict(version=version_name, **row) for row in out]
    sorted_for_csv = sorted(out, key=lambda r: (r['distance_sq'], int(r['chunk_x']), int(r['chunk_z'])))
    write_csv(args.out, sorted_for_csv, FIELDS)
    return out


def add_live_command(commands):
    a = commands.add_parser('live', help='對執行中的同版 vanilla 伺服器進行生成與存檔核驗')
    from .versions import SUPPORTED
    a.add_argument('--version', choices=['auto', *sorted(SUPPORTED)], default='auto')
    a.add_argument('--world', type=Path, required=True)
    a.add_argument('--candidates', type=Path, required=True)
    a.add_argument('--host', default='127.0.0.1')
    a.add_argument('--port', type=int, default=25575)
    a.add_argument('--password-env', default='MINECRAFT_RCON_PASSWORD')
    a.add_argument('--allow-remote', action='store_true', help='僅用於已加密的安全通道')
    a.add_argument('--limit', type=int, default=50)
    a.add_argument('--timeout', type=int, default=180, help='每個區塊驗證超時秒數')
    a.add_argument('--out', type=Path)
    a.add_argument('--checkpoint', type=Path, help='每筆原版存檔核對完成後保存稽核進度')
    a.set_defaults(run=run_live)
