"""File: test_server_asset_audit.py
Modification: 2026-10-13 — inspect bundle metadata without launching Minecraft.
"""
from pathlib import Path
import json
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace
import zipfile

from test_bundled_assets import bundle
from test_tower_geometry import make_jar
from test_placement_assets import add_assets
from lowy_outpost_finder.cli import main


class ServerAssetAuditTests(unittest.TestCase):
    def test_offline_report_with_bundled_game_data(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            inner = root / 'game.jar'
            make_jar(inner)
            add_assets(inner)
            # Biome tag is required for recognizing eligible biomes.
            with zipfile.ZipFile(inner, 'a') as f:
                f.writestr('data/minecraft/tags/worldgen/biome/has_structure/pillager_outpost.json',
                           json.dumps({'replace': False, 'values': ['minecraft:plains']}))
            jar = bundle(root / 'server.jar', inner.read_bytes())
            report = root / 'assets.json'
            code = main(['assets-audit', '--version','1.21.8','--server-jar',str(jar),
                         '--out',str(report)])
            self.assertEqual(code, 0)
            result = json.loads(report.read_text())
            self.assertEqual(result['game_version'], '1.21.8')
            self.assertTrue(result['placement_validated'])
            self.assertEqual(result['biomes'], ['minecraft:plains'])
            self.assertEqual(result['tower_y_offset'], 3)
            self.assertFalse(result['terrain_noise_verified'])
            self.assertFalse(result['vanilla_e2e_verified'])

    def test_rejects_missing_biome_tag(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            inner = root / 'inner.jar'
            make_jar(inner)
            add_assets(inner)
            jar = bundle(root / 'server.jar', inner.read_bytes())
            report = root / 'results.json'
            self.assertEqual(main(['assets-audit','--version','1.21.8',
                                   '--server-jar',str(jar), '--out',str(report)]), 2)
            self.assertFalse(report.exists())

    def test_rejects_version_mismatch_in_report(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            inner = root / 'inner.jar'
            make_jar(inner)
            add_assets(inner)
            jar = bundle(root / 'server.jar', inner.read_bytes())
            self.assertEqual(main(['assets-audit','--version','26.3',
                                   '--server-jar',str(jar)]), 2)

    def test_official_263_data_version_must_match_world(self):
        from lowy_outpost_finder.versions import detect_world_version
        self.assertEqual(detect_world_version({'DataVersion': 5023, 'Version': {'Name': '26.3'}}), ('26.3', 5023))
        with self.assertRaisesRegex(ValueError, 'DataVersion'):
            detect_world_version({'DataVersion': 4999, 'Version': {'Name': '26.3'}})

    def test_java_runtime_requirement_detected_before_server_launch(self):
        from lowy_outpost_finder.vanilla_oracle import ensure_compatible_java
        with patch('lowy_outpost_finder.vanilla_oracle.subprocess.run', return_value=
                   SimpleNamespace(returncode=0, stdout='', stderr='openjdk version \"21.0.5\"')):
            with self.assertRaisesRegex(ValueError, 'Java 25'):
                ensure_compatible_java('java', {'java_version':25})
            self.assertEqual(ensure_compatible_java('java', {'java_version':21}), 21)
        with patch('lowy_outpost_finder.vanilla_oracle.subprocess.run', return_value=
                   SimpleNamespace(returncode=0, stdout='', stderr='openjdk version \"17.0.9\"')):
            with self.assertRaisesRegex(ValueError, 'Java 21'):
                ensure_compatible_java('java', {'java_version':21})

if __name__ == '__main__':
    unittest.main()
