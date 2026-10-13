"""File: test_bundled_assets.py
Modification: 2026-10-13 — regression for official server bundle asset extraction.
"""
from __future__ import annotations

import io
from contextlib import redirect_stderr
import json
import io as stream_io
from pathlib import Path
import sys
import tempfile
import unittest
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from test_placement_assets import add_assets
from test_tower_geometry import make_jar
from placement_assets import validate_placement_assets
from start_geometry import load_outpost_assets
from tower_geometry import load_tower_blueprint


def bundle(path: Path, inner: bytes, version='1.21.8') -> Path:
    with zipfile.ZipFile(path, 'w') as jar:
        jar.writestr('version.json', json.dumps({'id': version, 'world_version': 4440, 'java_version': 21}))
        jar.writestr('META-INF/versions.list', f'fakehash\t{version}\t{version}/server-{version}.jar\n')
        jar.writestr(f'META-INF/versions/{version}/server-{version}.jar', inner)
    return path


class BundledAssetsTests(unittest.TestCase):
    def test_bundle_has_same_placement_and_templates_as_inner(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            inner_path = root / 'inner.jar'
            make_jar(inner_path)
            add_assets(inner_path)
            outer = bundle(root / 'bundle.jar', inner_path.read_bytes())
            self.assertEqual(validate_placement_assets(outer), validate_placement_assets(inner_path))
            self.assertEqual(load_outpost_assets(outer).size, load_outpost_assets(inner_path).size)
            self.assertEqual(load_tower_blueprint(outer), load_tower_blueprint(inner_path))

    def test_refuses_duplicate_internal_game_jars(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / 'bad.jar'
            with zipfile.ZipFile(path, 'w') as jar:
                jar.writestr('META-INF/versions/1.21.8/server-a.jar', b'bad')
                jar.writestr('META-INF/versions/1.21.8/server-b.jar', b'bad')
            from game_archive import open_game_assets
            with self.assertRaisesRegex(ValueError, 'single|multiple|Ambiguous'):
                with open_game_assets(path):
                    pass

    def test_invalid_embedded_archive_is_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            path = bundle(Path(td) / 'bad.jar', b'not a game archive')
            from game_archive import open_game_assets
            with self.assertRaisesRegex(ValueError, 'embedded|inner'):
                with open_game_assets(path):
                    pass

    def test_bundle_version_mismatch_is_rejected_for_candidate_scan(self):
        from finder import main
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            inner = root / 'inner.jar'
            make_jar(inner)
            add_assets(inner)
            outer = bundle(root / 'bundle.jar', inner.read_bytes())
            result = root / 'result.csv'
            self.assertEqual(main(['candidates','--version','26.3','--seed','123',
                '--radius','4096','--game-jar',str(outer),'--out',str(result)]), 2)
            self.assertFalse(result.exists())
    def test_estimator_refuses_unmatched_game_jar_before_native_work(self):
        from finder import main
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            raw = root / 'inner.jar'
            make_jar(raw)
            bundled = bundle(root / 'server.jar', raw.read_bytes(), version='26.3')
            error_text = stream_io.StringIO()
            with redirect_stderr(error_text):
                code = main(['estimate','--version','1.21.8','--seed','123',
                             '--radius','1024','--game-jar',str(bundled),
                             '--core-archive',str(root / 'nonexistent.tar.gz')])
            self.assertEqual(code, 2)
            self.assertIn('version mismatch', error_text.getvalue())



if __name__ == '__main__':
    unittest.main()
