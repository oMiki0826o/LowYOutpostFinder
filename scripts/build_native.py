#!/usr/bin/env python3
"""Build the optional native scanners with one cross-platform entry point."""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile


ROOT = Path(__file__).resolve().parents[1]
NATIVE_SOURCE = ROOT / "native" / "src"


def compiler() -> str:
    found = next((shutil.which(name) for name in ("cc", "clang", "gcc") if shutil.which(name)), None)
    if not found:
        raise RuntimeError("A C11 compiler (cc, clang, or gcc) is required")
    return found


def build_region() -> Path:
    destination = ROOT / "bin" / ("region_scan.exe" if os.name == "nt" else "region_scan")
    destination.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run([
        compiler(), "-O2", "-std=c11", "-Wall", "-Wextra", "-Werror",
        str(NATIVE_SOURCE / "region_scan.c"), "-o", str(destination),
    ], check=True)
    return destination


def _extract_core(archive: Path, destination: Path) -> None:
    if destination.exists():
        shutil.rmtree(destination)
    destination.mkdir(parents=True)
    if archive.suffix.lower() == ".zip":
        subprocess.run([
            sys.executable, str(ROOT / "scripts" / "extract_core.py"),
            str(archive), str(destination),
        ], check=True)
    elif archive.name.endswith((".tar.gz", ".tgz")):
        with tarfile.open(archive, "r:gz") as source:
            source.extractall(destination, filter="data")
    else:
        raise RuntimeError("Supported upstream archives: .zip, .tar.gz, .tgz")


def build_terrain(archive: Path) -> Path:
    if not archive.is_file():
        raise RuntimeError(f"Missing LowYSwampHut source archive: {archive}")
    if not shutil.which("cmake"):
        raise RuntimeError("cmake is required")
    source_root = ROOT / ".build" / "source"
    build_root = ROOT / ".build" / "core-build"
    _extract_core(archive, source_root)
    rng_sources = list(source_root.glob("**/lysh-c/src/rng.c"))
    if len(rng_sources) != 1:
        raise RuntimeError("Archive must contain exactly one lysh-c/src/rng.c")
    source_dir = rng_sources[0].parent
    project_dir = source_dir.parent
    subprocess.run([
        "cmake", "-S", str(project_dir), "-B", str(build_root),
        "-DLYSH_JNI=OFF", "-DLYSH_LTO=OFF",
        "-DCMAKE_C_FLAGS=-include stddef.h", "-DCMAKE_BUILD_TYPE=Release",
    ], check=True)
    subprocess.run(["cmake", "--build", str(build_root), "--parallel", "2"], check=True)
    destination = ROOT / "bin" / ("lowyoutpost.exe" if os.name == "nt" else "lowyoutpost")
    destination.parent.mkdir(parents=True, exist_ok=True)
    command = [
        compiler(), "-std=c11", "-O2", "-Wall", "-Wextra", "-ffp-contract=off",
        "-include", "stddef.h", f"-I{source_dir}", str(NATIVE_SOURCE / "outpost_scan.c"),
        str(build_root / "liblysh_core.a"), "-lm", "-lpthread", "-o", str(destination),
    ]
    subprocess.run(command, check=True)
    return destination


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build optional LowYOutpostFinder native tools")
    subparsers = parser.add_subparsers(dest="target", required=True)
    subparsers.add_parser("region", help="build the standalone placement scanner")
    terrain = subparsers.add_parser("terrain", help="build the experimental terrain sampler")
    terrain.add_argument("archive", type=Path, help="user-supplied LowYSwampHut source archive")
    args = parser.parse_args(argv)
    try:
        output = build_region() if args.target == "region" else build_terrain(args.archive)
    except (OSError, RuntimeError, subprocess.SubprocessError, tarfile.TarError) as exc:
        parser.exit(2, f"ERROR: {exc}\n")
    print(f"Built: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
