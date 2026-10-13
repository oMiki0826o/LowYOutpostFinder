"""File: test_full_map.py
Modification: 2026-10-13 — exhaustive seed-placement scan, bounded results and durable continuation.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from finder import candidates


class FullMapTests(unittest.TestCase):
    def test_world_grid_covers_both_signed_borders_without_allocating(self):
        from full_map import RegionGrid
        grid = RegionGrid(-29999984, 29999984, -29999984, 29999984)
        self.assertGreater(grid.total, 13_000_000_000)
        self.assertEqual(grid.row_col(0), (grid.rx_min, grid.rz_min))
        self.assertEqual(grid.row_col(grid.total - 1), (grid.rx_max, grid.rz_max))

    def test_rectangle_placement_equals_bounded_reference_search(self):
        from full_map import RegionGrid, scan_python
        seed = -123456789
        grid = RegionGrid(-2048, 2048, -2048, 2048)
        winners, matched = scan_python(grid, seed, 0, grid.total, 300, 0, 0)
        ref = list(candidates(seed, 2048))
        self.assertEqual(matched, len(ref))
        self.assertEqual({(r[0], r[1]) for r in winners},
                         {(r['chunk_x'], r['chunk_z']) for r in ref})

    def test_batch_resume_equals_uninterrupted_and_rejects_changed_parameters(self):
        from full_map import ScanConfig, scan
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            out = root / 'partial.csv'
            cfg = ScanConfig(version='1.21.8', seed=123, x_min=-4096, x_max=4096,
                             z_min=-4096, z_max=4096, center_x=100, center_z=-30,
                             top=5, batch_regions=8, sleep_ms=0, engine='python')
            result = scan(cfg, out, max_batches=2)
            self.assertEqual(result['status'], 'incomplete')
            self.assertEqual(result['processed_regions'], 16)
            with self.assertRaisesRegex(ValueError, 'checkpoint'):
                scan(ScanConfig(**{**cfg.__dict__, 'seed': 456}), out, resume=True)
            result = scan(cfg, out, resume=True)
            self.assertEqual(result['status'], 'complete')
            with out.open(newline='', encoding='utf-8') as fp:
                resumed = list(csv.DictReader(fp))
            other = root / 'complete.csv'
            expected = scan(cfg, other)
            self.assertEqual(result['placement_candidates'], expected['placement_candidates'])
            with other.open(encoding='utf-8', newline='') as fp:
                self.assertEqual(resumed, list(csv.DictReader(fp)))
            self.assertLessEqual(len(resumed), cfg.top)
            self.assertTrue(all(r['classification'] == 'placement_candidate' for r in resumed))


    def test_corrupted_checkpoint_candidate_is_rejected(self):
        from full_map import ScanConfig, scan
        with tempfile.TemporaryDirectory() as folder:
            out = Path(folder) / 'bad.csv'
            cfg = ScanConfig('1.21.8', 123, -1024, 1024, -1024, 1024,
                             0, 0, 5, 12, 0, 'python')
            scan(cfg, out, max_batches=1)
            state_path = out.with_suffix('.state.json')
            state = json.loads(state_path.read_text())
            state['retained'] = [[0, 0]]
            state_path.write_text(json.dumps(state))
            with self.assertRaisesRegex(ValueError, 'checkpoint'):
                scan(cfg, out, resume=True)

    def test_rejects_overwriting_state_or_output_without_resume(self):
        from full_map import ScanConfig, scan
        with tempfile.TemporaryDirectory() as folder:
            out = Path(folder) / 'x.csv'
            cfg = ScanConfig('1.21.8', 123, -1024, 1024, -1024, 1024,
                             0, 0, 5, 10, 0, 'python')
            scan(cfg, out, max_batches=1)
            with self.assertRaisesRegex(ValueError, 'existing'):
                scan(cfg, out)

    @unittest.skipUnless(shutil.which('cc') or shutil.which('clang') or shutil.which('gcc'), 'No C compiler')
    def test_native_same_as_python_for_negative_cells_and_long_seeds(self):
        from full_map import RegionGrid, scan_python, scan_native
        with tempfile.TemporaryDirectory() as folder:
            binpath = Path(folder) / 'region_scan'
            compiler = shutil.which('cc') or shutil.which('clang') or shutil.which('gcc')
            subprocess.run([compiler, '-O2', '-std=c11', '-Wall', '-Wextra',
                            str(ROOT / 'src' / 'region_scan.c'), '-o', str(binpath)], check=True,
                           capture_output=True, text=True)
            grid = RegionGrid(-3000, 5000, -4000, 4000)
            for seed in (0, 123, -9, 9223372036854775807, -9223372036854775808):
                py_hits, py_total = scan_python(grid, seed, 0, grid.total, 7, -500, 1000)
                c_hits, c_total = scan_native(grid, seed, 0, grid.total, 7, -500, 1000, binpath)
                self.assertEqual(py_total, c_total)
                self.assertEqual(sorted(py_hits), sorted(c_hits))


    def test_global_nearest_matches_exhaustive_bruteforce(self):
        from full_map import RegionGrid, scan_python, scan_nearest
        grid = RegionGrid(-10000, 12000, -12000, 9000)
        for seed, x, z in ((123, 0, 0), (-19, -9999, 8100),
                           (9223372036854775807, 1000, -1000)):
            matches, _ = scan_python(grid, seed, 0, grid.total, 10000, x, z)
            expected = sorted(matches, key=lambda pair: (
                (pair[0]*16-x)**2+(pair[1]*16-z)**2, *pair))[:15]
            actual, evidence = scan_nearest(grid, seed, 15, x, z)
            self.assertEqual(actual, expected)
            self.assertLessEqual(evidence['visited_regions'], grid.total)
            self.assertEqual(evidence['status'], 'proven_nearest_placement_only')

    def test_nearest_handles_search_window_starting_inside_cell_gap(self):
        from full_map import RegionGrid, scan_nearest, scan_python
        grid = RegionGrid(369, 4096, 369, 4096)
        expected, _ = scan_python(grid, 0, 0, grid.total, 10, 369, 369)
        actual, _ = scan_nearest(grid, 0, 10, 369, 369)
        self.assertEqual(sorted(actual), sorted(expected))

    def test_global_nearest_on_full_world_finishes_without_full_enumeration(self):
        from full_map import RegionGrid, scan_nearest, WORLD_EDGE
        full = RegionGrid(-WORLD_EDGE, WORLD_EDGE, -WORLD_EDGE, WORLD_EDGE)
        for center_x, center_z in ((0, 0), (WORLD_EDGE, -WORLD_EDGE)):
            hits, evidence = scan_nearest(full, 123, 7, center_x, center_z)
            self.assertEqual(len(hits), 7)
            self.assertLess(evidence['visited_regions'], full.total // 10000)
            self.assertEqual(evidence['scope'], 'placement_only_no_y')

    def test_cli_partial_reports_no_false_completion(self):
        with tempfile.TemporaryDirectory() as folder:
            out = Path(folder) / 'results.csv'
            result = subprocess.run([sys.executable, str(ROOT / 'finder.py'), 'full-map',
                                     '--version', '1.21.8', '--seed', '123',
                                     '--x-min', '-6000', '--x-max', '6000',
                                     '--z-min', '-6000', '--z-max', '6000',
                                     '--batch-regions', '10', '--max-batches', '1', '--strategy', 'exhaustive',
                                     '--cpu-rest-ms', '0', '--engine', 'python',
                                     '--out', str(out)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            status = json.loads((out.with_suffix('.state.json')).read_text())
            self.assertEqual(status['status'], 'incomplete')
            self.assertLess(status['processed_regions'], status['total_regions'])

if __name__ == '__main__':
    unittest.main()
