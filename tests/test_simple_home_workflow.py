"""Simple low-Y home: search contract and CSV regression tests."""
import csv
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch

from lowy_outpost_finder.simple_workflow import SimpleRequest, build_search_arguments, export_results
from lowy_outpost_finder.simple_gui import is_classic_entry
import tkinter as tk
from tkinter import ttk
from lowy_outpost_finder.native_bootstrap import BootstrapError, ensure_native_estimator, estimator_available


class SimpleWorkflowTests(unittest.TestCase):
    def test_default_estimated_center_scan_has_world_radius(self):
        req = SimpleRequest(seed='1233211234567')
        cmd = build_search_arguments(req, Path('/tmp/raw.csv'))
        self.assertEqual(cmd[0], 'full-map')
        self.assertEqual(cmd[cmd.index('--max-y') + 1], '-37')
        self.assertEqual(cmd[cmd.index('--top') + 1], '25')
        self.assertEqual(cmd[cmd.index('--height-engine') + 1], 'estimate')
        self.assertEqual(cmd[cmd.index('--strategy') + 1], 'nearest')
        self.assertEqual(cmd[cmd.index('--engine') + 1], 'native')
        self.assertEqual(cmd[cmd.index('--x-min') + 1], '-29999984')
        self.assertEqual(cmd[cmd.index('--x-max') + 1], '29999984')

    def test_radius_clips_and_center_stays_user_selected(self):
        req = SimpleRequest(seed='-123', radius='4096', center_x='-29000000', center_z='900')
        cmd = build_search_arguments(req, Path('raw.csv'))
        self.assertEqual(cmd[cmd.index('--x-min') + 1], '-29004096')
        self.assertEqual(cmd[cmd.index('--x-max') + 1], '-28995904')
        self.assertEqual(cmd[cmd.index('--center-x') + 1], '-29000000')
        self.assertEqual(cmd[cmd.index('--z-max') + 1], '4996')

    def test_invalid_seed_limit_and_height_fail_closed(self):
        for req in (SimpleRequest(seed='bad'), SimpleRequest(seed='1', top='0'),
                    SimpleRequest(seed='1', radius='30000001'),
                    SimpleRequest(seed='1', max_y='321'),
                    SimpleRequest(seed='1', center_x='30000000')):
            with self.subTest(req=req), self.assertRaises(ValueError):
                build_search_arguments(req, Path('raw.csv'))

    def test_csv_has_fixed_header_and_center_origin_distances(self):
        req = SimpleRequest(seed='123', radius='8192', max_y='-37',
                            top='4', center_x='100', center_z='0')
        with tempfile.TemporaryDirectory() as td:
            raw, public = Path(td)/'raw.csv', Path(td)/'result.csv'
            with raw.open('w', newline='', encoding='utf-8') as f:
                w = csv.DictWriter(f, fieldnames=('version', 'seed', 'chunk_x', 'chunk_z',
                    'x', 'z', 'projected_structure_center_y', 'classification'))
                w.writeheader()
                w.writerow(dict(version='1.21.8', seed='123', chunk_x='7', chunk_z='0',
                                x='112', z='0', projected_structure_center_y='-54',
                                classification='estimated_only'))
                w.writerow(dict(version='1.21.8', seed='123', chunk_x='0', chunk_z='4',
                                x='0', z='64', projected_structure_center_y='-45',
                                classification='estimated_only'))
            rows = export_results(raw, public, req)
            self.assertEqual([r['index'] for r in rows], [1,2])
            self.assertEqual(rows[0]['x'], 112)
            self.assertEqual(rows[0]['estimated_y'], -54)
            self.assertEqual(rows[0]['chunk_x'], 7)
            self.assertEqual(rows[0]['distance_from_center'], '12.00')
            self.assertEqual(rows[0]['distance_from_origin'], '112.00')
            self.assertEqual(rows[0]['status'], 'estimated_only')
            with public.open(encoding='utf-8', newline='') as f:
                reader = csv.DictReader(f)
                self.assertEqual(reader.fieldnames,
                    ['version','seed','index','x','estimated_y','z',
                     'distance_from_center','distance_from_origin','chunk_x','chunk_z','status'])
                self.assertEqual(len(list(reader)), 2)

    def test_distance_ranking_uses_exact_squared_distance_before_rounding(self):
        req = SimpleRequest(seed='3', radius='30000000', top='2')
        with tempfile.TemporaryDirectory() as td:
            raw = Path(td) / 'raw.csv'
            with raw.open('w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=(
                    'version', 'seed', 'chunk_x', 'chunk_z', 'x', 'z',
                    'projected_structure_center_y', 'classification'))
                writer.writeheader()
                for cx in (-2, -1):
                    writer.writerow(dict(
                        version='1.21.8', seed='3', chunk_x=cx, chunk_z=1250000,
                        x=cx*16, z=20000000,
                        projected_structure_center_y=-40,
                        classification='estimated_only'))
            rows = export_results(raw, Path(td) / 'public.csv', req)
            self.assertEqual(rows[0]['x'], -16)
            self.assertEqual(rows[1]['x'], -32)

    def test_csv_rejects_y_above_threshold_or_fake_verified_status(self):
        req = SimpleRequest(seed='1')
        for status,y in [('estimated_only','-37'), ('verified_tower','-54')]:
            with self.subTest(status=status,y=y), tempfile.TemporaryDirectory() as td:
                raw = Path(td)/'raw.csv'
                raw.write_text(
                    'version,seed,chunk_x,chunk_z,x,z,projected_structure_center_y,classification\\n'
                    f'1.21.8,1,1,2,16,32,{y},{status}\\n', encoding='utf-8')
                with self.assertRaises(ValueError):
                    export_results(raw, Path(td)/'public.csv', req)


class TkThemeTypeGuardsTests(unittest.TestCase):
    """No display server needed; tests Tk's actual Python MRO on all OSes."""

    def test_ttk_entry_and_combobox_are_not_classic_entries(self):
        self.assertTrue(issubclass(ttk.Entry, tk.Entry))
        self.assertTrue(issubclass(ttk.Combobox, tk.Entry))
        self.assertTrue(is_classic_entry(tk.Entry.__new__(tk.Entry)))
        self.assertFalse(is_classic_entry(ttk.Entry.__new__(ttk.Entry)))
        self.assertFalse(is_classic_entry(ttk.Combobox.__new__(ttk.Combobox)))


class NativeBootstrapTests(unittest.TestCase):
    def test_existing_executable_is_reused_without_compilation(self):
        with tempfile.TemporaryDirectory() as td:
            exe = Path(td)/'outpost_estimate'
            exe.write_bytes(b'scanner')
            exe.chmod(0o755)
            with patch('lowy_outpost_finder.native_bootstrap.subprocess.run') as run:
                run.return_value.returncode = 0
                run.return_value.stdout = (
                    '{"model_fingerprint":"lowyswamphut-approx-1.21.8-centre-strict-single-sample",'
                    '"matches":1,"next_ring":1,"rows":[]}')
                actual = ensure_native_estimator(native_path=exe)
            self.assertEqual(actual, exe)
            run.assert_called_once()

    def test_incompatible_native_binary_is_not_marked_available(self):
        with tempfile.TemporaryDirectory() as td:
            exe = Path(td) / 'outpost_estimate'
            exe.write_bytes(b'old incompatible native binary')
            exe.chmod(0o755)
            with patch('lowy_outpost_finder.native_bootstrap.subprocess.run') as run:
                run.return_value.returncode = 0
                run.return_value.stdout = 'some program: --help'
                self.assertFalse(estimator_available(exe))
                run.return_value.stdout = '{"model_fingerprint":"unexpected"}'
                self.assertFalse(estimator_available(exe))
                run.side_effect = OSError('bad executable format')
                self.assertFalse(estimator_available(exe))

    def test_missing_required_compiler_gives_actionable_error(self):
        with tempfile.TemporaryDirectory() as td:
            with patch('lowy_outpost_finder.native_bootstrap.shutil.which',
                       side_effect=lambda x: None if x == 'cmake' else '/usr/bin/' + x):
                with self.assertRaisesRegex(BootstrapError, 'CMake|cmake'):
                    ensure_native_estimator(native_path=Path(td)/'not-installed')


if __name__ == '__main__':
    unittest.main()
