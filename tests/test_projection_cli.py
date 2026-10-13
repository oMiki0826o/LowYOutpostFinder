"""File: test_projection_cli.py
Modification: 2026-10-13 — require template dimensions from supplied game archive.
"""
import argparse
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import lowy_outpost_finder.cli as finder
from test_start_geometry import sample_jar

class EstimateGeometryCommandTests(unittest.TestCase):
    def test_cli_passes_real_dimensions_to_native(self):
        with tempfile.TemporaryDirectory() as td:
            jar = Path(td) / 'minecraft.jar'
            sample_jar(jar)
            opts = argparse.Namespace(version='1.21.8', seed=123, radius=8192, max_y=64,
                                      top=25, approx_biome=False, core_archive=Path(td)/'core.tar.gz',
                                      game_jar=jar, out=Path(td)/'result.csv')
            with patch('lowy_outpost_finder.cli.subprocess.run') as run, patch('pathlib.Path.is_file', return_value=True):
                finder.run_estimate(opts)
            argv = run.call_args.args[0]
            self.assertEqual(argv[argv.index('--template-width')+1], '13')
            self.assertEqual(argv[argv.index('--template-depth')+1], '17')

    def test_mode_rejects_wrong_version(self):
        opts = argparse.Namespace(version='26.3', game_jar=Path('ignore'))
        with self.assertRaisesRegex(ValueError, '1.21.8'):
            finder.run_estimate(opts)

if __name__ == '__main__':
    unittest.main()
