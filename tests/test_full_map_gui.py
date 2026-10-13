"""File: test_full_map_gui.py
Modification: 2026-10-13 — no-Java whole-world GUI invocation and progress reporting.
"""
from __future__ import annotations

import unittest

from lowy_outpost_finder.gui_model import SearchRequest, build_arguments


class GuiModelFullMapTests(unittest.TestCase):
    def test_full_world_nearest_needs_no_server_or_eula_and_limits_results(self):
        req = SearchRequest(mode='full-map', version='1.21.8', seed='-3',
                            out='all.csv', top='99', center_x='-100', center_z='200',
                            scan_strategy='nearest', scan_engine='python',
                            batch_regions='10000', cpu_rest_ms='200')
        args, secret = build_arguments(req)
        self.assertEqual(secret, {})
        self.assertIn('full-map', args)
        self.assertIn('--top', args)
        self.assertIn('--strategy', args)
        self.assertIn('nearest', args)
        self.assertNotIn('--server-jar', args)
        self.assertNotIn('--radius', args)

    def test_resume_only_for_exhaustive_and_cpu_range_checked(self):
        req = SearchRequest(mode='full-map', out='a.csv', resume=True,
                            scan_strategy='nearest')
        with self.assertRaises(ValueError):
            build_arguments(req)
        req = SearchRequest(mode='full-map', out='a.csv', resume=True,
                            scan_strategy='exhaustive', cpu_rest_ms='100')
        args, _ = build_arguments(req)
        self.assertIn('--resume', args)
        with self.assertRaises(ValueError):
            build_arguments(SearchRequest(mode='full-map', out='a.csv', cpu_rest_ms='-1'))

if __name__ == '__main__':
    unittest.main()
