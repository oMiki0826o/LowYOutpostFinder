"""File: test_bilingual.py
Modification: 2026-10-12 — bilingual GUI and seed-only ranking contract tests.
"""
from __future__ import annotations

from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from gui_model import SearchRequest, build_arguments


class TranslationTests(unittest.TestCase):
    def test_catalogue_covers_gui_components_in_both_languages(self):
        from i18n import CATALOGS, tr
        self.assertEqual(set(CATALOGS), {'zh-TW', 'en-US'})
        self.assertEqual(set(CATALOGS['zh-TW']), set(CATALOGS['en-US']))
        for key, text in CATALOGS['en-US'].items():
            self.assertTrue(text.strip(), key)
            self.assertNotEqual(tr('en-US', 'start'), tr('zh-TW', 'start'))
        self.assertEqual(tr('en-US', 'mode_estimate'), '02  Terrain estimate (experimental)')
        with self.assertRaises(ValueError):
            tr('fr-FR', 'start')

    def test_english_gui_argument_errors(self):
        with self.assertRaisesRegex(ValueError, 'numeric world seed'):
            build_arguments(SearchRequest(mode='candidates', seed='abc', out='x.csv'), language='en-US')
        with self.assertRaisesRegex(ValueError, 'Choose a world folder'):
            build_arguments(SearchRequest(mode='world', world='', out='x.csv'), language='en-US')

    def test_estimate_cli_arguments_and_guards(self):
        args, env = build_arguments(SearchRequest(
            mode='estimate', version='1.21.8', seed='-5', radius='1024',
            max_y='-32', top='17', core_archive='/tmp/core.tar.gz',
            out='r.csv'), language='en-US')
        self.assertEqual(env, {})
        self.assertIn('--top', args)
        self.assertIn('17', args)
        self.assertIn('--core-archive', args)
        self.assertIn('/tmp/core.tar.gz', args)
        with self.assertRaisesRegex(ValueError, '1.21.8'):
            build_arguments(SearchRequest(
                mode='estimate', version='26.3', out='r.csv'), language='en-US')

    def test_english_help_and_gui_translator_without_display(self):
        from i18n import tr
        self.assertIn('English', tr('en-US', 'language_caption'))
        self.assertIn('approximate', tr('en-US', 'tip_estimate').lower())
        self.assertIn('not', tr('en-US', 'banner_ready').lower())


if __name__ == '__main__':
    unittest.main()
