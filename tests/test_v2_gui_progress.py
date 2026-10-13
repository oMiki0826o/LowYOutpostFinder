"""File: test_v2_gui_progress.py
Modification: 2026-10-13 — GUI must report real verified-candidate progress.
"""
from __future__ import annotations
import unittest
try: import tkinter as tk
except ImportError: tk=None

@unittest.skipIf(tk is None,'Tk not available')
class GuiProgressTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            t=tk.Tk();t.withdraw();t.destroy()
        except tk.TclError:
            raise unittest.SkipTest('No graphical display')

    def test_live_log_updates_progress_without_counting_unverified_y_as_success(self):
        from gui import App
        app=App(language='zh-TW')
        try:
            app._update_progress_from_log('[2/10] 32,41 : absent')
            self.assertEqual(str(app.progress.cget('mode')),'determinate')
            self.assertEqual(float(app.progress['value']),2.0)
            self.assertEqual(float(app.progress['maximum']),10.0)
            self.assertIn('2',app.banner.get())
            self.assertNotIn('verified_tower',app.banner.get())
        finally:app.destroy()

if __name__=='__main__':unittest.main()
