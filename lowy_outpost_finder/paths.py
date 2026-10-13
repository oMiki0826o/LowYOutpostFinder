"""Canonical project paths and subprocess entry points."""
from __future__ import annotations

import os
from pathlib import Path
import sys


PACKAGE_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = PACKAGE_ROOT.parent


def native_binary(name: str) -> Path:
    """Return the platform-specific path for a bundled native executable."""
    suffix = ".exe" if os.name == "nt" else ""
    return PROJECT_ROOT / "bin" / f"{name}{suffix}"


def cli_command(*args: str) -> list[str]:
    """Build a relocation-safe command for this package's CLI."""
    return [sys.executable, "-m", "lowy_outpost_finder", *args]
