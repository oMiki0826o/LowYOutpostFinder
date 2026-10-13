"""File: test_release.py
Modification: 2026-10-12 — safe source release packaging regression tests.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
import sys
import tempfile
import unittest
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from package_release import package


class ReleaseTests(unittest.TestCase):
    def test_does_not_bundle_builds_secrets_or_private_folders(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / 'project'
            root.mkdir()
            (root / 'VERSION').write_text('2.1.0\n')
            (root / 'README.md').write_text('Read me\n')
            (root / 'LowYOutpostFinder.py').write_text('print("hello")\n')
            package_dir = root / 'lowy_outpost_finder'
            package_dir.mkdir()
            (package_dir / 'cli.py').write_text('def main(): return 0\n')
            for name in ('.git/config', '.build/temp.o', 'bin/scanner', 'data/secret.txt',
                         'results/hits.csv', 'world/region/r.0.0.mca', '__pycache__/hi.pyc',
                         '.env', 'server.properties'):
                file = root / name
                file.parent.mkdir(parents=True, exist_ok=True)
                file.write_text('private')
            zip_path = Path(td) / 'dist.zip'
            package(root, zip_path)
            with zipfile.ZipFile(zip_path) as z:
                files = z.namelist()
                self.assertIn('project/VERSION', files)
                self.assertIn('project/LowYOutpostFinder.py', files)
                self.assertIn('project/lowy_outpost_finder/cli.py', files)
                self.assertIn('project/SHA256SUMS.txt', files)
                self.assertTrue(all('private' not in z.read(name).decode() for name in files))
                self.assertEqual(z.testzip(), None)

    def test_archive_members_have_provided_hashes(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / 'project'
            root.mkdir()
            (root / 'VERSION').write_text('2.1.0\n')
            (root / 'hello.txt').write_bytes(b'hello\n')
            out = Path(td) / 'out.zip'
            package(root, out)
            with zipfile.ZipFile(out) as z:
                manifest = z.read('project/SHA256SUMS.txt').decode()
                digest = hashlib.sha256(b'hello\n').hexdigest()
                self.assertIn(f'{digest}  hello.txt', manifest)
                self.assertEqual(z.read('project/hello.txt'), b'hello\n')


if __name__ == '__main__':
    unittest.main()
