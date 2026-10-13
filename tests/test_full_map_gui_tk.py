"""Tk-only whole-world GUI progress tests."""
from __future__ import annotations

import unittest

try:
    import tkinter as tk
except ImportError:
    tk = None


@unittest.skipIf(tk is None, 'Tk is not installed')
class GuiProgressTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            window = tk.Tk()
            window.destroy()
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
