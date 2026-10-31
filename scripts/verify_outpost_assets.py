#!/usr/bin/env python3
"""Optional maintenance check for the embedded 1.21.8 outpost asset baseline."""
from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from lowy_outpost_finder.worldgen_assets import verify_outpost_assets


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("jar", type=Path, help="official Minecraft Java 1.21.8 server inner JAR")
    args = parser.parse_args(argv)
    mismatches = verify_outpost_assets(args.jar)
    if mismatches:
        for name, actual in mismatches.items():
            print(f"MISMATCH {name}: {actual}")
        return 1
    print("Outpost asset baseline matches Minecraft Java 1.21.8.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
