"""File: test_explorer_cli.py
Modification: 2026-10-13 — regression tests for advanced CLI exports and failure modes.
"""
import csv
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class ExplorerCliTests(unittest.TestCase):
    def test_cli_rectangle_export_provisional_coordinates(self):
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / 'out.csv'
            coords = Path(td) / 'coords.txt'
            p = subprocess.run([sys.executable, '-m', 'lowy_outpost_finder.explorer', '--seed', '123',
                '--min-x', '-16', '--max-x', '16', '--min-z', '-16', '--max-z', '16',
                '--threads', '2', '--top', '500', '--out', str(out), '--export-tp', str(coords)],
                capture_output=True, text=True, cwd=ROOT)
            self.assertEqual(p.returncode, 0, p.stderr)
            with out.open(newline='', encoding='utf-8') as f:
                rows = list(csv.DictReader(f))
            self.assertGreater(len(rows), 5)
            self.assertTrue(all(x['classification'] == 'placement_candidate' for x in rows))
            self.assertTrue(all(not x['projected_surface_y'] for x in rows))
            self.assertNotIn('/tp ', coords.read_text(encoding='utf-8'))

    def test_cli_refuses_sort_y_without_y(self):
        with tempfile.TemporaryDirectory() as td:
            p = subprocess.run([sys.executable, '-m', 'lowy_outpost_finder.explorer', '--seed', '123',
                '--min-x', '-16', '--max-x', '16', '--min-z', '-16', '--max-z', '16',
                '--sort', 'y', '--out', str(Path(td) / 'out.csv')],
                capture_output=True, text=True, cwd=ROOT)
            self.assertNotEqual(p.returncode, 0)
            self.assertIn('Cannot sort placement-only', p.stderr)
            self.assertFalse((Path(td) / 'out.csv').exists())


if __name__ == '__main__':
    unittest.main()
