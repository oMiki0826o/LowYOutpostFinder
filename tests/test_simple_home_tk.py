"""Tk lifecycle smoke tests for the minimalist low-Y home."""
from __future__ import annotations

import tkinter as tk
import unittest
from unittest.mock import patch

from lowy_outpost_finder.simple_gui import SimpleApp, PUBLIC_FIELDS, is_classic_entry
from lowy_outpost_finder.gui import App as LegacyApp


class SimpleHomeTkTests(unittest.TestCase):
    def setUp(self):
        try:
            self.app = SimpleApp(auto_prepare=False)
            self.app.update_idletasks()
        except tk.TclError as exc:
            # Never disguise a real UI startup regression (e.g. unknown -bg
            # on macOS ttk.Combobox) as missing DISPLAY.
            reason = str(exc).lower()
            if ('no display name' in reason or "couldn't connect to display" in reason
                    or 'could not connect to display' in reason):
                self.skipTest('No graphical Tk display')
            raise

    def tearDown(self):
        if hasattr(self, 'app'):
            try:
                self.app._on_close()
            except tk.TclError:
                pass

    def test_ttk_combobox_is_not_styled_as_classic_tk_entry(self):
        """ttk.Combobox inherits tk.Entry but rejects classic -bg/-fg options."""
        import tkinter.ttk as ttk
        self.assertTrue(issubclass(ttk.Combobox, tk.Entry))
        app = self.app
        self.assertIsInstance(app.version_field, ttk.Combobox)
        self.assertFalse(is_classic_entry(app.version_field))
        self.assertTrue(is_classic_entry(app.seed_field))
        # Both initial theming and toggling must remain safe on real Tk.
        app._apply_theme()
        app._toggle_theme()
        app._toggle_theme()
        self.assertEqual(app.theme_mode, 'dark')

    def test_buttons_have_contrast_in_normal_disabled_and_active_states(self):
        from tkinter import ttk
        app = self.app
        style = ttk.Style(app)
        controls = {
            app.settings_btn: 'MonoIcon.TButton',
            app.advanced_link: 'MonoLink.TButton',
            app.search_btn: 'MonoPrimary.TButton',
            app.stop_btn: 'MonoSecondary.TButton',
            app.export_btn: 'MonoSecondary.TButton',
        }
        for mode in ('dark', 'light'):
            app.theme_mode = mode
            app._apply_theme()
            self.assertEqual(style.theme_use(), 'clam')
            for widget, name in controls.items():
                with self.subTest(mode=mode, widget=name):
                    self.assertIsInstance(widget, ttk.Button)
                    self.assertEqual(widget.cget('style'), name)
                    for state in ((), ('active',), ('pressed',), ('disabled',)):
                        foreground = style.lookup(name, 'foreground', state)
                        background = style.lookup(name, 'background', state)
                        self.assertTrue(foreground and background)
                        self.assertNotEqual(foreground.lower(), background.lower())
        app.theme_mode = 'dark'
        app._apply_theme()

    def test_settings_dialog_controls_are_legible_themed_buttons(self):
        from tkinter import ttk
        app = self.app
        app._open_settings()
        dialog = app._open_windows[-1]
        frame = next(child for child in dialog.winfo_children()
                     if isinstance(child, tk.Frame))
        buttons = [widget for widget in frame.winfo_children()
                   if isinstance(widget, ttk.Button)]
        self.assertGreaterEqual(len(buttons), 8)
        self.assertFalse(any(isinstance(w, tk.Button) for w in frame.winfo_children()))
        for widget in buttons:
            self.assertEqual(widget.cget('style'), 'MonoSecondary.TButton')

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

    def test_retry_native_setup_clears_prior_cancellation(self):
        app = self.app
        app.cancel_event.set()
        with patch('lowy_outpost_finder.simple_gui.threading.Thread') as worker:
            app._prepare_backend()
        self.assertFalse(app.cancel_event.is_set())
        worker.assert_called_once()

    def test_missing_toolchain_message_has_chinese_guidance(self):
        app = self.app
        message = app._explain_bootstrap_error('Missing cmake. Please install it.')
        self.assertIn('編譯', message)
        self.assertIn('CMake', message)
        self.assertIn('macOS', message)

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
