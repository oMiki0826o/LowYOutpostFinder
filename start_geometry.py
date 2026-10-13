"""File: start_geometry.py
Modification: 2026-10-13 — Jigsaw baseplate start rotation/center and version asset inspection.

Geometry uses the supplied game's own baseplate template, never a guessed size.
No Y is considered vanilla-confirmed unless subsequently checked in a generated save.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import zipfile
from game_archive import open_game_assets

from finder import JavaRandom, MASK64, to_int32
from nbt import NBTError, inflate_limited, parse_nbt


@dataclass(frozen=True)
class OutpostAssets:
    size: tuple[int, int, int]
    sha256: str
    jar: str


@dataclass(frozen=True)
class StartProjection:
    rotation: int
    sample_x: int
    sample_z: int


def _get_member(archive: zipfile.ZipFile, path: str, limit: int) -> bytes:
    try:
        info = archive.getinfo(path)
    except KeyError as exc:
        raise ValueError(f'Official game archive is missing required resource: {path}') from exc
    if not (0 < info.file_size <= limit):
        raise ValueError(f'Unreasonable resource size: {path}')
    data = archive.read(info)
    if len(data) != info.file_size:
        raise ValueError('Archive file was truncated')
    return data


def load_outpost_assets(jar_path: Path) -> OutpostAssets:
    """Load required generation metadata from a *user-supplied* game archive.

    This does NOT assert the archive is authentic or prove terrain/RNG agreement.
    Reject custom datapack changes/unknown pools rather than silently guessing.
    """
    path = Path(jar_path)
    try:
        with open_game_assets(path) as jar:
            structure = json.loads(_get_member(jar, 'data/minecraft/worldgen/structure/pillager_outpost.json', 256 * 1024))
            pool = json.loads(_get_member(jar, 'data/minecraft/worldgen/template_pool/pillager_outpost/base_plates.json', 256 * 1024))
            if (structure.get('type') != 'minecraft:jigsaw'
                or structure.get('project_start_to_heightmap') != 'WORLD_SURFACE_WG'
                or structure.get('start_height') != {'absolute': 0}
                or structure.get('start_pool') != 'minecraft:pillager_outpost/base_plates'
                or structure.get('start_jigsaw_name') not in (None, '')):
                raise ValueError('Archive uses a different outpost Jigsaw definition')
            elements = pool.get('elements')
            if not isinstance(elements, list) or len(elements) != 1:
                raise ValueError('Unexpected outpost base pool selection; cannot predict start piece')
            e = elements[0]
            element = e.get('element') if isinstance(e, dict) else None
            if (not isinstance(element, dict) or e.get('weight') != 1
                or element.get('location') != 'minecraft:pillager_outpost/base_plate'
                or element.get('projection') != 'rigid'
                or element.get('element_type') not in ('minecraft:legacy_single_pool_element', 'minecraft:single_pool_element')):
                raise ValueError('Unexpected outpost start pool element')
            template = None
            for filepath in ('data/minecraft/structure/pillager_outpost/base_plate.nbt',
                             'data/minecraft/structures/pillager_outpost/base_plate.nbt'):
                if filepath in jar.namelist():
                    template = _get_member(jar, filepath, 4 * 1024 * 1024)
                    break
            if template is None:
                raise ValueError('Archive does not include the base_plate structure template')
            nbt = parse_nbt(inflate_limited(template, gzip_format=True))
            size = nbt.get('size')
            if (not isinstance(size, list) or len(size) != 3
                or any(type(v) is not int or v < 1 or v > 128 for v in size)):
                raise ValueError('Invalid base_plate template dimensions')
            return OutpostAssets(tuple(size), hashlib.sha256(template).hexdigest(), str(path))
    except (OSError, zipfile.BadZipFile, UnicodeDecodeError, NBTError, json.JSONDecodeError) as exc:
        raise ValueError(f'Cannot inspect Minecraft game archive: {exc}') from exc


def java_signed32(number: int) -> int:
    return to_int32(number)


def java_next_long(rng: JavaRandom) -> int:
    """java.util.Random.nextLong() signed 32-bit append/add; 64-bit wrap."""
    high = java_signed32(rng.bits(32))
    low = java_signed32(rng.bits(32))
    result = ((high << 32) + low) & MASK64
    return result if result < (1 << 63) else result - (1 << 64)


def java_div_trunc(value: int, divisor: int) -> int:
    return value // divisor if value >= 0 else -((-value) // divisor)


def geometry_for_rotation(x: int, z: int, size_x: int, size_z: int, rotation: int) -> tuple[int, int]:
    """Replicate StructureTemplate.createBox with mirror NONE, pivot ORIGIN.

    Rotation enum: NONE=0, CW90=1, CW180=2, CCW90=3.
    """
    if rotation not in (0, 1, 2, 3) or min(size_x, size_z) <= 0:
        raise ValueError('Invalid start rotation/template size')
    a, b = size_x - 1, size_z - 1
    corner_x, corner_z = ((a, b), (-b, a), (-a, -b), (b, -a))[rotation]
    return (java_div_trunc(x + (x + corner_x), 2),
            java_div_trunc(z + (z + corner_z), 2))


def projection(seed: int, chunk_x: int, chunk_z: int,
               size: tuple[int, int, int]) -> StartProjection:
    """Replicate Structure.Context.createChunkRandom(seed, chunk) + rotation.

    The projection X/Z is exact for the vanilla start pool encoded in the supplied
    version template; querying the terrain height at this position is a separate step.
    """
    if len(size) != 3 or any(v < 1 for v in size):
        raise ValueError('Invalid template dimensions')
    rng = JavaRandom(seed)
    mul_x, mul_z = java_next_long(rng), java_next_long(rng)
    carver_seed = ((chunk_x * mul_x) ^ (chunk_z * mul_z) ^ seed) & MASK64
    rng = JavaRandom(carver_seed)
    rotation = rng.bounded(4)
    px, pz = geometry_for_rotation(chunk_x * 16, chunk_z * 16,
                                   size[0], size[2], rotation)
    return StartProjection(rotation, px, pz)
