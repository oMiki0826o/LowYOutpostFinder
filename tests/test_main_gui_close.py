"""File: test_main_gui_close.py
Modification: 2026-10-13 — GUI root must release scheduled Tk callbacks on close.
"""
import tkinter as tk
import unittest
from lowy_outpost_finder.gui import App


class MainGuiCloseTests(unittest.TestCase):
    def test_root_removes_poll_callback_on_destroy(self):
        try:
            app = App('en-US')
        except tk.TclError:
            self.skipTest('No Tk display')
        timer = app._poll_id
        self.assertIn(timer, app.tk.call('after', 'info'))
        app.destroy()
        self.assertNotIn(timer, app.tk.call('after', 'info'))


if __name__ == '__main__':
    unittest.main()
