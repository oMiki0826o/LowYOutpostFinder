"""First-run setup for the optional 1.21.8 estimated-height C scanner.

Fetches a pinned MIT-licensed source revision, verifies the Git commit, and
uses the repository's existing cross-platform CMake build script. No shell,
privilege escalation, automatic package manager, or unpinned code execution.
"""
from __future__ import annotations

import os
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time
from typing import Callable

from .paths import PROJECT_ROOT, native_binary


UPSTREAM_URL = 'https://github.com/M33Galaxy/LowYSwampHut.git'
UPSTREAM_COMMIT = 'e3431121127d8f51613041a59c4fb3dbfaefd8b1'
UPSTREAM_LICENSE = 'MIT (M33Galaxy, SunnySlopes)'
DEPENDENCY_GUIDE = (
    'Automatic C build requires Git, CMake and a C11 compiler. '
    'macOS: install Xcode Command Line Tools and CMake; '
    'Ubuntu: install git, cmake and build-essential. '
    'Then restart LowYOutpostFinder.py.'
)


class BootstrapError(RuntimeError):
    """An actionable native-toolchain error, safe to display in the GUI."""


EXPECTED_MODEL = 'lowyswamphut-approx-1.21.8-centre-strict-single-sample'


def estimator_available(path: Path | None = None) -> bool:
    """Exercise the strict-nearest JSON protocol before trusting an existing binary.

    A filename and executable bit alone do not prove architecture or model
    compatibility. This one-region seed is bounded and does not generate world
    chunks; an outdated C scanner fails closed and is rebuilt when possible.
    """
    binary = Path(path) if path is not None else native_binary('outpost_estimate')
    if not binary.is_file() or not os.access(binary, os.X_OK):
        return False
    command = [
        str(binary), '--json', '--seed', '123',
        '--x-min', '-512', '--x-max', '512',
        '--z-min', '-512', '--z-max', '512',
        '--center-x', '0', '--center-z', '0',
        '--start-ring', '0', '--ring-count', '1',
        '--max-y', '320', '--top', '1', '--threads', '1',
    ]
    try:
        result = subprocess.run(command, capture_output=True, text=True,
                                timeout=15, check=False)
        if result.returncode != 0:
            return False
        payload = json.loads(result.stdout)
        return (isinstance(payload, dict)
                and payload.get('model_fingerprint') == EXPECTED_MODEL
                and type(payload.get('matches')) is int
                and payload.get('next_ring') == 1
                and isinstance(payload.get('rows'), list))
    except (OSError, ValueError, TypeError, subprocess.TimeoutExpired):
        return False


def _report(callback: Callable[[str], None] | None, message: str) -> None:
    if callback:
        callback(message)


def _command(argv: list[str], *, cwd: Path | None = None, timeout: int = 900,
             cancel_event=None) -> str:
    """Capture compiler diagnostics while allowing the launcher to cancel setup."""
    command = [str(x) for x in argv]
    try:
        proc = subprocess.Popen(
            command, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, encoding='utf-8', errors='replace',
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    except OSError as exc:
        raise BootstrapError(f'Could not launch {command[0]}: {exc}') from exc
    deadline = time.monotonic() + timeout
    try:
        while True:
            try:
                output, _ = proc.communicate(timeout=0.4)
                break
            except subprocess.TimeoutExpired:
                if cancel_event is not None and cancel_event.is_set():
                    raise BootstrapError('Native compilation cancelled')
                if time.monotonic() >= deadline:
                    raise BootstrapError('Native compilation timed out')
        if proc.returncode:
            raise BootstrapError(
                f'{Path(command[0]).name} exited with {proc.returncode}: '
                + output[-1600:])
        return output
    except BaseException:
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.communicate(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.communicate()
        raise


def ensure_native_estimator(*, native_path: Path | None = None,
                            status: Callable[[str], None] | None = None,
                            cancel_event=None) -> Path:
    """Build the pinned C height estimator once when all prerequisites are present.

    Reuse a compatible already-installed executable; never silently fall back
    to placement-only X/Z search after an estimate bootstrap failure.
    """
    binary = Path(native_path) if native_path is not None else native_binary('outpost_estimate')
    if estimator_available(binary):
        _report(status, 'C estimated-height scanner ready')
        return binary
    required = {'git': shutil.which('git'), 'cmake': shutil.which('cmake')}
    compiler = next((shutil.which(x) for x in ('cc', 'clang', 'gcc')
                     if shutil.which(x)), None)
    missing = [key for key, path in required.items() if not path]
    if not compiler:
        missing.append('C11 compiler')
    if missing:
        raise BootstrapError('Missing ' + ', '.join(missing) + '. ' + DEPENDENCY_GUIDE)
    _report(status, 'Downloading pinned MIT-licensed C source (first launch only)')
    with tempfile.TemporaryDirectory(prefix='lowy-outpost-native-') as tmp:
        work = Path(tmp)
        checkout = work / 'LowYSwampHut'
        checkout.mkdir()
        _command([required['git'], 'init', '-q'], cwd=checkout,
                 cancel_event=cancel_event)
        _command([required['git'], 'remote', 'add', 'origin', UPSTREAM_URL],
                 cwd=checkout, cancel_event=cancel_event)
        _command([required['git'], 'fetch', '--depth', '1', 'origin', UPSTREAM_COMMIT],
                 cwd=checkout, cancel_event=cancel_event)
        _command([required['git'], 'checkout', '--detach', '-q', 'FETCH_HEAD'],
                 cwd=checkout, cancel_event=cancel_event)
        actual = _command([required['git'], 'rev-parse', 'HEAD'],
                          cwd=checkout, cancel_event=cancel_event).strip()
        if actual != UPSTREAM_COMMIT:
            raise BootstrapError('Source revision checksum mismatch; native setup aborted')
        if not (checkout / 'lysh-c' / 'src' / 'rng.c').is_file():
            raise BootstrapError('Pinned upstream archive does not contain expected C source')
        _report(status, 'Building 1.21.8 C estimated-height scanner')
        archive = work / 'pinned-LowYSwampHut.tar.gz'
        with tarfile.open(archive, mode='w:gz') as tar:
            tar.add(checkout / 'lysh-c', arcname='LowYSwampHut/lysh-c')
            license_path = checkout / 'LICENSE'
            if license_path.is_file():
                tar.add(license_path, arcname='LowYSwampHut/LICENSE')
        output = _command([
            sys.executable, str(PROJECT_ROOT / 'scripts' / 'build_native.py'),
            'estimate', str(archive),
        ], cwd=PROJECT_ROOT, timeout=1800, cancel_event=cancel_event)
        if not estimator_available(binary):
            raise BootstrapError('Native build finished but outpost_estimate is missing or not executable: '
                                 + output[-600:])
    _report(status, 'C estimated-height scanner built and ready')
    return binary
