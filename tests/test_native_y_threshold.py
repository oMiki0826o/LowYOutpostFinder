"""File: test_native_y_threshold.py
Modification: 2026-10-13 — --max-y on projected Jigsaw base must use base Y, not surface Y.
"""
from pathlib import Path
import csv
import io
import subprocess
import unittest


class NativeYThresholdTests(unittest.TestCase):
    def test_max_y_on_baseplate_respects_ground_level_delta(self):
        binary = Path(__file__).resolve().parents[1] / 'bin' / 'lowyoutpost'
        if not binary.is_file():
            self.skipTest('Optional C backend not built')
        opts = [str(binary), '--seed', '123', '--radius', '4096', '--top', '150',
                '--skip-biome', '--template-width', '13', '--template-depth', '17']
        initial = subprocess.run(opts + ['--max-y', '320'], capture_output=True, text=True, check=True)
        rows = list(csv.DictReader(io.StringIO(initial.stdout)))
        self.assertTrue(rows)
        best = min(int(row['projected_base_plate_y']) for row in rows)
        limited = subprocess.run(opts + ['--max-y', str(best)], capture_output=True, text=True, check=True)
        filtered = list(csv.DictReader(io.StringIO(limited.stdout)))
        self.assertTrue(filtered, 'The lowest baseplate should be included even if surface Y is one higher')
        self.assertTrue(all(int(row['projected_base_plate_y']) <= best for row in filtered))

if __name__ == '__main__':
    unittest.main()
