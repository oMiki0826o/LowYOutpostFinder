"""File: test_placement_assets.py
Modification: 2026-10-13 — check game archive placement configuration before seed scan.
"""
from __future__ import annotations

import json
import tempfile
import unittest
import zipfile
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from placement_assets import validate_placement_assets
from finder import main
from test_start_geometry import sample_jar


OUTPOST = {'structures': [{'structure': 'minecraft:pillager_outpost', 'weight': 1}],
           'placement': {'type': 'minecraft:random_spread', 'spacing': 32,
                         'separation': 8, 'salt': 165745296, 'frequency': 0.2,
                         'frequency_reduction_method': 'legacy_type_1',
                         'exclusion_zone': {'chunk_count': 10,
                                            'other_set': 'minecraft:villages'}}}
VILLAGES = {'structures': [{'structure': 'minecraft:village_plains', 'weight': 1}],
            'placement': {'type': 'minecraft:random_spread', 'spacing': 34,
                          'separation': 8, 'salt': 10387312}}


def add_assets(path: Path, *, new_spacing=32, village_spacing=34):
    outpost = json.loads(json.dumps(OUTPOST))
    village = json.loads(json.dumps(VILLAGES))
    outpost['placement']['spacing'] = new_spacing
    village['placement']['spacing'] = village_spacing
    with zipfile.ZipFile(path, 'a') as jar:
        jar.writestr('data/minecraft/worldgen/structure_set/pillager_outposts.json', json.dumps(outpost))
        jar.writestr('data/minecraft/worldgen/structure_set/villages.json', json.dumps(village))


class PlacementAssetTests(unittest.TestCase):
    def test_verified_supported_placement_from_archive(self):
        with tempfile.TemporaryDirectory() as td:
            jar = Path(td) / 'assets.jar'
            sample_jar(jar)
            add_assets(jar)
            assert validate_placement_assets(jar).supported
            out = Path(td) / 'candidates.csv'
            self.assertEqual(main(['candidates', '--seed', '123', '--radius', '4096',
                                   '--game-jar', str(jar), '--out', str(out)]), 0)
            self.assertTrue(out.exists())

    def test_changed_outpost_spacing_must_be_rejected_before_search(self):
        with tempfile.TemporaryDirectory() as td:
            jar = Path(td) / 'bad.jar'
            sample_jar(jar)
            add_assets(jar, new_spacing=35)
            with self.assertRaisesRegex(ValueError, 'spacing'):
                validate_placement_assets(jar)

    def test_changed_village_spacing_must_be_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            jar = Path(td) / 'bad.jar'
            sample_jar(jar)
            add_assets(jar, village_spacing=35)
            with self.assertRaisesRegex(ValueError, 'spacing'):
                validate_placement_assets(jar)

    def test_missing_placement_definition_is_not_treated_as_compatible(self):
        with tempfile.TemporaryDirectory() as td:
            jar = Path(td) / 'incomplete.jar'
            sample_jar(jar)
            with self.assertRaisesRegex(ValueError, 'pillager_outposts.json'):
                validate_placement_assets(jar)

if __name__ == '__main__':
    unittest.main()
