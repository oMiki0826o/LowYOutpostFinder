"""File: test_benchmark.py
Modification: 2026-10-12 — enforce true measured benchmark labels.
"""
from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.benchmark import benchmark, parse_radii


class BenchmarkTests(unittest.TestCase):
    def test_parses_and_limits_radii(self):
        self.assertEqual(parse_radii('8192,16384'), [8192, 16384])
        for invalid in ('8192,-10', '', '1,2,3,4,5,6,7,8,9', 'abc'):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                parse_radii(invalid)

    def test_python_candidate_benchmark_produces_only_measured_fields(self):
        data = benchmark(123, [1024], rounds=1, native=None)
        self.assertEqual(data[0]['backend'], 'python_candidate_placement')
        self.assertIn('elapsed_seconds_median', data[0])
        self.assertGreaterEqual(data[0]['elapsed_seconds_median'], 0)
        self.assertGreaterEqual(data[0]['candidate_count'], 0)
        self.assertNotIn('verified_height', data[0])

    def test_refuses_nonexisting_native_binary(self):
        with self.assertRaises(FileNotFoundError):
            benchmark(123, [1024], rounds=1, native=Path('/does/not/exist'))


if __name__ == '__main__':
    unittest.main()
