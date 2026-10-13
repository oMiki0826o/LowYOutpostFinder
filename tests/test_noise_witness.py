"""File: test_noise_witness.py
Modification: 2026-10-13 — test-first acceptance of measured vanilla sample heights.
"""
from __future__ import annotations

import csv
import tempfile
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from noise_witness import build_witnesses, compare_witnesses, read_witnesses


class WitnessTests(unittest.TestCase):
    def _observed(self, **kwargs):
        result = dict(seed=123, version='1.21.8', chunk_x=-10, chunk_z=22,
                      sample_x=-151, sample_z=365, status='verified_tower',
                      geometry_status='match', tower_vertical_status='match',
                      base_plate_y=-30, watchtower_min_y=-30, watchtower_max_y=-10,
                      expected_rotation='none')
        result.update(kwargs)
        return result

    def test_only_reconciled_vanilla_towers_produce_height_samples(self):
        records = [self._observed(), self._observed(chunk_x=8, sample_x=130, geometry_status='rotation_mismatch'),
                   self._observed(chunk_x=9, sample_x=150, tower_vertical_status='missing'),
                   self._observed(chunk_x=11, sample_x=175, status='not_full')]
        witnessed, summary = build_witnesses(records, '1.21.8', 123, 'abc')
        self.assertEqual(len(witnessed), 1)
        self.assertEqual(witnessed[0]['world_surface_wg'], -29)
        self.assertEqual(witnessed[0]['evidence'], 'derived_from_vanilla_saved_jigsaw')
        self.assertEqual(summary['status'], 'sample_observations_only')
        self.assertEqual(summary['excluded'], 3)
        self.assertFalse(summary['global_exactness_proven'])

    def test_duplicate_or_bad_height_fails_closed(self):
        row = self._observed()
        with self.assertRaisesRegex(ValueError, 'Duplicate'):
            build_witnesses([row, row], '1.21.8', 123, 'abc')
        with self.assertRaisesRegex(ValueError, 'Height'):
            build_witnesses([self._observed(base_plate_y='no')], '1.21.8', 123, 'abc')
        with self.assertRaisesRegex(ValueError, 'Height'):
            build_witnesses([self._observed(base_plate_y=-25.5)], '1.21.8', 123, 'abc')
        with self.assertRaisesRegex(ValueError, 'seed'):
            build_witnesses([self._observed(seed=456)], '1.21.8', 123, 'abc')

    def test_difference_reports_nonzero_error_and_no_fabricated_matches(self):
        observed, _ = build_witnesses([self._observed()], '1.21.8', 123, 'abc')
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            observed_file = root / 'witness.csv'
            with observed_file.open('w', encoding='utf-8', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=list(observed[0]))
                writer.writeheader()
                writer.writerows(observed)
            loaded = read_witnesses(observed_file)
            self.assertEqual(loaded[0]['sample_x'], -151)
            estimated_file = root / 'estimate.csv'
            estimated_file.write_text('version,seed,chunk_x,chunk_z,sample_x,sample_z,rotation,projected_base_plate_y,classification\n'
                                      '1.21.8,123,-10,22,-151,365,0,-27,estimated_only\n')
            result, summary = compare_witnesses(loaded, estimated_file)
            self.assertEqual(result[0]['base_plate_error'], 3)
            self.assertEqual(summary['compared'], 1)
            self.assertEqual(summary['maximum_absolute_error'], 3)
            self.assertFalse(summary['global_exactness_proven'])

    def test_mismatched_sample_coordinate_never_used(self):
        observed, _ = build_witnesses([self._observed()], '1.21.8', 123, 'abc')
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'estimated.csv'
            path.write_text('version,seed,chunk_x,chunk_z,sample_x,sample_z,rotation,projected_base_plate_y,classification\n'
                            '1.21.8,123,-10,22,-150,365,0,-30,estimated_only\n')
            with self.assertRaisesRegex(ValueError, 'sample'):
                compare_witnesses(observed, path)

    def test_empty_samples_remain_inconclusive(self):
        observations, summary = build_witnesses([self._observed(status='not_full')], '1.21.8', 123, 'abc')
        self.assertEqual(observations, [])
        self.assertEqual(summary['status'], 'no_verified_observations')

if __name__ == '__main__':
    unittest.main()
