"""Regression tests for integrated nearest candidate GUI and bounded C estimate searches."""
from __future__ import annotations

import tempfile
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

from lowy_outpost_finder.cli import candidates, nearest_candidates
from lowy_outpost_finder.gui_model import SearchRequest, build_arguments
from lowy_outpost_finder.estimated_full_map import EstimatedScanConfig, scan_estimated_nearest


class NearestCandidateIntegrationTests(TestCase):
    def test_nearest_matches_enumerated_small_area(self):
        for seed in (0, 123, -5):
            original = list(candidates(seed, 4096))
            expected = sorted(original, key=lambda row:
                              (row['x']**2 + row['z']**2,
                               row['chunk_x'], row['chunk_z']))[:9]
            result = list(nearest_candidates(seed, 4096, 9))
            self.assertEqual(
                [(row['chunk_x'], row['chunk_z']) for row in result],
                [(row['chunk_x'], row['chunk_z']) for row in expected])

    def test_gui_nearest_translates_into_cli_arguments(self):
        args, secrets = build_arguments(SearchRequest(
            mode='candidates', out='near.csv', seed='123',
            radius='30000000', nearest_only=True, top='11'))
        self.assertEqual(secrets, {})
        self.assertEqual(args[args.index('--nearest') + 1], '11')
        self.assertEqual(args[args.index('--radius') + 1], '30000000')

    def test_full_map_estimate_uses_correct_version_and_resume(self):
        args, _ = build_arguments(SearchRequest(
            mode='full-map', out='est.csv', version='1.21.8',
            height_engine='estimate', scan_strategy='nearest', max_y='-37',
            resume=True))
        self.assertIn('--resume', args)
        with self.assertRaisesRegex(ValueError, '1.21.8'):
            build_arguments(SearchRequest(
                mode='full-map', out='est.csv', version='26.3',
                height_engine='estimate', max_y='-37'))
        with self.assertRaisesRegex(ValueError, 'Resume'):
            build_arguments(SearchRequest(
                mode='full-map', out='place.csv', resume=True,
                height_engine='placement', scan_strategy='nearest'))

    def test_estimated_nearest_terminates_at_world_edge_when_no_matches(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            binary = root / 'mock-scanner'
            binary.write_text('fixture', encoding='utf-8')
            cfg = EstimatedScanConfig(
                version='1.21.8', seed=123, x_min=-512, x_max=512,
                z_min=-512, z_max=512, center_x=0, center_z=0,
                max_y=-37, top=3, batch_regions=1,
                sleep_ms=0, engine='native')
            seen = []

            def fake_native(grid, config, start, count, wanted, binary_path):
                seen.append((start, count))
                return [], 0, 0, 0, start + count, False, 'test-model'

            with patch('lowy_outpost_finder.estimated_full_map.scan_native_strict_nearest',
                       side_effect=fake_native):
                state = scan_estimated_nearest(cfg, root / 'out.csv',
                                               binary=binary)
            self.assertEqual(state['status'], 'exhausted_estimated_only')
            self.assertTrue(seen)
            self.assertLessEqual(len(seen), 10)
            self.assertEqual(len(state['retained']), 0)
            self.assertGreater(state['processed_rings'], 0)


try:
    import tkinter as tk
except ImportError:
    tk = None


class TkVisualIntegrationTests(TestCase):
    def setUp(self):
        if tk is None:
            self.skipTest('Tkinter unavailable')
        try:
            from lowy_outpost_finder.gui import App
            self.app = App(language='zh-TW')
        except tk.TclError:
            self.skipTest('No graphical display')

    def tearDown(self):
        if hasattr(self, 'app'):
            self.app.destroy()

    def test_default_dark_theme_and_light_switch(self):
        app = self.app
        self.assertEqual(app.theme_mode.get(), 'dark')
        self.assertEqual(app.mode_widgets['candidates'].grid_info()['row'], 0)
        self.assertEqual(app.mode_widgets['full-map'].grid_info()['row'], 0)
        app.theme_display.set(app.t('theme_light'))
        app._change_theme()
        self.assertEqual(app.theme_mode.get(), 'light')

    def test_mode_updates_y_guidance_and_nearest_checkbox(self):
        app = self.app
        self.assertTrue(app.vars['nearest_only'].get())
        app.mode.set('full-map')
        app.vars['height_engine'].set('estimate')
        app.vars['scan_strategy'].set('nearest')
        app._set_mode(reset_output=False)
        self.assertEqual(app.vars['version'].get(), '1.21.8')
        self.assertIn('-52', app.height_note.cget('text'))
        app.vars['scan_strategy'].set('exhaustive')
        app._set_mode(reset_output=False)
        self.assertIn('基板', app.height_note.cget('text'))
        self.assertTrue(app.groups['max_y'].winfo_manager())

    def test_scroll_and_hover_bindings_exist(self):
        app = self.app
        self.assertIn('MouseWheel', app.form_canvas.bind())
        self.assertIn('Enter', app.mode_widgets['candidates'].bind())
