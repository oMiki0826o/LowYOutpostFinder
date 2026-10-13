"""File: test_search_conditions.py
Modification: 2026-10-13 — acceptance predicate and honest nearest-result evidence.
"""
import unittest
from lowy_outpost_finder.search_conditions import accepted_tower, summarize_search


class SearchConditionsTests(unittest.TestCase):
    def row(self, center=-40, base=-31, status='verified_tower'):
        return {'status': status, 'structure_center_y': center, 'base_plate_y': base,
                'chunk_x': 0, 'chunk_z': 0}

    def test_both_thresholds_must_be_satisfied_before_stopping(self):
        self.assertFalse(accepted_tower(self.row(base=4), center_below=-37, max_y=0))
        self.assertFalse(accepted_tower(self.row(center=-37), center_below=-37, max_y=0))
        self.assertTrue(accepted_tower(self.row(), center_below=-37, max_y=0))

    def test_rejects_incomplete_or_unexpected_height_values(self):
        self.assertFalse(accepted_tower(self.row(status='absent'), center_below=-37, max_y=0))
        self.assertFalse(accepted_tower(self.row(center='nan'), center_below=-37, max_y=0))
        self.assertFalse(accepted_tower(self.row(center=''), center_below=-37, max_y=0))

    def test_nearest_is_unproven_when_earlier_candidate_timed_out(self):
        rows = [self.row(status='timeout'), self.row()]
        report = summarize_search(rows, center_below=-37, max_y=0, total_candidates=3, priority='near-origin')
        self.assertEqual(report['nearest_status'], 'not_proven')
        self.assertEqual(report['unresolved_before_first_hit'], 1)

    def test_missing_earlier_verified_height_is_not_conclusive(self):
        rows = [self.row(center=''), self.row()]
        report = summarize_search(rows, center_below=-37, max_y=0, total_candidates=2)
        self.assertEqual(report['nearest_status'], 'not_proven')

    def test_nearest_is_proven_only_with_full_coverage(self):
        rows = [self.row(status='absent'), self.row()]
        report = summarize_search(rows, center_below=-37, max_y=0, total_candidates=2, priority='near-origin')
        self.assertEqual(report['nearest_status'], 'nearest_proven_within_radius')
        self.assertEqual(report['confirmed_hits'], 1)

    def test_terrain_priority_cannot_claim_nearest(self):
        rows = [self.row()]
        report = summarize_search(rows, center_below=-37, max_y=0, total_candidates=1, priority='terrain')
        self.assertEqual(report['nearest_status'], 'not_proven')
