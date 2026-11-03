"""Tk lifecycle smoke tests for the minimalist low-Y home."""
from __future__ import annotations

import tkinter as tk
import unittest

from lowy_outpost_finder.simple_gui import SimpleApp, PUBLIC_FIELDS
from lowy_outpost_finder.gui import App as LegacyApp


class SimpleHomeTkTests(unittest.TestCase):
    def setUp(self):
        try:
            self.app = SimpleApp(auto_prepare=False)
            self.app.update_idletasks()
        except tk.TclError:
            self.skipTest('No graphical Tk display')

    def tearDown(self):
        if hasattr(self, 'app'):
            try:
                self.app._on_close()
            except tk.TclError:
                pass

    def test_black_white_default_values_and_result_columns(self):
        app = self.app
        self.assertEqual(app.theme_mode, 'dark')
        self.assertEqual(app.cget('background'), '#000000')
        self.assertEqual(app.vars['version'].get(), '1.21.8')
        self.assertEqual(app.vars['max_y'].get(), '-37')
        self.assertEqual(app.vars['radius'].get(), '30000000')
        self.assertEqual(app.vars['top'].get(), '25')
        self.assertEqual(tuple(app.tree['columns']), PUBLIC_FIELDS)
        self.assertEqual(str(app.search_btn.cget('state')), 'disabled')

    def test_settings_and_language_toggle_do_not_change_user_seed(self):
        app = self.app
        app.vars['seed'].set('-12345')
        app._open_settings()
        app._toggle_language()
        self.assertEqual(app.vars['seed'].get(), '-12345')
        self.assertEqual(app.language, 'en-US')
        self.assertEqual(app.vars['max_y'].get(), '-37')
        app._toggle_theme()
        self.assertEqual(app.cget('background'), '#ffffff')

    def test_window_destroy_removes_poll_timer_without_error(self):
        app = self.app
        poll = app._poll_id
        self.assertIn(poll, app.tk.call('after', 'info'))
        app._on_close()
        self.assertTrue(app._closing)
        self.assertIsNone(app._poll_id)
        del self.app

    def test_legacy_window_cancelled_resize_does_not_access_destroyed_form(self):
        advanced = LegacyApp()
        try:
            self.assertEqual(advanced.cget('background'), '#000000')
            advanced._schedule_form_resize()
            self.assertIsNotNone(advanced._layout_after)
            advanced.destroy()
            self.assertIsNone(advanced._layout_after)
            advanced._resize_form_viewport()
        finally:
            if not advanced._closing:
                advanced.destroy()


if __name__ == '__main__':
    unittest.main()
