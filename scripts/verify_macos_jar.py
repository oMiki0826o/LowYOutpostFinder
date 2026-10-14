#!/usr/bin/env python3
"""Verify a self-contained LowYOutpostFinder macOS JAR."""
from __future__ import annotations

import argparse
from pathlib import Path

from macos_jar import verify_jar


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("jar", type=Path)
    parser.add_argument("--arch", required=True, choices=("arm64", "x86_64"))
    args = parser.parse_args()
    report = verify_jar(args.jar, args.arch)
    print(f"OK: {report.arch}, {report.payload_files} files, {report.payload_bytes} bytes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
