"""File: test_height_audit.py
Modification: 2026-10-12 — compare seed-only estimated Y with genuine saved Y.
"""
from __future__ import annotations

import csv
from pathlib import Path
import tempfile
import unittest

from height_audit import compare_heights


def write_rows(path: Path, records: list[dict]):
    with path.open('w', encoding='utf-8', newline='') as file:
        writer = csv.DictWriter(file, fieldnames=list(records[0]))
        writer.writeheader()
        writer.writerows(records)


class HeightAuditTests(unittest.TestCase):
    def test_difference_metrics_and_absent_are_not_silently_skipped(self):
        with tempfile.TemporaryDirectory() as td:
            a, b = Path(td) / 'estimate.csv', Path(td) / 'vanilla.csv'
            write_rows(a, [
                dict(version='1.21.8', seed='123', chunk_x='2', chunk_z='3', projected_surface_y='42', classification='estimated_only'),
                dict(version='1.21.8', seed='123', chunk_x='3', chunk_z='4', projected_surface_y='30', classification='estimated_only'),
                dict(version='1.21.8', seed='123', chunk_x='4', chunk_z='5', projected_surface_y='-12', classification='estimated_only'),
            ])
            write_rows(b, [
                dict(version='1.21.8', seed='123', chunk_x='2', chunk_z='3', base_plate_y='40', status='verified_tower'),
                dict(version='1.21.8', seed='123', chunk_x='3', chunk_z='4', base_plate_y='30', status='verified_tower'),
                dict(version='1.21.8', seed='123', chunk_x='4', chunk_z='5', base_plate_y='', status='absent'),
            ])
            stats = compare_heights(a,b)
            self.assertEqual(stats['matched_verified'], 2)
            self.assertEqual(stats['skipped_not_verified'], 1)
            self.assertEqual(stats['missing_estimate'], 0)
            self.assertEqual(stats['mean_absolute_error'], 1.0)
            self.assertEqual(stats['maximum_absolute_error'], 2)
            self.assertEqual(stats['exact_matches'], 1)
            self.assertFalse(stats['estimator_proven_exact'])

    def test_seed_version_mismatch_never_compared(self):
        with tempfile.TemporaryDirectory() as td:
            a,b=Path(td)/'a.csv',Path(td)/'b.csv'
            write_rows(a,[dict(version='1.21.8',seed='123',chunk_x='2',chunk_z='3',projected_surface_y='42',classification='estimated_only')])
            write_rows(b,[dict(version='26.3',seed='123',chunk_x='2',chunk_z='3',base_plate_y='42',status='verified_tower')])
            with self.assertRaisesRegex(ValueError,'version'):
                compare_heights(a,b)

    def test_duplicate_estimate_coords_are_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            a,b=Path(td)/'a.csv',Path(td)/'b.csv'
            row=dict(version='1.21.8',seed='123',chunk_x='2',chunk_z='3',projected_surface_y='42',classification='estimated_only')
            write_rows(a,[row,row]);write_rows(b,[dict(version='1.21.8',seed='123',chunk_x='2',chunk_z='3',base_plate_y='42',status='verified_tower')])
            with self.assertRaisesRegex(ValueError,'duplicate'):
                compare_heights(a,b)

    def test_no_verified_match_reports_no_accuracy(self):
        with tempfile.TemporaryDirectory() as td:
            a,b=Path(td)/'a.csv',Path(td)/'b.csv'
            write_rows(a,[dict(version='1.21.8',seed='123',chunk_x='2',chunk_z='3',projected_surface_y='42',classification='estimated_only')])
            write_rows(b,[dict(version='1.21.8',seed='123',chunk_x='2',chunk_z='3',base_plate_y='',status='not_generated')])
            stats=compare_heights(a,b)
            self.assertIsNone(stats['mean_absolute_error'])
            self.assertEqual(stats['matched_verified'],0)

if __name__=='__main__':
    unittest.main()
