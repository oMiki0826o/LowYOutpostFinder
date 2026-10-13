"""File: test_gui_english.py
Modification: 2026-10-12 — exercise English GUI labels and live language switching.
"""
from __future__ import annotations

import csv
import os
from pathlib import Path
import sys
import tempfile
import tkinter as tk
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


class EnglishGuiTests(unittest.TestCase):
    def setUp(self):
        try:
            from lowy_outpost_finder.gui import App
            self.app = App(language='en-US')
        except tk.TclError:
            self.skipTest('Tk requires a working window display')

    def tearDown(self):
        if getattr(self, 'app', None) is not None:
            self.app.destroy()

    def test_switching_language_keeps_seed_output_and_mode(self):
        app = self.app
        self.assertEqual(app.start_btn.cget('text'), 'Start search')
        self.assertEqual(app.browse_widgets['out'].cget('text'), 'Save as')
        app.mode.set('estimate')
        app._set_mode()
        self.assertEqual(app.vars['version'].get(), '1.21.8')
        app.vars['seed'].set('-777')
        app.vars['out'].set('/tmp/keep-results.csv')
        app.language.set('zh-TW')
        app._apply_language()
        self.assertEqual(app.vars['seed'].get(), '-777')
        self.assertEqual(app.vars['out'].get(), '/tmp/keep-results.csv')
        self.assertEqual(app.mode.get(), 'estimate')
        self.assertEqual(app.start_btn.cget('text'), '開始搜尋')
        app.language.set('en-US')
        app._apply_language()
        self.assertEqual(app.start_btn.cget('text'), 'Start search')

    def test_collapsible_form_preserves_inputs_and_shows_results(self):
        app = self.app
        app.vars['seed'].set('34567')
        self.assertTrue(app.form_visible)
        app._toggle_form(visible=False)
        app.update_idletasks()
        self.assertFalse(app.form_container.winfo_ismapped())
        self.assertEqual(app.vars['seed'].get(), '34567')
        self.assertEqual(app.toggle_form_btn.cget('text'), 'Show search settings')
        app.language.set('zh-TW')
        app._apply_language()
        self.assertIn('展開', app.toggle_form_btn.cget('text'))
        app._toggle_form(visible=True)
        app.update_idletasks()
        self.assertTrue(app.form_canvas.winfo_ismapped())

    def test_english_csv_preview_columns(self):
        app = self.app
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / 'estimate.csv'
            with path.open('w', encoding='utf-8', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(('seed', 'projected_surface_y', 'classification'))
                writer.writerow(('123', '-30', 'estimated_only'))
            self.assertEqual(app._preview(path), (1, 1))
            self.assertEqual(app.grid.heading('projected_surface_y')['text'], 'Estimated surface Y')
            self.assertEqual(app.grid.item(app.grid.get_children()[0])['values'][2], 'estimated_only')

    def test_english_modes_fit_minimum_window_width(self):
        app = self.app
        app.geometry('810x720')
        app.update()
        outer_right = app.winfo_rootx() + app.winfo_width()
        for widget in app.mode_widgets.values():
            self.assertGreater(widget.winfo_width(), 50)
            self.assertLessEqual(widget.winfo_rootx() + widget.winfo_width(), outer_right - 8)

    def test_seed_vanilla_form_is_scrollable_and_results_remain_visible(self):
        app = self.app
        app.mode.set('seed-vanilla')
        app._set_mode()
        app.geometry('810x570')
        app.update()
        # Search controls and results must both be accessible at minimum window size.
        self.assertLess(app.start_btn.winfo_rooty() + app.start_btn.winfo_height(),
                        app.winfo_rooty() + app.winfo_height())
        self.assertGreater(app.preview_label.winfo_width(), 0)
        self.assertGreater(app.preview_label.winfo_rooty(), app.winfo_rooty())
        self.assertTrue(app.form_canvas.winfo_ismapped())
        app.vars['eula_accepted'].set(True)
        app.language.set('zh-TW')
        app._apply_language()
        self.assertTrue(app.vars['eula_accepted'].get())
        self.assertIn('種子原版', app.mode_widgets['seed-vanilla'].cget('text'))

    def test_seed_vanilla_priority_setting_survives_language_switch(self):
        app = self.app
        app.mode.set('seed-vanilla')
        app._set_mode()
        self.assertTrue(app.groups['priority'].winfo_manager())
        app.vars['priority'].set('terrain')
        app.language.set('zh-TW')
        app._apply_language()
        self.assertEqual(app.vars['priority'].get(), 'terrain')
        self.assertIn('驗證順序', app.field_widgets['priority'].cget('text'))
        app.mode.set('candidates')
        app._set_mode()
        self.assertFalse(app.groups['priority'].winfo_manager())

    def test_english_candidate_mode_cli_payload(self):
        from lowy_outpost_finder.gui_model import SearchRequest, build_arguments
        app = self.app
        req = SearchRequest(mode='candidates', version='1.21.8', seed='22',
                            radius='1024', out='somewhere.csv')
        args, env = build_arguments(req, language=app.language.get())
        self.assertEqual(env, {})
        self.assertIn('candidates', args)
        self.assertIn('22', args)


if __name__ == '__main__':
    unittest.main()
