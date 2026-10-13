"""File: test_explorer_gui.py
Modification: 2026-10-13 — GUI smoke / language / threaded search regression.
"""
from __future__ import annotations

import time
import tkinter as tk
import unittest

from explorer_gui import AdvancedWindow, LABELS
from gui import App


class ExplorerGuiTests(unittest.TestCase):
    def setUp(self):
        try:
            self.app = App('zh-TW')
        except tk.TclError:
            self.skipTest('Tk display unavailable; run with xvfb-run on Linux')
        self.addCleanup(self.app.destroy)

    def test_bilingual_labels_and_main_entry(self):
        self.assertEqual(set(LABELS['zh-TW']), set(LABELS['en-US']))
        self.app._advanced()
        win = next(x for x in self.app.winfo_children() if isinstance(x, AdvancedWindow))
        self.app.language.set('en-US')
        self.app._apply_language()
        self.assertEqual(win.language, 'en-US')
        self.assertIn('Advanced', win.title())
        self.assertEqual(win.tab_buttons['batch'].cget('text'), 'Seed list')
        win.destroy()

    def test_can_scan_seed_without_freezing_window(self):
        win = AdvancedWindow(self.app, language='zh-TW')
        win.values['seed'].set('123')
        win._start()
        self.assertIsNotNone(win.worker)
        for _ in range(200):
            self.app.update()
            if win.rows:
                break
            time.sleep(.01)
        self.assertGreater(len(win.rows), 20)
        self.assertTrue(all(row['classification'] == 'placement_candidate' for row in win.rows))
        self.assertFalse(any(row['projected_surface_y'] for row in win.rows))
        win.destroy()


if __name__ == '__main__':
    unittest.main()
