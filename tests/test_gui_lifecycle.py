"""File: test_gui_lifecycle.py
Modification: 2026-10-12 — Tkinter event/lifecycle smoke tests.
"""
from __future__ import annotations

from pathlib import Path
import sys
import unittest
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

try:
    import tkinter as tk
except ImportError:
    tk = None


@unittest.skipIf(tk is None, 'Tk is not installed')
class TkLifecycleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            root = tk.Tk()
            root.withdraw()
            root.destroy()
        except tk.TclError:
            raise unittest.SkipTest('No usable desktop display')

    def test_close_with_active_worker_marks_cancel_before_teardown(self):
        from gui import App
        app = App()
        try:
            class Busy:
                def is_alive(self):
                    return True
            app.worker = Busy()
            with patch('gui.messagebox.askyesno', return_value=True):
                app._on_close()
            self.assertTrue(app.cancel_requested.is_set())
        finally:
            app.worker = None
            app.destroy()

    def test_build_and_mode_switch(self):
        from gui import App
        app = App()
        try:
            self.assertIn('candidates', [key for key, _ in app.mode_choices])
            for mode in ('world', 'verify', 'search-live', 'candidates'):
                app.mode.set(mode)
                app._set_mode()
                self.assertTrue(app.vars['out'].get().endswith('.csv'))
        finally:
            app.destroy()
