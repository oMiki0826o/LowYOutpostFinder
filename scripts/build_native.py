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


def _fix_upstream_carver(source_dir: Path) -> None:
    """Remove a non-C11 floating-point assertion from the pinned source copy.

    Only the exact audited source is patched. The constant and algorithm
    remain unchanged; unexpected upstream revisions fail closed.
    """
    carver = source_dir / "carver.c"
    content = carver.read_text(encoding="utf-8")
    macro = "#define MC_SIN_SCALE 0x1.45f306dc9c883p13"
    assertion = (
        '_Static_assert(MC_SIN_SCALE == 10430.378350470453,\n'
        '               "MC_SIN_SCALE must be the exact double 10430.378350470453d");'
    )
    if content.count(macro) != 1 or content.count(assertion) != 1:
        raise RuntimeError("Pinned upstream carver.c layout changed; refusing unsafe patch")
    if float.fromhex("0x1.45f306dc9c883p13") != float("10430.378350470453"):
        raise RuntimeError("Pinned MC_SIN_SCALE constant is not equivalent")
    carver.write_text(
        content.replace(assertion, "/* C11: checked by build_native.py. */", 1),
        encoding="utf-8",
    )


def build_terrain(archive: Path, output_name: str = "lowyoutpost") -> Path:
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
    _fix_upstream_carver(source_dir)
    # The upstream project enables AVX2 unconditionally on non-macOS builds.
    # Keep the downloaded archive intact, but make the disposable build copy
    # portable to CPUs and virtual machines without AVX2 support.
    cmake_lists = project_dir / "CMakeLists.txt"
    contents = cmake_lists.read_text(encoding="utf-8")
    portable = contents.replace("    add_compile_options(-mavx2)\n", "")
    if portable == contents:
        raise RuntimeError("LowYSwampHut CMake file has no expected AVX2 setting")
    cmake_lists.write_text(portable, encoding="utf-8")
    subprocess.run([
        "cmake", "-S", str(project_dir), "-B", str(build_root),
        "-DLYSH_JNI=OFF", "-DLYSH_LTO=OFF",
        "-DCMAKE_C_FLAGS=-include stddef.h", "-DCMAKE_BUILD_TYPE=Release",
    ], check=True)
    subprocess.run(["cmake", "--build", str(build_root), "--parallel", "2"], check=True)
    destination = ROOT / "bin" / (output_name + (".exe" if os.name == "nt" else ""))
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
    estimate = subparsers.add_parser("estimate", help="build the resumable estimated-height scanner")
    estimate.add_argument("archive", type=Path, help="user-supplied LowYSwampHut source archive")
    args = parser.parse_args(argv)
    try:
        output = build_region() if args.target == "region" else build_terrain(
            args.archive, "outpost_estimate" if args.target == "estimate" else "lowyoutpost")
    except (OSError, RuntimeError, subprocess.SubprocessError, tarfile.TarError) as exc:
        parser.exit(2, f"ERROR: {exc}\n")
    print(f"Built: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
