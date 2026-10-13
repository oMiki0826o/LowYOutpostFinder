"""File: test_finder.py
Modification: 2026-10-12 — offline unit, property, fixture and independent Java RNG regression tests.
"""
from __future__ import annotations

import csv
import gzip
import io
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest
import zlib

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import finder
from nbt import NBTError, Region, parse_nbt


# ── Minimal Java NBT test fixture writer (not used by production code) ──
def tag(name, value):
    if isinstance(value, dict):
        return bytes([10]) + name_bytes(name) + compound(value)
    if isinstance(value, str):
        return bytes([8]) + name_bytes(name) + name_bytes(value)
    if isinstance(value, list):
        if len(value) == 6 and all(isinstance(i, int) for i in value):
            # Explicit int-array for BB fixture.
            return bytes([11]) + name_bytes(name) + struct.pack('>i', len(value)) + struct.pack('>6i', *value)
        if value and all(isinstance(item, dict) for item in value):
            return (bytes([9]) + name_bytes(name) + struct.pack('>Bi', 10, len(value)) +
                    b''.join(compound(item) for item in value))
        if value == []:
            return bytes([9]) + name_bytes(name) + struct.pack('>Bi', 10, 0)
    if isinstance(value, int):
        return bytes([4]) + name_bytes(name) + struct.pack('>q', value)
    raise TypeError(f'unsupported fixture value: {name}={value}')


def name_bytes(name):
    encoded = name.encode('utf-8')
    return struct.pack('>H', len(encoded)) + encoded


def compound(contents):
    return b''.join(tag(k, v) for k, v in contents.items()) + b'\0'


def nbt(contents):
    return b'\x0a\0\0' + compound(contents)


def generated_world(root: Path, seed=123, chunk_x=-1, chunk_z=2, complete=True, tower=True,
                    data_version=4440, version_name=None):
    root.mkdir(parents=True, exist_ok=True)
    (root / 'region').mkdir(exist_ok=True)
    level_data = {'DataVersion': data_version, 'WorldGenSettings': {'seed': seed}, 'LevelName': 'TestFixture'}
    if version_name:
        level_data['Version'] = {'Name': version_name}
    (root / 'level.dat').write_bytes(gzip.compress(nbt({'Data': level_data})))
    x, z = chunk_x, chunk_z
    base = {'id': 'minecraft:jigsaw', 'BB': [-16, -50, 32, -1, -50, 47],
            'pool_element': {'location': 'minecraft:pillager_outpost/base_plate'}}
    pieces = [base]
    if tower:
        pieces.append({'id': 'minecraft:jigsaw', 'BB': [-15, -50, 33, -2, -29, 46],
                       'pool_element': {'elements': [
                           {'location': 'minecraft:pillager_outpost/watchtower'},
                           {'location': 'minecraft:pillager_outpost/watchtower_overgrown'}]}})
    structure = {'id': 'minecraft:pillager_outpost', 'ChunkX': x, 'ChunkZ': z, 'Children': pieces}
    record = {'xPos': x, 'zPos': z, 'DataVersion': data_version,
              'Status': 'minecraft:full' if complete else 'minecraft:structure_starts',
              'structures': {'starts': {'minecraft:pillager_outpost': structure}}}
    compressed = zlib.compress(nbt(record))
    frame = struct.pack('>iB', len(compressed) + 1, 2) + compressed
    buffer = bytearray(3 * 4096)
    idx = (x & 31) + (z & 31) * 32
    buffer[idx * 4:idx * 4 + 4] = bytes([0, 0, 2, 1])
    buffer[2 * 4096:2 * 4096 + len(frame)] = frame
    (root / 'region' / f'r.{x // 32}.{z // 32}.mca').write_bytes(buffer)
    return record


class FinderTests(unittest.TestCase):
    def test_empty_region_placeholder_is_read_as_empty(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'r.-2.-1.mca'
            path.touch()
            with Region(path) as region:
                self.assertEqual(region.length, 0)
                self.assertIsNone(region.read_chunk(-33, -1))

    def test_primitive_bounded_java_random(self):
        self.assertEqual(finder.JavaRandom(0).bits(32), 0xbb20b460)
        self.assertEqual(finder.JavaRandom(-1).bounded(5), 3)
        self.assertEqual(finder.region_position(123, 0, 0, finder.OUTPOST),
                         finder.region_position(123, 0, 0, finder.OUTPOST))

    def test_example_placement_properties(self):
        for seed in (0, 123, -1, -(1 << 63), (1 << 63)-1):
            seen = set()
            for row in finder.candidates(seed, 4096):
                cx, cz = row['chunk_x'], row['chunk_z']
                self.assertTrue(finder.pass_legacy_frequency(seed, cx, cz))
                self.assertTrue(finder.pass_village_exclusion(seed, cx, cz))
                self.assertEqual(row['x'], cx * 16)
                self.assertEqual(row['z'], cz * 16)
                self.assertNotIn((cx, cz), seen)
                seen.add((cx, cz))

    @unittest.skipUnless(shutil.which('java') and shutil.which('javac'), 'Java JDK not installed')
    def test_independent_java_oracle(self):
        root = Path(__file__).resolve().parent
        with tempfile.TemporaryDirectory() as tmp:
            subprocess.run(['javac', '-d', tmp, str(root / 'PlacementOracle.java')], check=True)
            for seed in ('0', '123', '-1', '-9223372036854775808', '9223372036854775807'):
                java = subprocess.run(['java', '-cp', tmp, 'PlacementOracle', seed, '4096'],
                                      capture_output=True, text=True, check=True)
                from_java = [(int(r['chunk_x']), int(r['chunk_z']))
                             for r in csv.DictReader(io.StringIO(java.stdout))]
                ours = [(r['chunk_x'], r['chunk_z']) for r in finder.candidates(int(seed), 4096)]
                self.assertEqual(ours, from_java, seed)

    def test_negative_region_exact_bbox_from_nbt(self):
        with tempfile.TemporaryDirectory() as td:
            world = Path(td)
            generated_world(world)
            data, seed = finder.confirmed_world(world)
            self.assertEqual(seed, 123)
            with finder.WorldChunks(world) as chunk_source:
                row = finder.examine(chunk_source.get(-1, 2), seed, -1, 2)
                missing = finder.examine(chunk_source.get(-2, 2), seed, -2, 2)
            self.assertEqual(row['status'], 'verified_tower')
            self.assertEqual(row['base_plate_y'], -50)
            self.assertEqual(row['watchtower_max_y'], -29)
            self.assertEqual(missing['status'], 'not_generated')

    def test_not_full_vs_confirmed(self):
        with tempfile.TemporaryDirectory() as td:
            world = Path(td)
            generated_world(world, complete=False)
            with finder.WorldChunks(world) as source:
                row = finder.examine(source.get(-1, 2), 123, -1, 2)
            self.assertEqual(row['status'], 'not_full')

    def test_synthetic_26_3_world_and_csv_version(self):
        # This is a synthetic NBT fixture, NOT a real vanilla 26.3 generated world.
        with tempfile.TemporaryDirectory() as td:
            world = Path(td)
            generated_world(world, data_version=5023, version_name='26.3')
            data, seed = finder.confirmed_world(world, '26.3')
            self.assertEqual(seed, 123)
            with self.assertRaisesRegex(ValueError, 'cross-version'):
                finder.confirmed_world(world, '1.21.8')
            args = SimpleNamespace(world=world, version='auto', radius=None,
                                   max_y=0, out=world / 'out.csv')
            finder.run_world(args)
            with args.out.open() as f:
                rows = list(csv.DictReader(f))
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]['version'], '26.3')
            self.assertEqual(rows[0]['base_plate_y'], '-50')
            with finder.WorldChunks(world) as ws:
                row = finder.examine(ws.get(-1, 2), 123, -1, 2, data_version=5023)
            self.assertEqual(row['status'], 'verified_tower')
            candidate = world / 'candidate.csv'
            candidate.write_text('version,seed,chunk_x,chunk_z,x,z\n1.21.8,123,-1,2,-16,32\n')
            with self.assertRaisesRegex(ValueError, 'Version mismatch'):
                finder.load_candidates(candidate, 123, '26.3')

    def test_live_search_filter_with_mock_rcon(self):
        # Verify CLI result wiring only: fake RCON result, not Minecraft ground truth.
        with tempfile.TemporaryDirectory() as td:
            world = Path(td)
            generated_world(world)
            row = finder.base_row(123, -1, 2, status='verified_tower')
            row.update(version='1.21.8', base_plate_y=-50, watchtower_min_y=-50,
                       watchtower_max_y=-29, piece_count=2)
            args = SimpleNamespace(world=world, version='auto', radius=2048,
                    limit=1, priority='near-origin', core_archive=None,
                    audit=world / 'audit.csv', out=world / 'result.csv', max_y=0)
            with patch('live.run_live', return_value=[row]):
                finder.run_search_live(args)
            with args.out.open() as fp:
                result = list(csv.DictReader(fp))
            self.assertEqual(result[0]['version'], '1.21.8')
            self.assertEqual(result[0]['status'], 'verified_tower')

    def test_live_search_filters_on_verified_structure_center(self):
        with tempfile.TemporaryDirectory() as td:
            world = Path(td)
            generated_world(world)
            low = finder.base_row(123, -1, 2, status='verified_tower')
            low.update(version='1.21.8', base_plate_y=-60, watchtower_min_y=-60,
                       watchtower_max_y=-39, structure_min_y=-60,
                       structure_max_y=-20, structure_center_y=-40, piece_count=2)
            args = SimpleNamespace(world=world, version='auto', radius=2048,
                    limit=1, priority='near-origin', core_archive=None,
                    audit=world / 'audit.csv', out=world / 'result.csv', max_y=None,
                    center_y_below=-37)
            with patch('live.run_live', return_value=[low]):
                finder.run_search_live(args)
            with args.out.open() as fp:
                result = list(csv.DictReader(fp))
            self.assertEqual(len(result), 1)
            self.assertEqual(result[0]['structure_center_y'], '-40')

    def test_seed_verification(self):
        with tempfile.TemporaryDirectory() as td:
            world = Path(td)
            generated_world(world, seed=123)
            csv_path = world / 'candidates.csv'
            csv_path.write_text('seed,chunk_x,chunk_z,x,z\n42,-1,2,-16,32\n')
            with self.assertRaisesRegex(ValueError, 'Seed mismatch'):
                finder.load_candidates(csv_path, 123)

    def test_invalid_nbt_length(self):
        with self.assertRaises(NBTError):
            parse_nbt(b'\x0a\0\0\x0b\0\x02BB\xff\xff\xff\xff\0')

    def test_version_guard(self):
        with tempfile.TemporaryDirectory() as td:
            world = Path(td)
            generated_world(world)
            level = nbt({'Data': {'DataVersion': 4441, 'WorldGenSettings': {'seed': 123}}})
            (world / 'level.dat').write_bytes(gzip.compress(level))
            with self.assertRaisesRegex(ValueError, 'Version.Name'):
                finder.confirmed_world(world)

    def test_commands_do_not_execute(self):
        with tempfile.TemporaryDirectory() as td:
            directory = Path(td)
            fn = directory / 'candidate.csv'
            fn.write_text('seed,chunk_x,chunk_z,x,z\n123,-1,2,-16,32\n', encoding='utf-8')
            args = type('Arg', (), {'candidates': fn, 'max_chunks': 3, 'out': directory / 'cmd.txt'})()
            finder.run_commands(args)
            data = args.out.read_text()
            self.assertIn('forceload add -16 32', data)
            self.assertIn('save-all flush', data)
            self.assertIn('# forceload remove -16 32', data)


if __name__ == '__main__':
    unittest.main()
