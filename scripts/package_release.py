"""File: package_release.py
Modification: 2026-10-12 — reproducible, source-only release ZIP with hashes.
"""
from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
import zipfile

OMIT_DIRS = frozenset({'.git', '.build', '.superpowers', '.agents', '.codex', '.worktrees',
                       'bin', 'data', 'results', 'world',
                       '__pycache__', '.venv', '.pytest_cache', '.idea', '.vscode',
                       'dist', 'node_modules'})
OMIT_FILES = frozenset({'server.properties', 'eula.txt', 'level.dat',
                        '.env', 'Thumbs.db', '.DS_Store', 'SHA256SUMS.txt'})
ALLOWED_EXT = frozenset({'.py', '.java', '.c', '.h', '.md', '.txt', '.sh',
                         '.command', '.bat', '.yml', '.yaml', '.toml', '.json',
                         '.gitignore'})
ALLOWED_FILES = frozenset({'VERSION', '.gitignore', 'LICENSE', 'LICENSE.md',
                           'NOTICE', 'Makefile'})
MAX_TEXT_BYTES = 5_000_000


def source_files(root: Path):
    for path in sorted(root.rglob('*')):
        if path.is_symlink() or not path.is_file():
            continue
        rel = path.relative_to(root)
        if (any(part in OMIT_DIRS or part.startswith('.env') for part in rel.parts)
                or path.name in OMIT_FILES or path.suffix.lower() not in ALLOWED_EXT
                and path.name not in ALLOWED_FILES):
            continue
        if path.stat().st_size > MAX_TEXT_BYTES:
            raise ValueError(f'Source file too large for release: {rel}')
        yield path, rel


def package(root: Path, output: Path) -> None:
    root = root.resolve()
    output = output.resolve()
    if not (root / 'VERSION').is_file():
        raise ValueError('No VERSION file in project root')
    version = (root / 'VERSION').read_text(encoding='utf-8').strip()
    if not version or any(char not in '0123456789.' for char in version):
        raise ValueError('VERSION must be a dotted numeric release identifier')
    files = list(source_files(root))
    if not files:
        raise ValueError('No source files found')
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.is_relative_to(root):
        raise ValueError('Release archive must be written outside the source tree')
    part = output.with_name(output.name + '.tmp')
    try:
        manifest = []
        with zipfile.ZipFile(part, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
            for path, rel in files:
                data = path.read_bytes()
                try:
                    data.decode('utf-8')
                except UnicodeDecodeError as exc:
                    raise ValueError(f'Non-UTF-8 source file: {rel}') from exc
                entry = zipfile.ZipInfo(f'{root.name}/{rel.as_posix()}', (1980, 1, 1, 0, 0, 0))
                entry.compress_type = zipfile.ZIP_DEFLATED
                entry.create_system = 3
                executable = rel.suffix in ('.sh', '.command')
                entry.external_attr = ((0o755 if executable else 0o644) << 16)
                archive.writestr(entry, data, compress_type=zipfile.ZIP_DEFLATED,
                                 compresslevel=9)
                manifest.append(f'{hashlib.sha256(data).hexdigest()}  {rel.as_posix()}')
            checksum_entry = zipfile.ZipInfo(f'{root.name}/SHA256SUMS.txt', (1980, 1, 1, 0, 0, 0))
            checksum_entry.compress_type = zipfile.ZIP_DEFLATED
            checksum_entry.external_attr = 0o644 << 16
            archive.writestr(checksum_entry, ('\n'.join(manifest) + '\n').encode('utf-8'))
        with zipfile.ZipFile(part) as archive:
            broken = archive.testzip()
            if broken:
                raise ValueError(f'Release ZIP validation failed: {broken}')
        part.replace(output)
    finally:
        part.unlink(missing_ok=True)


def write_manifest(root: Path, output: Path) -> None:
    """Write deterministic SHA-256 hashes for releasable source files."""
    root = root.resolve()
    lines = [f'{hashlib.sha256(path.read_bytes()).hexdigest()}  {rel.as_posix()}'
             for path, rel in source_files(root)]
    output.write_text('\n'.join(lines) + '\n', encoding='utf-8')


def main() -> int:
    parser = argparse.ArgumentParser(description='Create a source-only LowYOutpostFinder release ZIP')
    destination = parser.add_mutually_exclusive_group(required=True)
    destination.add_argument('--output', type=Path)
    destination.add_argument('--manifest', type=Path)
    parser.add_argument('--source', type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    try:
        if args.manifest:
            write_manifest(args.source, args.manifest)
        else:
            package(args.source, args.output)
    except (ValueError, OSError, zipfile.BadZipFile) as exc:
        parser.error(str(exc))
    print(f'Created: {(args.manifest or args.output).resolve()}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
