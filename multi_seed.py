"""File: multi_seed.py
Modification: 2026-10-12 — sort low-Y candidate estimates across world seeds.
"""
from __future__ import annotations

import argparse
import csv
import io
from pathlib import Path
import subprocess
import sys


def main() -> int:
    parser = argparse.ArgumentParser(description="多種子低 Y 前哨站候選排序")
    parser.add_argument("--seeds-file", type=Path, required=True, help="每行一個帶正負號的十進位種子")
    parser.add_argument("--radius", type=int, default=8192)
    parser.add_argument("--max-y", type=int, default=64)
    parser.add_argument("--top", type=int, default=25)
    parser.add_argument("--output", type=Path, default=Path("results.csv"))
    parser.add_argument("--binary", type=Path, default=Path(__file__).resolve().parent / "bin" / "lowyoutpost")
    args = parser.parse_args()
    if args.top <= 0:
        parser.error("--top 必須大於零")
    seen: set[str] = set()
    results: list[dict[str, str]] = []
    for raw in args.seeds_file.read_text(encoding="utf-8").splitlines():
        seed = raw.strip()
        if not seed or seed.startswith("#"):
            continue
        try:
            seed = str(int(seed))
        except ValueError:
            parser.error(f"無效的種子：{seed}")
        if seed in seen:
            continue
        seen.add(seed)
        cmd = [str(args.binary), "--seed", seed, "--radius", str(args.radius),
               "--max-y", str(args.max_y), "--top", str(args.top)]
        cp = subprocess.run(cmd, capture_output=True, text=True)
        if cp.returncode:
            print(f"執行失敗 seed={seed}: {cp.stderr}", file=sys.stderr)
            return cp.returncode
        rows = list(csv.DictReader(io.StringIO(cp.stdout)))
        results.extend(rows)
        print(f"seed={seed}: {len(rows)} 個候選", file=sys.stderr)
    results.sort(key=lambda r: (int(r["projected_surface_y"]),
                                int(r["seed"]), int(r["x"]), int(r["z"])))
    fields = ["version", "seed", "chunk_x", "chunk_z", "x", "z", "projected_surface_y", "biome_id", "classification"]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(results[:args.top])
    print(f"完成：{len(seen)} 個種子，共 {len(results)} 個符合 Y 上限的保留候選；輸出 {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
