"""File: test_worldgen_contract.py
Modification: 2026-10-13 — exact asset dependency and provenance checks, not noise parity.
"""
import json
from pathlib import Path
import sys
import tempfile
import unittest
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from worldgen_contract import inspect_contract

ROOT = 'data/minecraft/worldgen/'


def fixture(path, *, bad_ref=False, cycle=False):
    with zipfile.ZipFile(path, 'w') as z:
        z.writestr('version.json', json.dumps({'id': '1.21.8'}))
        z.writestr(ROOT+'structure/pillager_outpost.json', '{}')
        z.writestr(ROOT+'noise_settings/overworld.json', json.dumps({
            'noise': {'min_y': -64, 'height': 384},
            'noise_router': {'final_density': 'minecraft:overworld/start',
                             'temperature': {'type': 'minecraft:noise',
                                             'noise': 'minecraft:temperature',
                                             'xz_scale': 1, 'y_scale': 0}}}))
        z.writestr(ROOT+'density_function/overworld/start.json', json.dumps(
            'minecraft:overworld/start' if cycle else {'type':'minecraft:add',
               'argument1': 'minecraft:overworld/not_exists' if bad_ref else 0,
               'argument2': {'type': 'minecraft:noise', 'noise':'minecraft:temperature'}}))
        z.writestr(ROOT+'noise/temperature.json', json.dumps({'firstOctave': -10, 'amplitudes': [1]}))
    return path


class ContractTests(unittest.TestCase):
    def test_resolves_real_resources_and_records_both_hashes(self):
        with tempfile.TemporaryDirectory() as d:
            path = fixture(Path(d)/'game.jar')
            result = inspect_contract(path, '1.21.8')
            self.assertEqual(result['version'], '1.21.8')
            self.assertEqual(result['noise_settings']['min_y'], -64)
            self.assertEqual(result['noise_settings']['height'], 384)
            self.assertEqual(result['density_files_visited'], 1)
            self.assertEqual(result['noise_files_visited'], 1)
            self.assertEqual(len(result['sha256']['worldgen_settings']), 64)
            self.assertFalse(result['seed_equivalence_proven'])

    def test_missing_density_asset_fails_closed(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaisesRegex(ValueError, 'not_exists'):
                inspect_contract(fixture(Path(d)/'game.jar', bad_ref=True), '1.21.8')

    def test_cyclic_density_asset_fails_closed(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaisesRegex(ValueError, 'Cyclic'):
                inspect_contract(fixture(Path(d)/'game.jar', cycle=True), '1.21.8')

    def test_builtin_large_biomes_registry_does_not_silently_use_overworld_json(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaisesRegex(ValueError, 'builtin'):
                inspect_contract(fixture(Path(d)/'game.jar'), '1.21.8', preset='large_biomes')

    def test_mismatched_game_version_fails_before_asset_scan(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaisesRegex(ValueError, 'mismatch'):
                inspect_contract(fixture(Path(d)/'game.jar'), '26.3')


if __name__ == '__main__':
    unittest.main()
