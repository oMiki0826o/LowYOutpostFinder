"""File: test_version_2612.py
Modification: 2026-10-13 — regression for official Java 26.1.2 hotfix version.
"""
import unittest
from versions import SUPPORTED, check_version


class Version2612Tests(unittest.TestCase):
    def test_java_2612_is_available_for_placement_scans(self):
        self.assertIn('26.1.2', SUPPORTED)
        self.assertEqual(check_version('26.1.2'), '26.1.2')


if __name__ == '__main__':
    unittest.main()
