"""File: test_full_map_gui.py
Modification: 2026-10-13 — no-Java whole-world GUI invocation and progress reporting.
"""
from __future__ import annotations

from pathlib import Path
import sys
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

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


try:
    import tkinter as tk
except ImportError:
    tk = None


@unittest.skipIf(tk is None, 'Tk is not installed')
class GuiProgressTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            w = tk.Tk()
            w.destroy()
        except tk.TclError:
            raise unittest.SkipTest('No usable Tk display')

    def test_bilingual_fullmap_mode_and_progress(self):
        from lowy_outpost_finder.gui import App
        app = App()
        try:
            self.assertIn('full-map', [key for key, _ in app.mode_choices])
            app.mode.set('full-map')
            app._set_mode()
            self.assertIn('scan_strategy', app.groups)
            app._update_progress_from_log('FULLMAP_PROGRESS 50 100 8 incomplete\n')
            self.assertEqual(int(app.progress['value']), 50)
            app.language.set('en-US')
            app._apply_language()
            self.assertTrue(app.mode_widgets['full-map'].cget('text'))
        finally:
            app.destroy()

if __name__ == '__main__':
    unittest.main()
