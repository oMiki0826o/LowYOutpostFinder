"""File: test_tower_geometry.py
Modification: 2026-10-13 — test Jigsaw tower vertical relation from NBT templates.
"""
from pathlib import Path
import gzip
import json
import struct
import tempfile
import unittest
import zipfile

from tower_geometry import load_tower_blueprint, predict_vertical, TowerGeometryError


def tag(typ, name, payload):
    name = name.encode('utf-8')
    return bytes([typ]) + struct.pack('>H', len(name)) + name + payload


def value(v):
    if isinstance(v, str):
        b = v.encode('utf-8')
        return 8, struct.pack('>H', len(b)) + b
    if isinstance(v, int):
        return 3, struct.pack('>i', v)
    if isinstance(v, dict):
        return 10, b''.join(tag(*((lambda t, p:(t,k,p))(*value(item)))) for k, item in v.items()) + b'\x00'
    if isinstance(v, list):
        if not v:
            return 9, b'\x00' + struct.pack('>i', 0)
        tags = [value(item) for item in v]
        kinds = {t for t, _ in tags}
        assert len(kinds) == 1
        return 9, bytes([tags[0][0]]) + struct.pack('>i', len(tags)) + b''.join(p for _,p in tags)
    raise AssertionError(type(v))


def pack_nbt(root):
    return gzip.compress(b'\x0a\x00\x00' + value(root)[1])


def make_jar(path, *, parent_y=2, child_y=0, parent_orientation='up_north', child_orientation='down_north', broken=False, modern=False):
    structure = {
        'type': 'minecraft:jigsaw', 'project_start_to_heightmap': 'WORLD_SURFACE_WG',
        'start_height': {'absolute': 0}, 'start_pool': 'minecraft:pillager_outpost/base_plates'
    }
    base_pool = {'elements': [{'element': {'element_type': 'minecraft:legacy_single_pool_element',
                                            'location': 'minecraft:pillager_outpost/base_plate',
                                            'projection': 'rigid'}, 'weight': 1}]}
    towers = {'elements': [{'element': {'element_type': 'minecraft:list_pool_element',
                                        'projection': 'rigid', 'elements': [
                                            {'element_type': 'minecraft:legacy_single_pool_element',
                                             'location': 'minecraft:pillager_outpost/watchtower', 'projection': 'rigid'},
                                            {'element_type': 'minecraft:legacy_single_pool_element',
                                             'location': 'minecraft:pillager_outpost/watchtower_overgrown', 'projection': 'rigid'}]}, 'weight': 1}]}
    base = {'size': [13, 3, 17], 'palette': [
        {'Name': 'minecraft:jigsaw', 'Properties': {'orientation': parent_orientation}}],
        'blocks': [{'state': 0, 'pos': [7, parent_y, 8], 'nbt': {
            'name': 'minecraft:base', 'target': 'minecraft:watchtower',
            'pool': 'minecraft:pillager_outpost/towers'}}]}
    tower = {'size': [15, 21, 15], 'palette': [
        {'Name': 'minecraft:jigsaw', 'Properties': {'orientation': child_orientation}}],
        'blocks': [{'state': 0, 'pos': [6, child_y, 6], 'nbt': {
            'name': 'minecraft:other' if broken else 'minecraft:watchtower',
            'target': 'minecraft:base', 'pool': 'minecraft:empty'}}]}
    if modern:
        for struct in (base, tower):
            struct['palette'] = [{'id': p['Name'], 'properties': p['Properties']} for p in struct['palette']]
    with zipfile.ZipFile(path, 'w') as jar:
        jar.writestr('data/minecraft/worldgen/structure/pillager_outpost.json', json.dumps(structure))
        jar.writestr('data/minecraft/worldgen/template_pool/pillager_outpost/base_plates.json', json.dumps(base_pool))
        jar.writestr('data/minecraft/worldgen/template_pool/pillager_outpost/towers.json', json.dumps(towers))
        jar.writestr('data/minecraft/structure/pillager_outpost/base_plate.nbt', pack_nbt(base))
        jar.writestr('data/minecraft/structure/pillager_outpost/watchtower.nbt', pack_nbt(tower))


class TowerGeometryTests(unittest.TestCase):
    def test_unique_rigid_connection_exact_vertical_delta(self):
        with tempfile.TemporaryDirectory() as temp:
            jar = Path(temp) / '1.21.8.jar'
            make_jar(jar, parent_y=2, child_y=0)
            blueprint = load_tower_blueprint(jar)
            self.assertEqual(blueprint.tower_min_y_from_base, 3)
            self.assertEqual(blueprint.tower_height, 21)
            self.assertEqual(blueprint.base_size, (13, 3, 17))
            self.assertEqual(predict_vertical(blueprint, -30), (-31, -28, -8))

    def test_malformed_attachment_must_not_guess_y(self):
        with tempfile.TemporaryDirectory() as temp:
            jar = Path(temp) / '1.21.8.jar'
            make_jar(jar, broken=True)
            with self.assertRaises(TowerGeometryError):
                load_tower_blueprint(jar)

    def test_horizontal_connectors_use_same_y_in_modern_palette(self):
        with tempfile.TemporaryDirectory() as temp:
            jar = Path(temp) / 'horizontal.jar'
            make_jar(jar, parent_y=2, child_y=1, parent_orientation='north_up',
                     child_orientation='south_up', modern=True)
            result = load_tower_blueprint(jar)
            self.assertEqual(result.tower_min_y_from_base, 1)

    def test_horizontal_root_attachment_is_not_supported(self):
        with tempfile.TemporaryDirectory() as temp:
            jar = Path(temp) / '1.21.8.jar'
            make_jar(jar, parent_orientation='east_up')
            with self.assertRaises(TowerGeometryError):
                load_tower_blueprint(jar)

    def test_shifted_child_connector_shifts_tower_height(self):
        with tempfile.TemporaryDirectory() as temp:
            jar = Path(temp) / '1.21.8.jar'
            make_jar(jar, parent_y=1, child_y=3)
            b = load_tower_blueprint(jar)
            self.assertEqual(b.tower_min_y_from_base, -1)
            self.assertEqual(predict_vertical(b, 69), (68, 67, 87))


if __name__ == '__main__':
    unittest.main()
