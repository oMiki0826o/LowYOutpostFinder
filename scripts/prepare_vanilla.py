"""File: prepare_vanilla.py
Modification: 2026-10-12 — version-aware Mojang server preparation and SHA-1 verification.

No bundled Minecraft binaries, EULA auto-consent, or server auto-start.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import secrets
import shutil
import sys
from urllib.parse import urlsplit
from urllib.request import urlopen

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lowy_outpost_finder.versions import SUPPORTED, check_version

MANIFEST = 'https://piston-meta.mojang.com/mc/game/version_manifest_v2.json'
MAX_META_BYTES = 5_000_000
ALLOWED_HOSTS = {'piston-meta.mojang.com', 'piston-data.mojang.com',
                 'launcher.mojang.com', 'launchermeta.mojang.com',
                 'launcher.mojang.com'}


def safe_mojang_url(url: str) -> str:
    parts = urlsplit(url)
    if parts.scheme != 'https' or parts.hostname not in ALLOWED_HOSTS or parts.username or parts.password:
        raise ValueError(f'Refusing non-Mojang URL for Minecraft server metadata: {parts.hostname}')
    return url


def download_json(url: str) -> dict:
    with urlopen(safe_mojang_url(url), timeout=30) as handle:
        data = handle.read(MAX_META_BYTES + 1)
    if len(data) > MAX_META_BYTES:
        raise ValueError('Mojang metadata exceeds size limit')
    return json.loads(data)


def server_meta(version: str) -> dict:
    check_version(version)
    manifest = download_json(MANIFEST)
    record = next((row for row in manifest.get('versions', [])
                   if row.get('id') == version and row.get('type') == 'release'), None)
    if not record:
        raise ValueError(f'Mojang manifest does not list {version} as a stable Java release')
    record_data = download_json(record['url'])
    server = record_data.get('downloads', {}).get('server')
    if not server or not all(key in server for key in ('url', 'sha1', 'size')):
        raise ValueError(f'Mojang did not publish a server binary for {version}')
    safe_mojang_url(server['url'])
    if len(server['sha1']) != 40 or not all(char in '0123456789abcdef' for char in server['sha1'].lower()):
        raise ValueError('Server artifact has invalid SHA-1 in Mojang metadata')
    if not 100_000 < server['size'] < 300_000_000:
        raise ValueError('Unexpected server artifact size')
    return server


def check_server(path: Path, metadata: dict) -> bool:
    if not path.is_file() or path.stat().st_size != metadata['size']:
        return False
    sha = hashlib.sha1()
    with path.open('rb') as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b''):
            sha.update(block)
    return sha.hexdigest() == metadata['sha1'].lower()


def prepare(path: Path, seed: int, download: bool, version: str) -> None:
    check_version(version)
    path = path.resolve()
    path.mkdir(parents=True, exist_ok=True)
    if (path / 'level.dat').exists() or (path / 'world').exists():
        raise ValueError('Refusing to configure an existing world; create a new, isolated directory')
    props = path / 'server.properties'
    if props.exists():
        raise ValueError('Existing server.properties will not be overwritten')
    jar = path / 'server.jar'
    metadata = server_meta(version)  # official version-specific checksum; internet required
    if not check_server(jar, metadata):
        if jar.exists():
            raise ValueError(f'Existing server.jar is NOT the Mojang {version} server (SHA-1 mismatch)')
        if not download:
            raise ValueError(f'Place Mojang {version} server.jar at {jar} or pass --download')
        part = jar.with_suffix('.download')
        try:
            with urlopen(safe_mojang_url(metadata['url']), timeout=120) as source, part.open('wb') as target:
                shutil.copyfileobj(source, target)
            if not check_server(part, metadata):
                raise ValueError('Downloaded server binary failed Mojang size/SHA-1 checks')
            part.replace(jar)
        finally:
            part.unlink(missing_ok=True)
    secret = secrets.token_urlsafe(32)
    props.write_text(f'''# Dedicated local Vanilla {version} world verification.
level-name=world
level-seed={seed}
level-type=minecraft:normal
generate-structures=true
server-ip=127.0.0.1
server-port=25565
enable-rcon=true
rcon.port=25575
rcon.password={secret}
view-distance=3
simulation-distance=3
max-players=1
motd=LowYOutpostFinder verification
''', encoding='utf-8')
    props.chmod(0o600)
    launcher = path / 'run.sh'
    launcher.write_text('''#!/bin/sh
# File: run.sh
# Modification: 2026-10-12 — local vanilla validation runner.
set -eu
cd "$(dirname "$0")"
exec java -Xms512M -Xmx2G -jar server.jar nogui
''', encoding='utf-8')
    launcher.chmod(0o755)
    print(f'Prepared Mojang {version} server in: {path}\n'
          f'Official SHA-1: {metadata["sha1"]}\n'
          'Run sh run.sh after confirming compatible Java runtime.\n'
          'Read and decide on the EULA yourself; this tool never agrees on your behalf.\n'
          'RCON is localhost only, unencrypted; never expose it to the internet.')


def main(argv=None):
    parser = argparse.ArgumentParser(description='Set up a version-matched Mojang Java server')
    parser.add_argument('--version', choices=sorted(SUPPORTED), default='1.21.8')
    parser.add_argument('--directory', type=Path, required=True)
    parser.add_argument('--seed', type=int, required=True)
    parser.add_argument('--download', action='store_true')
    args = parser.parse_args(argv)
    if not -(1 << 63) <= args.seed < (1 << 63):
        parser.error('Seed must fit Java long')
    try:
        prepare(args.directory, args.seed, args.download, args.version)
    except (ValueError, OSError, KeyError, json.JSONDecodeError) as exc:
        print(f'ERROR: {exc}', file=sys.stderr)
        return 2
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
