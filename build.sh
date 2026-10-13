#!/bin/sh
# File: build.sh
# Modification: 2026-10-13 — macOS/Linux offline build from user-supplied .zip or .tar.gz.
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
CORE_ARCHIVE=${1:-"$ROOT/../LowYSwampHut-2.0.1.tar.gz"}
if [ ! -f "$CORE_ARCHIVE" ]; then
    echo "Missing LowYSwampHut source archive: $CORE_ARCHIVE" >&2
    echo "Usage: sh build.sh /full/path/to/LowYSwampHut-2.0.1.tar.gz" >&2
    exit 2
fi
command -v cmake >/dev/null 2>&1 || { echo "cmake is required" >&2; exit 2; }
command -v cc >/dev/null 2>&1 || { echo "C compiler is required" >&2; exit 2; }
mkdir -p "$ROOT/.build/source" "$ROOT/.build/core-build" "$ROOT/bin"
case "$CORE_ARCHIVE" in
    *.zip) python3 "$ROOT/scripts/extract_core.py" "$CORE_ARCHIVE" "$ROOT/.build/source" ;;
    *.tar.gz|*.tgz) tar -xzf "$CORE_ARCHIVE" -C "$ROOT/.build/source" ;;
    *) echo "Supported upstream archives: .zip, .tar.gz, .tgz" >&2; exit 2 ;;
esac
CORE=$(find "$ROOT/.build/source" -type f -path '*/lysh-c/src/rng.c' -print -quit)
[ -n "$CORE" ] || { echo "Archive does not contain lysh-c/src/rng.c" >&2; exit 2; }
SRC=$(dirname "$CORE")
PROJECT=$(dirname "$SRC")
# Upstream 2.0.1 rng.h uses size_t without including stddef.h; inject it at compile time.
cmake -S "$PROJECT" -B "$ROOT/.build/core-build" -DLYSH_JNI=OFF -DLYSH_LTO=OFF -DCMAKE_C_FLAGS='-include stddef.h' -DCMAKE_BUILD_TYPE=Release
cmake --build "$ROOT/.build/core-build" --parallel 2
cc -std=c11 -O2 -Wall -Wextra -ffp-contract=off -include stddef.h \
   -I"$SRC" "$ROOT/src/outpost_scan.c" "$ROOT/.build/core-build/liblysh_core.a" \
   -lm -lpthread -o "$ROOT/bin/lowyoutpost"
echo "Built: $ROOT/bin/lowyoutpost"
