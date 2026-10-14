#!/usr/bin/env python3
"""Build one architecture-specific, self-contained macOS JAR."""
from __future__ import annotations

import argparse
from pathlib import Path

from macos_jar import RuntimeLock, build_jar


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--arch", required=True, choices=("arm64", "x86_64"))
    parser.add_argument("--runtime", required=True, type=Path)
    parser.add_argument("--lock", type=Path,
                        default=Path(__file__).resolve().parents[1] / "packaging/macos/runtime-lock.json")
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    expected_name = f"LowYOutpostFinder-macos-{args.arch}.jar"
    if args.output.name != expected_name:
        parser.error(f"output filename must be {expected_name}")
    lock = RuntimeLock.load(args.lock, args.arch)
    build_jar(Path(__file__).resolve().parents[1], args.runtime, lock, args.output)
    print(args.output.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
