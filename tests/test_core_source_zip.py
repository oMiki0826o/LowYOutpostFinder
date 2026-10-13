"""File: test_core_source_zip.py
Modification: 2026-10-13 — optional LowYSwampHut ZIP sources and safe extraction.
"""
from __future__ import annotations
from pathlib import Path
import sys
import tempfile
import unittest
import zipfile
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))

class CoreZipTests(unittest.TestCase):
    def test_extracts_valid_zip_source_layout(self):
        from extract_core import extract_zip_source
        with tempfile.TemporaryDirectory() as td:
            source = Path(td) / 'ref.zip'
            with zipfile.ZipFile(source, 'w') as z:
                z.writestr('repo/lysh-c/src/rng.c', 'int rng(void){return 42;}\n')
            dest = Path(td) / 'dest'
            extract_zip_source(source, dest)
            self.assertTrue((dest / 'repo/lysh-c/src/rng.c').is_file())

    def test_rejects_path_traversal_without_writing_any_member(self):
        from extract_core import extract_zip_source
        with tempfile.TemporaryDirectory() as td:
            source = Path(td) / 'evil.zip'
            with zipfile.ZipFile(source, 'w') as z:
                z.writestr('repo/lysh-c/src/rng.c', 'okay')
                z.writestr('../outside.txt', 'hijack')
            dest = Path(td) / 'dest'
            with self.assertRaisesRegex(ValueError, 'Unsafe'):
                extract_zip_source(source, dest)
            self.assertFalse((Path(td) / 'outside.txt').exists())
            self.assertFalse((dest / 'repo/lysh-c/src/rng.c').exists())

if __name__ == '__main__':
    unittest.main()
