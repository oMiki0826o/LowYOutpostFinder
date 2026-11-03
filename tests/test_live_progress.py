"""Live native progress, user-visible percentage and portable bootstrap regression tests."""
from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path
import unittest

from lowy_outpost_finder.simple_gui import format_search_progress
from lowy_outpost_finder.estimated_full_map import _run_native_with_progress


class SearchProgressTests(unittest.TestCase):
    def test_percent_uses_found_count_not_scanned_area(self):
        message, progress = format_search_progress(4096, 2, 25, 12.9)
        self.assertEqual(progress, 8.0)
        self.assertIn('4,096', message)
        self.assertIn('2/25', message)
        self.assertIn('12 秒', message)

    def test_before_first_match_reports_work_without_fictitious_percentage(self):
        message, progress = format_search_progress(250000, 0, 25, 20)
        self.assertEqual(progress, 0.0)
        self.assertIn('250,000', message)
        self.assertIn('0/25', message)

    def test_completed_and_exhausted_counts(self):
        self.assertEqual(format_search_progress(5, 25, 25, 0)[1], 100.0)
        self.assertEqual(format_search_progress(5, 4, 25, 0)[1], 16.0)
        self.assertEqual(format_search_progress(5, 999, 25, 0)[1], 100.0)

    def test_english_progress(self):
        message, progress = format_search_progress(1024, 1, 10, 3, 'en-US')
        self.assertEqual(progress, 10.0)
        self.assertIn('generation regions', message)

    def test_live_stderr_telemetry_does_not_corrupt_json_stdout(self):
        script = (
            "import sys\n"
            "print('LOWY_NATIVE_PROGRESS 0 0 0 0', file=sys.stderr, flush=True)\n"
            "print('LOWY_NATIVE_PROGRESS 32 3 2 2', file=sys.stderr, flush=True)\n"
            "print('{\"rows\":[],\"matches\":2}', flush=True)\n"
        )
        received = []
        result = _run_native_with_progress(
            [sys.executable, '-c', script],
            lambda regions, ring, found, accepted:
                received.append((regions, ring, found, accepted)),
        )
        self.assertEqual(result.returncode, 0)
        self.assertEqual(received, [(0, 0, 0, 0), (32, 3, 2, 2)])
        self.assertIn('"rows":[]', result.stdout)

    def test_malformed_telemetry_is_ignored(self):
        script = (
            "import sys\n"
            "print('LOWY_NATIVE_PROGRESS bad payload', file=sys.stderr, flush=True)\n"
            "print('LOWY_NATIVE_PROGRESS 3 2 5 1', file=sys.stderr, flush=True)\n"
            "print('ok', flush=True)\n"
        )
        received = []
        result = _run_native_with_progress(
            [sys.executable, '-c', script], lambda *nums: received.append(nums))
        self.assertEqual(received, [])
        self.assertEqual(result.stdout.strip(), 'ok')


class PortableCarverPatchTests(unittest.TestCase):
    def test_pinned_constant_check_preserves_semantics(self):
        from scripts.build_native import _fix_upstream_carver
        original = (
            "#define MC_SIN_SCALE 0x1.45f306dc9c883p13\n"
            "_Static_assert(MC_SIN_SCALE == 10430.378350470453,\n"
            '               "MC_SIN_SCALE must be the exact double 10430.378350470453d");\n'
        )
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / 'carver.c'
            source.write_text(original, encoding='utf-8')
            _fix_upstream_carver(Path(folder))
            updated = source.read_text(encoding='utf-8')
            self.assertIn('#define MC_SIN_SCALE', updated)
            self.assertNotIn('_Static_assert', updated)

    def test_changed_upstream_constant_fails_closed(self):
        from scripts.build_native import _fix_upstream_carver
        with tempfile.TemporaryDirectory() as folder:
            (Path(folder) / 'carver.c').write_text(
                '#define MC_SIN_SCALE 42.0\n'
                '_Static_assert(MC_SIN_SCALE == 42.0, "changed");\n',
                encoding='utf-8')
            with self.assertRaisesRegex(RuntimeError, 'upstream'):
                _fix_upstream_carver(Path(folder))



if __name__ == '__main__':
    unittest.main()
