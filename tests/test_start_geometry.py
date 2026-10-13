"""File: test_start_geometry.py
Modification: 2026-10-13 — original 1.21.8 Jigsaw start placement checks.
"""
from pathlib import Path
import gzip
import json
import struct
import subprocess
import tempfile
import unittest
import shutil
import sys
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from start_geometry import projection, load_outpost_assets, geometry_for_rotation


def nbt_size(x, y, z):
    # NBT Compound(root) -> int list size
    name = b'size'
    data = b'\x0a\x00\x00' + b'\x09' + struct.pack('>H', len(name)) + name + b'\x03' + struct.pack('>i', 3) + struct.pack('>iii', x, y, z) + b'\x00'
    return gzip.compress(data)


def sample_jar(path, *, invalid=False):
    with zipfile.ZipFile(path, 'w') as jar:
        jar.writestr('data/minecraft/worldgen/structure/pillager_outpost.json', json.dumps({
            'type': 'minecraft:jigsaw', 'project_start_to_heightmap': 'WORLD_SURFACE_WG',
            'start_height': {'absolute': 0}, 'start_pool': 'minecraft:pillager_outpost/base_plates',
        }))
        jar.writestr('data/minecraft/worldgen/template_pool/pillager_outpost/base_plates.json', json.dumps({
            'elements': [{'element': {'element_type': 'minecraft:legacy_single_pool_element',
                         'location': 'minecraft:pillager_outpost/base_plate', 'projection': 'rigid'}, 'weight': 1}]
        }))
        jar.writestr('data/minecraft/structure/pillager_outpost/base_plate.nbt', nbt_size(13, 1, 17 if not invalid else 0))


class GeometryTests(unittest.TestCase):
    def test_rotated_bounding_box_center_and_negative_coordinates(self):
        # Template transformAround() rotates about block origin and Java / truncates toward zero.
        self.assertEqual(geometry_for_rotation(-512, -32, 13, 17, 0), (-506, -24))
        self.assertEqual(geometry_for_rotation(-512, -32, 13, 17, 1), (-520, -26))
        self.assertEqual(geometry_for_rotation(-512, -32, 13, 17, 2), (-518, -40))
        self.assertEqual(geometry_for_rotation(-512, -32, 13, 17, 3), (-504, -38))
        self.assertEqual(geometry_for_rotation(-16, 0, 2, 2, 0), (-15, 0))

    def test_assets_read_from_version_jar_and_malformed_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            jar = Path(temp) / 'client.jar'
            sample_jar(jar)
            data = load_outpost_assets(jar)
            self.assertEqual(data.size, (13, 1, 17))
            self.assertEqual(len(data.sha256), 64)
            sample_jar(jar, invalid=True)
            with self.assertRaises(ValueError):
                load_outpost_assets(jar)

    def test_real_placement_reference_vectors(self):
        # Expected values generated independently with Java 21 java.util.Random.
        tool = Path(__file__).with_name('StartProjectionOracle.java')
        if not shutil.which('javac') or not shutil.which('java'):
            self.skipTest('JDK unavailable')
        with tempfile.TemporaryDirectory() as tmp:
            subprocess.run(['javac', '-d', tmp, str(tool)], check=True)
            for seed, cx, cz in [(0, 0, 0), (123, -432, 122), (-1, -1, -1),
                                  (-(1 << 63), -23, 99), ((1 << 63) - 1, 44, -444)]:
                result = subprocess.check_output(['java', '-cp', tmp, 'StartProjectionOracle',
                                                  str(seed), str(cx), str(cz), '13', '17'], text=True)
                expected = tuple(int(i) for i in result.split(','))
                output = projection(seed, cx, cz, (13, 1, 17))
                self.assertEqual((output.rotation, output.sample_x, output.sample_z), expected)


if __name__ == '__main__':
    import shutil
    unittest.main()
