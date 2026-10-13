"""File: test_native_projection.py
Modification: 2026-10-13 — compare native Jigsaw sample coordinates to an independent Java model.
"""
from pathlib import Path
import csv
import io
import subprocess
import unittest
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from start_geometry import projection


class NativeProjectionTests(unittest.TestCase):
    def test_native_matches_java_rotation_and_sample(self):
        exe = Path(__file__).resolve().parents[1] / 'bin' / 'lowyoutpost'
        if not exe.is_file():
            self.skipTest('Build optional C backend before cross-language testing')
        for seed in (0, 123, -1, -(1 << 63), (1 << 63) - 1):
            process = subprocess.run([str(exe), '--seed', str(seed), '--radius', '4096',
                                      '--max-y', '320', '--top', '150', '--skip-biome',
                                      '--template-width', '13', '--template-depth', '17'],
                                     capture_output=True, text=True, check=True)
            rows = list(csv.DictReader(io.StringIO(process.stdout)))
            self.assertGreater(len(rows), 0)
            for row in rows:
                pos = projection(seed, int(row['chunk_x']), int(row['chunk_z']), (13, 1, 17))
                self.assertEqual((int(row['sample_x']), int(row['sample_z']), int(row['rotation'])),
                                 (pos.sample_x, pos.sample_z, pos.rotation))
                self.assertEqual(int(row['projected_base_plate_y']), int(row['projected_surface_y']) - 1)

if __name__ == '__main__':
    unittest.main()
