"""Resumable C11-estimated low-Y outpost scan.

This module deliberately separates seed-only estimates from saved-world
verification.  It never emits ``verified_tower``.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import heapq
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time

from .cli import OUTPOST, is_candidate_start, write_csv
from .full_map import MAX_TOP, RegionGrid, WORLD_EDGE, rank
from .worldgen_assets import OUTPOST_ASSET_MODEL

FIELDS = ("version", "seed", "chunk_x", "chunk_z", "x", "z", "distance_sq",
          "projected_surface_y", "projected_base_plate_y", "sample_x", "sample_z",
          "rotation", "biome_id", "classification")
STRICT_FIELDS = ("version", "seed", "chunk_x", "chunk_z", "x", "z", "distance_sq",
                 "projected_surface_y", "projected_base_plate_y", "projected_structure_center_y", "projected_base_plate_max_y",
                 "footprint_sample_count", "sample_x", "sample_z", "rotation", "biome_id",
                 "classification")


@dataclass(frozen=True)
class EstimatedScanConfig:
    version: str
    seed: int
    x_min: int = -WORLD_EDGE
    x_max: int = WORLD_EDGE
    z_min: int = -WORLD_EDGE
    z_max: int = WORLD_EDGE
    center_x: int = 0
    center_z: int = 0
    max_y: int = -37
    top: int = 100
    batch_regions: int = 500_000
    sleep_ms: int = 150
    engine: str = "native"
    template_width: int = 16
    template_depth: int = 16
    threads: int = 0

    def grid(self) -> RegionGrid:
        if self.version != "1.21.8":
            raise ValueError("Estimated height mode supports Minecraft 1.21.8 only")
        if type(self.seed) is not int or not -(1 << 63) <= self.seed < (1 << 63):
            raise ValueError("World seed must be a signed Java 64-bit integer")
        if not -64 <= self.max_y <= 320:
            raise ValueError("max-y must be within -64..320")
        if not 1 <= self.top <= MAX_TOP or not 1 <= self.batch_regions <= 5_000_000:
            raise ValueError("top must be 1..10000; batch-regions 1..5000000")
        if not 0 <= self.sleep_ms <= 5000 or self.engine not in ("native", "auto"):
            raise ValueError("cpu-rest-ms must be 0..5000; estimate engine must be native or auto")
        if not 0 <= self.threads <= 256:
            raise ValueError("threads must be 0 (automatic) or 1..256")
        if not all(type(v) is int and -WORLD_EDGE <= v <= WORLD_EDGE
                   for v in (self.center_x, self.center_z)):
            raise ValueError("Center outside world border")
        if not 1 <= self.template_width <= 128 or not 1 <= self.template_depth <= 128:
            raise ValueError("Invalid base_plate template dimensions")
        return RegionGrid(self.x_min, self.x_max, self.z_min, self.z_max)


def _atomic_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent,
                                         prefix="." + path.name, suffix=".tmp", delete=False) as handle:
            temporary = Path(handle.name)
            json.dump(value, handle, ensure_ascii=False, sort_keys=True, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        temporary.replace(path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def _digest(cfg: EstimatedScanConfig) -> str:
    values = asdict(cfg)
    for key in ("batch_regions", "sleep_ms", "engine", "threads"):
        values.pop(key)
    return hashlib.sha256(json.dumps(values, sort_keys=True).encode()).hexdigest()


def _add(heap: list[tuple[int, int, int, dict]], row: dict, cfg: EstimatedScanConfig) -> None:
    key = rank(row["chunk_x"], row["chunk_z"], cfg.center_x, cfg.center_z)
    item = (-key[0], -key[1], -key[2], row)
    if len(heap) < cfg.top:
        heapq.heappush(heap, item)
    elif item[:3] > heap[0][:3]:
        heapq.heapreplace(heap, item)


def scan_native_estimate(grid: RegionGrid, cfg: EstimatedScanConfig, start: int, end: int,
                         binary: Path) -> tuple[list[dict], int, int, int, str]:
    command = [str(binary), "--json", "--seed", str(cfg.seed), "--start", str(start),
               "--count", str(end - start), "--x-min", str(grid.x_min), "--x-max", str(grid.x_max),
               "--z-min", str(grid.z_min), "--z-max", str(grid.z_max), "--max-y", str(cfg.max_y),
               "--top", str(cfg.top), "--template-width", str(cfg.template_width),
               "--template-depth", str(cfg.template_depth)]
    result = subprocess.run(command, capture_output=True, text=True, timeout=3600, check=False)
    if result.returncode:
        raise RuntimeError(f"Native estimated scan failed (exit={result.returncode}): {result.stderr[-1200:]}")
    try:
        payload = json.loads(result.stdout)
        matches, biome_passes, passes, fingerprint, rows = (payload["matches"], payload["biome_passes"], payload["height_passes"],
                                                            payload["model_fingerprint"], payload["rows"])
        if (type(matches) is not int or type(biome_passes) is not int or type(passes) is not int or not isinstance(fingerprint, str)
                or not isinstance(rows, list) or not 0 <= passes <= biome_passes <= matches <= end - start
                or len(rows) > cfg.top):
            raise ValueError("invalid native result header")
        validated, seen = [], set()
        for row in rows:
            if not isinstance(row, dict) or set(row) != {"chunk_x", "chunk_z", "projected_surface_y",
                                                         "projected_base_plate_y", "sample_x", "sample_z",
                                                         "rotation", "biome_id", "classification"}:
                raise ValueError("invalid native row schema")
            if any(type(row[key]) is not int for key in row if key != "classification") or row["classification"] != "estimated_only":
                raise ValueError("invalid native row values")
            cx, cz = row["chunk_x"], row["chunk_z"]
            rx, rz = cx // OUTPOST[0], cz // OUTPOST[0]
            index = (rz - grid.rz_min) * grid.width + (rx - grid.rx_min)
            if ((cx, cz) in seen or not start <= index < end or not is_candidate_start(cfg.seed, cx, cz)
                    or not grid.x_min <= cx * 16 <= grid.x_max or not grid.z_min <= cz * 16 <= grid.z_max
                    or row["projected_base_plate_y"] > cfg.max_y):
                raise ValueError("untrusted native estimate row")
            seen.add((cx, cz))
            validated.append(row)
        return validated, matches, biome_passes, passes, fingerprint
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise RuntimeError("Native estimated scan returned invalid JSON") from exc


def scan_native_strict_nearest(grid: RegionGrid, cfg: EstimatedScanConfig, start_ring: int,
                               ring_count: int, wanted: int, binary: Path) -> tuple[list[dict], int, int, int, int, bool, str]:
    command = [str(binary), "--json", "--seed", str(cfg.seed), "--x-min", str(grid.x_min),
               "--x-max", str(grid.x_max), "--z-min", str(grid.z_min), "--z-max", str(grid.z_max),
               "--center-x", str(cfg.center_x), "--center-z", str(cfg.center_z),
               "--start-ring", str(start_ring), "--ring-count", str(ring_count), "--max-y", str(cfg.max_y),
               "--top", str(wanted), "--template-width", str(cfg.template_width),
               "--template-depth", str(cfg.template_depth), "--threads", str(cfg.threads)]
    result = subprocess.run(command, capture_output=True, text=True, timeout=3600, check=False)
    if result.returncode:
        raise RuntimeError(f"Native strict estimated scan failed (exit={result.returncode}): {result.stderr[-1200:]}")
    try:
        payload = json.loads(result.stdout)
        matches, biome_passes, passes, next_ring, stopped, fingerprint, rows = (
            payload["matches"], payload["biome_passes"], payload["height_passes"], payload["next_ring"], payload["stopped_early"],
            payload["model_fingerprint"], payload["rows"])
        expected = {"chunk_x", "chunk_z", "projected_surface_y", "projected_base_plate_y", "projected_structure_center_y",
                    "projected_base_plate_max_y", "footprint_sample_count", "sample_x", "sample_z",
                    "rotation", "biome_id", "classification"}
        if (type(matches) is not int or type(biome_passes) is not int or type(passes) is not int or type(next_ring) is not int
                or type(stopped) is not bool or not isinstance(fingerprint, str) or not isinstance(rows, list)
                or not start_ring <= next_ring <= start_ring + ring_count or not 0 <= passes <= biome_passes <= matches
                or len(rows) > wanted):
            raise ValueError("invalid native strict result header")
        validated, seen = [], set()
        for row in rows:
            if (not isinstance(row, dict) or set(row) != expected
                    or any(type(row[key]) is not int for key in expected if key != "classification")
                    or row["classification"] != "estimated_only" or row["footprint_sample_count"] != 1
                    or row["projected_structure_center_y"] >= cfg.max_y):
                raise ValueError("invalid native strict row")
            cx, cz = row["chunk_x"], row["chunk_z"]
            rx, rz = cx // OUTPOST[0], cz // OUTPOST[0]
            ring = max(abs(rx - cfg.center_x // 512), abs(rz - cfg.center_z // 512))
            if ((cx, cz) in seen or not start_ring <= ring < next_ring
                    or not is_candidate_start(cfg.seed, cx, cz)
                    or not grid.x_min <= cx * 16 <= grid.x_max or not grid.z_min <= cz * 16 <= grid.z_max):
                raise ValueError("untrusted native strict row")
            seen.add((cx, cz))
            validated.append(row)
        return validated, matches, biome_passes, passes, next_ring, stopped, fingerprint
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise RuntimeError("Native strict estimated scan returned invalid JSON") from exc


def _rows(heap: list[tuple[int, int, int, dict]], cfg: EstimatedScanConfig) -> list[dict]:
    result = []
    for _, _, _, native in sorted(heap, key=lambda item: (-item[0], -item[1], -item[2])):
        cx, cz = native["chunk_x"], native["chunk_z"]
        result.append({"version": cfg.version, "seed": cfg.seed, "chunk_x": cx, "chunk_z": cz,
                       "x": cx * 16, "z": cz * 16,
                       "distance_sq": rank(cx, cz, cfg.center_x, cfg.center_z)[0], **native})
    return result


def scan_estimated(cfg: EstimatedScanConfig, out: Path, *, resume: bool = False,
                   max_batches: int = 0, binary: Path | None = None, progress=None) -> dict:
    grid = cfg.grid()
    if cfg.threads:
        raise ValueError("threads applies to strict nearest estimated scans only")
    if max_batches < 0 or Path(out).suffix.lower() != ".csv":
        raise ValueError("max-batches must not be negative and output must be .csv")
    out, state_path = Path(out), Path(out).with_suffix(".state.json")
    if binary is None:
        from .paths import native_binary
        binary = native_binary("outpost_estimate")
    if not Path(binary).is_file():
        raise ValueError("Native estimated scanner not compiled; run scripts/build_native.py estimate ARCHIVE")
    fingerprint = _digest(cfg)
    heap: list[tuple[int, int, int, dict]] = []
    if resume:
        if not state_path.is_file():
            raise ValueError("No estimated-scan checkpoint found")
        state = json.loads(state_path.read_text(encoding="utf-8"))
        if state.get("configuration_sha256") != fingerprint or state.get("total_regions") != grid.total:
            raise ValueError("checkpoint does not match estimated scan parameters")
        for row in state.get("retained", []):
            if not isinstance(row, dict):
                raise ValueError("Invalid estimated checkpoint row")
            _add(heap, row, cfg)
    else:
        if out.exists() or state_path.exists():
            raise ValueError("Refusing to overwrite existing output/checkpoint; use --resume")
        state = {"configuration_sha256": fingerprint, "seed": cfg.seed, "version": cfg.version,
                 "total_regions": grid.total, "processed_regions": 0, "placement_candidates": 0,
                 "estimated_biome_passes": 0, "estimated_height_passes": 0, "classification": "estimated_only", "retained": [],
                 "status": "incomplete", "bounds": {"x_min": cfg.x_min, "x_max": cfg.x_max,
                 "z_min": cfg.z_min, "z_max": cfg.z_max}}
        _atomic_json(state_path, state)
    index, batches = state["processed_regions"], 0
    while index < grid.total and (max_batches == 0 or batches < max_batches):
        end = min(index + cfg.batch_regions, grid.total)
        native_rows, matches, biome_passes, passes, model = scan_native_estimate(grid, cfg, index, end, Path(binary))
        for row in native_rows:
            _add(heap, row, cfg)
        index, batches = end, batches + 1
        state.update(processed_regions=index,
                     placement_candidates=state["placement_candidates"] + matches,
                     estimated_biome_passes=state.get("estimated_biome_passes", 0) + biome_passes,
                     estimated_height_passes=state["estimated_height_passes"] + passes,
                     model_fingerprint=model, outpost_asset_model=OUTPOST_ASSET_MODEL, retained=[item[3] for item in heap],
                     status="complete_estimated_only" if index == grid.total else "incomplete")
        _atomic_json(state_path, state)
        write_csv(out, _rows(heap, cfg), FIELDS)
        if progress:
            progress(state)
        if cfg.sleep_ms and index != grid.total:
            time.sleep(cfg.sleep_ms / 1000)
    return state


def scan_estimated_nearest(cfg: EstimatedScanConfig, out: Path, *, resume: bool = False,
                           max_batches: int = 0, binary: Path | None = None, progress=None) -> dict:
    """Find nearest centre-height estimates in deterministic centre-out rings."""
    grid = cfg.grid()
    if max_batches < 0 or Path(out).suffix.lower() != ".csv":
        raise ValueError("max-batches must not be negative and output must be .csv")
    out, state_path = Path(out), Path(out).with_suffix(".state.json")
    if binary is None:
        from .paths import native_binary
        binary = native_binary("outpost_estimate")
    if not Path(binary).is_file():
        raise ValueError("Native estimated scanner not compiled; run scripts/build_native.py estimate ARCHIVE")
    # v2 completes a ring and ranks its survivors by distance before stopping.
    # Old checkpoints could have stopped part-way through the final ring.
    fingerprint = _digest(cfg) + ":strict-centre-nearest-v2"
    rows: list[dict] = []
    if resume:
        if not state_path.is_file():
            raise ValueError("No strict-nearest checkpoint found")
        state = json.loads(state_path.read_text(encoding="utf-8"))
        if state.get("configuration_sha256") != fingerprint or state.get("mode") != "strict_nearest":
            raise ValueError("checkpoint does not match strict-nearest scan parameters")
        rows = state.get("retained", [])
        if not isinstance(rows, list) or len(rows) > cfg.top:
            raise ValueError("Invalid strict-nearest checkpoint rows")
    else:
        if out.exists() or state_path.exists():
            raise ValueError("Refusing to overwrite existing output/checkpoint; use --resume")
        state = {"configuration_sha256": fingerprint, "mode": "strict_nearest", "seed": cfg.seed,
                 "version": cfg.version, "processed_rings": 0, "placement_candidates": 0,
                 "estimated_biome_passes": 0, "estimated_height_passes": 0, "classification": "estimated_only",
                 "retained": [], "status": "incomplete", "bounds": {"x_min": cfg.x_min,
                 "x_max": cfg.x_max, "z_min": cfg.z_min, "z_max": cfg.z_max}}
        _atomic_json(state_path, state)
    cr, cz = cfg.center_x // 512, cfg.center_z // 512
    max_ring = max(abs(grid.rx_min-cr), abs(grid.rx_max-cr),
                   abs(grid.rz_min-cz), abs(grid.rz_max-cz))
    batches = 0
    while (len(rows) < cfg.top and state["processed_rings"] <= max_ring
           and (max_batches == 0 or batches < max_batches)):
        rings = min(cfg.batch_regions, 512, max_ring - state["processed_rings"] + 1)
        native_rows, matches, biome_passes, passes, next_ring, stopped, model = scan_native_strict_nearest(
            grid, cfg, state["processed_rings"], rings, cfg.top - len(rows), Path(binary))
        rows.extend(native_rows)
        state.update(processed_rings=next_ring,
                     placement_candidates=state["placement_candidates"] + matches,
                     estimated_biome_passes=state.get("estimated_biome_passes", 0) + biome_passes,
                     estimated_height_passes=state["estimated_height_passes"] + passes,
                     model_fingerprint=model, outpost_asset_model=OUTPOST_ASSET_MODEL, retained=rows,
                     status=("complete_estimated_only" if stopped else
                             "exhausted_estimated_only" if next_ring > max_ring else "incomplete"))
        _atomic_json(state_path, state)
        write_csv(out, _strict_rows(rows, cfg), STRICT_FIELDS)
        batches += 1
        if progress:
            progress(state)
        if stopped or (cfg.sleep_ms and max_batches == 0):
            if stopped:
                break
            time.sleep(cfg.sleep_ms / 1000)
    return state


def _strict_rows(rows: list[dict], cfg: EstimatedScanConfig) -> list[dict]:
    return [{"version": cfg.version, "seed": cfg.seed, "chunk_x": row["chunk_x"], "chunk_z": row["chunk_z"],
             "x": row["chunk_x"] * 16, "z": row["chunk_z"] * 16,
             "distance_sq": rank(row["chunk_x"], row["chunk_z"], cfg.center_x, cfg.center_z)[0], **row}
            for row in sorted(rows, key=lambda item: rank(item["chunk_x"], item["chunk_z"], cfg.center_x, cfg.center_z))]
