"""File: test_biome_assets.py
Modification: 2026-10-13 — test recursive vanilla biome tags without running terrain.
"""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from biome_assets import expand_biome_tag


class BiomeAssetTests(unittest.TestCase):
    def test_nested_tags_expand_only_allowed_biome_resource_ids(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp)/'assets.jar'
            with zipfile.ZipFile(path, 'w') as z:
                z.writestr('data/minecraft/tags/worldgen/biome/has_structure/pillager_outpost.json',
                           json.dumps({'values':['minecraft:plains','#minecraft:is_mountain']}))
                z.writestr('data/minecraft/tags/worldgen/biome/is_mountain.json',
                           json.dumps({'values':['minecraft:meadow','minecraft:cherry_grove']}))
            with zipfile.ZipFile(path) as z:
                self.assertEqual(expand_biome_tag(z, 'minecraft:has_structure/pillager_outpost'),
                                 ['minecraft:cherry_grove', 'minecraft:meadow', 'minecraft:plains'])

    def test_cycle_is_an_error_not_silent_acceptance(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp)/'bad.jar'
            with zipfile.ZipFile(path,'w') as z:
                z.writestr('data/minecraft/tags/worldgen/biome/a.json',
                           json.dumps({'values':['#minecraft:b']}))
                z.writestr('data/minecraft/tags/worldgen/biome/b.json',
                           json.dumps({'values':['#minecraft:a']}))
            with zipfile.ZipFile(path) as z:
                with self.assertRaisesRegex(ValueError, 'cycle'):
                    expand_biome_tag(z, 'minecraft:a')

    def test_optional_tag_does_not_suppress_cycle(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp)/'cycle.jar'
            with zipfile.ZipFile(path,'w') as z:
                z.writestr('data/minecraft/tags/worldgen/biome/a.json',
                           json.dumps({'values':[{'id':'#minecraft:b','required':False}]}))
                z.writestr('data/minecraft/tags/worldgen/biome/b.json',
                           json.dumps({'values':['#minecraft:a']}))
            with zipfile.ZipFile(path) as z:
                with self.assertRaisesRegex(ValueError, 'cycle'):
                    expand_biome_tag(z, 'minecraft:a')

    def test_missing_required_tag_fails_closed(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp)/'bad.jar'
            with zipfile.ZipFile(path,'w') as z:
                z.writestr('data/minecraft/tags/worldgen/biome/a.json',
                           json.dumps({'values':['#minecraft:missing']}))
            with zipfile.ZipFile(path) as z:
                with self.assertRaisesRegex(ValueError, 'Missing'):
                    expand_biome_tag(z, 'minecraft:a')

if __name__ == '__main__':
    unittest.main()
