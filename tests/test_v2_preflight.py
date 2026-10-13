"""File: test_v2_preflight.py
Modification: 2026-10-13 — Minecraft executable/asset checks must not create a world or accept EULA.
"""
import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch
from finder import main
from test_bundled_assets import bundle
from test_tower_geometry import make_jar
from test_placement_assets import add_assets

class PreflightTests(unittest.TestCase):
    def test_game_preflight_validates_jar_runtime_and_reports_unverified_e2e(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);inner=root/'inner.jar';make_jar(inner);add_assets(inner)
            jar=bundle(root/'server.jar',inner.read_bytes())
            out=root/'check.json'
            with patch('vanilla_oracle.subprocess.run',return_value=SimpleNamespace(
                       returncode=0,stdout='',stderr='openjdk version "21.0.3"')):
                self.assertEqual(main(['server-check','--version','1.21.8',
                     '--server-jar',str(jar),'--java','java','--out',str(out)]),0)
            data=json.loads(out.read_text())
            self.assertEqual(data['game_version'],'1.21.8')
            self.assertEqual(data['java_runtime'],21)
            self.assertTrue(data['placement_parameters_match'])
            self.assertFalse(data['vanilla_world_generated'])
            self.assertFalse(data['exact_seed_only_height_ready'])
            self.assertFalse((root/'eula.txt').exists())
            self.assertFalse((root/'world').exists())

if __name__=='__main__': unittest.main()
