"""File: test_versions_gui.py
Modification: 2026-10-12 — version metadata and GUI request regression tests.
"""
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lowy_outpost_finder.gui_model import SearchRequest, build_arguments
from lowy_outpost_finder.versions import check_version, detect_world_version
import lowy_outpost_finder.cli as finder


class VersionsAndGuiTests(unittest.TestCase):
    def test_supported_versions_and_future_not_claimed(self):
        for version in ('1.21', '1.21.8', '1.21.11', '26.1', '26.1.1', '26.2', '26.3'):
            self.assertEqual(version, check_version(version))
        for version in ('1.20.6', '26.4', '26.3-snapshot-1', '1.22'):
            with self.assertRaises(ValueError):
                check_version(version)

    def test_world_name_detection_and_exact_chunk_data_version(self):
        data = {'DataVersion': 5023, 'Version': {'Name': '26.3'}}
        self.assertEqual(detect_world_version(data), ('26.3', 5023))
        with self.assertRaisesRegex(ValueError, 'selected version'):
            detect_world_version(data, '1.21.8')
        row = finder.examine({'DataVersion': 4440, 'Status': 'minecraft:full'},
                             123, 0, 0, data_version=5023)
        self.assertEqual(row['status'], 'version_mismatch')

    def test_gui_candidate_arguments(self):
        arg, env = build_arguments(SearchRequest(mode='candidates', version='26.3',
                 seed='-9223372036854775808', radius='1024', out='results.csv'))
        self.assertIn('26.3', arg)
        self.assertIn('-9223372036854775808', arg)
        self.assertEqual(env, {})

    def test_gui_live_password_stays_out_of_argv(self):
        arg, env = build_arguments(SearchRequest(mode='search-live', version='auto',
               world='/tmp/vanilla-world', password='test-very-secret', out='audit.csv'))
        self.assertNotIn('test-very-secret', str(arg))
        self.assertEqual(env['MINECRAFT_RCON_PASSWORD'], 'test-very-secret')
        self.assertEqual(arg[0], 'search-live')

    def test_gui_rejects_invalid(self):
        for req in (SearchRequest(mode='candidates', version='auto', out='x.csv'),
                    SearchRequest(mode='world', world='', out='x.csv'),
                    SearchRequest(mode='candidates', out='x.txt'),
                    SearchRequest(mode='search-live', world='/tmp/x', out='x.csv')):
            with self.assertRaises(ValueError):
                build_arguments(req)


if __name__ == '__main__':
    unittest.main()
