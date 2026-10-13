"""File: tower_geometry.py
Modification: 2026-10-13 — derive the rigid primary watchtower's Y offset from game NBT.

The output is CONDITIONAL on an externally supplied exact WORLD_SURFACE_WG value.
This does not reproduce noise, chunk generation, arbitrary Jigsaw RNG or other pieces.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import zipfile
from game_archive import open_game_assets

from nbt import NBTError, inflate_limited, parse_nbt
from start_geometry import load_outpost_assets


class TowerGeometryError(ValueError):
    """Unsupported or ambiguous template connector layout."""


@dataclass(frozen=True)
class TowerBlueprint:
    base_size: tuple[int, int, int]
    tower_size: tuple[int, int, int]
    tower_min_y_from_base: int
    base_sha256: str
    tower_sha256: str

    @property
    def tower_height(self) -> int:
        return self.tower_size[1]


def _read_nbt(jar: zipfile.ZipFile, location: str) -> tuple[dict, str]:
    name = location.removeprefix('minecraft:')
    if not name.startswith('pillager_outpost/') or '..' in name:
        raise TowerGeometryError('Template location outside vanilla pillager_outpost')
    options = [f'data/minecraft/{prefix}/{name}.nbt' for prefix in ('structure', 'structures')]
    matches = [p for p in options if p in jar.namelist()]
    if len(matches) != 1:
        raise TowerGeometryError(f'Expected one NBT resource for {name}')
    resource = jar.getinfo(matches[0])
    if not 0 < resource.file_size <= 4 * 1024 * 1024:
        raise TowerGeometryError('Invalid template NBT compressed size')
    data = jar.read(resource)
    try:
        value = parse_nbt(inflate_limited(data, gzip_format=True))
    except (NBTError, OSError, ValueError) as exc:
        raise TowerGeometryError(f'Invalid template NBT for {name}: {exc}') from exc
    if not isinstance(value, dict):
        raise TowerGeometryError('NBT root is not a compound')
    return value, hashlib.sha256(data).hexdigest()


def _connectors(template: dict, *, parent: bool) -> list[tuple[int, str, str, str]]:
    """(local_y, orientation, target, name), filtered to tower pool on the parent."""
    palette = template.get('palette')
    blocks = template.get('blocks')
    size = template.get('size')
    if not isinstance(palette, list) or not isinstance(blocks, list) or not (
        isinstance(size, list) and len(size) == 3 and
        all(type(v) is int and 1 <= v <= 128 for v in size)
    ):
        raise TowerGeometryError('Unsupported template palette/blocks/dimensions')
    result = []
    for block in blocks:
        if not isinstance(block, dict):
            raise TowerGeometryError('Invalid template block')
        index = block.get('state')
        if type(index) is not int or not 0 <= index < len(palette):
            raise TowerGeometryError('Invalid template palette index')
        state = palette[index]
        if not isinstance(state, dict):
            raise TowerGeometryError('Invalid template palette state')
        block_id = state.get('Name', state.get('id'))
        if block_id != 'minecraft:jigsaw':
            continue
        coordinates = block.get('pos')
        nbt = block.get('nbt')
        props = state.get('Properties', state.get('properties'))
        if (not isinstance(coordinates, list) or len(coordinates) != 3 or
            any(type(v) is not int for v in coordinates) or
            any(not 0 <= coordinates[d] < size[d] for d in range(3)) or
            not isinstance(nbt, dict) or not isinstance(props, dict)):
            raise TowerGeometryError('Invalid jigsaw connector payload')
        orientation = props.get('orientation')
        target, name = nbt.get('target'), nbt.get('name')
        if not all(isinstance(v, str) and v for v in (orientation, target, name)):
            raise TowerGeometryError('Jigsaw connector name/orientation missing')
        if parent and nbt.get('pool') != 'minecraft:pillager_outpost/towers':
            continue
        result.append((coordinates[1], orientation, target, name))
    return result


def _tower_entry(jar: zipfile.ZipFile) -> str:
    path = 'data/minecraft/worldgen/template_pool/pillager_outpost/towers.json'
    try:
        info = jar.getinfo(path)
        if not 0 < info.file_size < 256 * 1024:
            raise TowerGeometryError('Tower pool size outside bounds')
        data = json.loads(jar.read(info))
    except (KeyError, UnicodeDecodeError, json.JSONDecodeError, OSError) as exc:
        raise TowerGeometryError(f'Cannot read vanilla tower pool: {exc}') from exc
    elements = data.get('elements') if isinstance(data, dict) else None
    if not isinstance(elements, list) or len(elements) != 1:
        raise TowerGeometryError('Tower pool is not the known singleton list pool')
    record = elements[0]
    element = record.get('element', {}) if isinstance(record, dict) else {}
    if record.get('weight') != 1 or element.get('element_type') != 'minecraft:list_pool_element' or element.get('projection') != 'rigid':
        raise TowerGeometryError('Unknown tower pool layout/projection')
    children = element.get('elements')
    if not isinstance(children, list) or len(children) < 1:
        raise TowerGeometryError('Tower pool has no templates')
    for child in children:
        if not isinstance(child, dict) or child.get('projection') != 'rigid' or child.get('element_type') not in (
            'minecraft:single_pool_element', 'minecraft:legacy_single_pool_element'):
            raise TowerGeometryError('Unsupported tower pool child')
    first = children[0].get('location')
    if first != 'minecraft:pillager_outpost/watchtower':
        raise TowerGeometryError('Primary tower is not the expected rigid watchtower')
    return first


def load_tower_blueprint(game_jar: Path) -> TowerBlueprint:
    """Calculate the rotation-invariant rigid tower Y difference from same-JAR assets.

    If there are multiple compatible vertical placements, refuse to guess which
    the full Jigsaw algorithm would choose; it depends on randomized ordering.
    """
    assets = load_outpost_assets(game_jar)
    try:
        with open_game_assets(game_jar) as jar:
            tower_loc = _tower_entry(jar)
            base, base_hash = _read_nbt(jar, 'minecraft:pillager_outpost/base_plate')
            tower, tower_hash = _read_nbt(jar, tower_loc)
    except (OSError, zipfile.BadZipFile, zipfile.LargeZipFile) as exc:
        raise TowerGeometryError(f'Cannot inspect game JAR: {exc}') from exc
    tower_size = tower.get('size')
    if (not isinstance(tower_size, list) or len(tower_size) != 3 or
        any(type(v) is not int or not 1 <= v <= 128 for v in tower_size)):
        raise TowerGeometryError('Invalid tower dimensions')
    if tuple(base['size']) != assets.size:
        raise TowerGeometryError('Base plate changed while reading archive')
    parents = _connectors(base, parent=True)
    children = _connectors(tower, parent=False)
    differences = set()
    cardinal = {'north', 'south', 'east', 'west'}
    for by, facing, target, _name in parents:
        parent_front, sep, parent_top = facing.partition('_')
        if not sep:
            raise TowerGeometryError(f'Unknown parent connector orientation {facing!r}')
        for cy, child_facing, _target, name in children:
            if name != target:
                continue
            child_front, sep2, child_top = child_facing.partition('_')
            if not sep2:
                raise TowerGeometryError(f'Unknown child connector orientation {child_facing!r}')
            if parent_front == 'up' and child_front == 'down':
                # Attached piece sits one block higher than an upward-facing parent.
                if parent_top in cardinal and child_top in cardinal:
                    differences.add(by + 1 - cy)
            elif parent_front in cardinal and child_front in cardinal:
                # A yaw rotation aligns opposing horizontal facings. For aligned
                # joints the up vectors must still agree. Horizontal neighbours
                # preserve the connector's world-space Y, with no +1 offset.
                if parent_top == child_top == 'up':
                    differences.add(by - cy)
    # Other front/top combinations require full 3D rotations, which vanilla
    # horizontal template rotation cannot provide here. Fail closed.
    if len(differences) != 1:
        raise TowerGeometryError(f'Non-unique or absent rigid tower connection: {sorted(differences)}')
    return TowerBlueprint(assets.size, tuple(tower_size), differences.pop(), base_hash, tower_hash)


def predict_vertical(blueprint: TowerBlueprint, world_surface_wg: int) -> tuple[int, int, int]:
    """Return (base_min_y, tower_min_y, tower_max_y), conditional on exact WG Y."""
    if type(world_surface_wg) is not int or not -64 <= world_surface_wg <= 321:
        raise ValueError('Height must be an integer WORLD_SURFACE_WG value (-64..321)')
    # The vanilla StructurePoolElement.getGroundLevelDelta() is 1. Base template
    # bounding-box minimum is local y=0; starting height is absolute 0.
    base_min_y = world_surface_wg - 1
    tower_min_y = base_min_y + blueprint.tower_min_y_from_base
    return base_min_y, tower_min_y, tower_min_y + blueprint.tower_height - 1
