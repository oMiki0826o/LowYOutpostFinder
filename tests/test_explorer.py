"""File: test_explorer.py
Modification: 2026-10-13 — TDD acceptance tests for seed-only advanced explorer.
"""
import csv
from io import StringIO
from pathlib import Path
import tempfile
import threading
import unittest

from finder import candidates
from explorer import RegionBounds, load_seeds, candidate_area, Explorer, export_seed_list, export_teleports


class ExplorerTests(unittest.TestCase):
    def test_small_rectangular_region_agrees_with_original_finder(self):
        box = RegionBounds(-16, 16, -13, 17)
        expected = [x for x in candidates(123, 16384)
                    if box.min_x <= x['chunk_x'] // 32 <= box.max_x
                    and box.min_z <= x['chunk_z'] // 32 <= box.max_z]
        actual = list(candidate_area(123, box))
        self.assertEqual([(r['chunk_x'], r['chunk_z']) for r in actual],
                         [(r['chunk_x'], r['chunk_z']) for r in expected])

    def test_seed_file_preserves_order_and_deduplicates(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / 'seeds.txt'
            path.write_text('# comment\n-1\n3\n-1\n\n0\n', encoding='utf-8')
            self.assertEqual(load_seeds(path), [-1, 3, 0])

    def test_seed_file_rejects_invalid_out_of_range_and_empty(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / 'seeds.txt'
            for text in ('abc', str(2**63), '\n # empty\n'):
                p.write_text(text, encoding='utf-8')
                with self.assertRaises(ValueError):
                    load_seeds(p)

    def test_cancel_then_pause_and_resume(self):
        pause = threading.Event()
        cancel = threading.Event()
        pause.set()
        seen = []
        def progress(done, total, rows, eta):
            seen.append(done)
            cancel.set()
        search = Explorer('1.21.8', mode='candidates',
                          bounds=RegionBounds(-16, 16, -16, 16))
        rows = search.run([123, 456], pause=pause, cancel=cancel, progress=progress)
        self.assertEqual(seen, [1])
        self.assertTrue(all(r['seed'] == 123 for r in rows))

    def test_export_teleports_cannot_invent_y(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / 'tp.txt'
            export_teleports(p, [{'x': 128, 'z': -160, 'seed': 123,
                                  'classification': 'placement_candidate', 'projected_surface_y': ''}])
            t = p.read_text(encoding='utf-8')
            self.assertNotIn('/tp', t)
            self.assertIn('128', t)
            export_teleports(p, [{'x': 128, 'z': -160, 'seed': 123,
                                   'classification': 'estimated_only', 'projected_surface_y': '41'}])
            self.assertNotIn('/tp', p.read_text(encoding='utf-8'))
            export_teleports(p, [{'x': 128, 'z': -160, 'seed': 123,
                                   'status': 'verified_tower', 'base_plate_y': -12}])
            self.assertIn('/tp 128 -12 -160', p.read_text(encoding='utf-8'))

    def test_export_unique_seed_list(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / 'seeds.txt'
            export_seed_list(p, [{'seed': 3}, {'seed': 3}, {'seed': -8}])
            self.assertEqual(p.read_text(encoding='utf-8'), '3\n-8\n')

    def test_sort_by_y_rejects_non_y_candidates(self):
        search = Explorer('1.21.8', mode='candidates', bounds=RegionBounds(-2, 2, -2, 2))
        with self.assertRaises(ValueError):
            search.sort_rows([{'classification': 'placement_candidate'}], 'y')

    def test_region_limit_and_order_rejected(self):
        for box in ((3, 1, 0, 2), (-8000, 8000, -8000, 8000)):
            with self.assertRaises(ValueError):
                RegionBounds(*box)


if __name__ == '__main__':
    unittest.main()
