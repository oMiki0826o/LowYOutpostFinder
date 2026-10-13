"""File: test_tower_cli.py
Modification: 2026-10-13 — CLI conditional worldgen-Y calculation, never claimed verified.
"""
import json
import tempfile
from pathlib import Path
import unittest

from finder import candidates, main
from test_tower_geometry import make_jar


class TowerCLI(unittest.TestCase):
    def test_projection_from_exact_supplied_surface_is_conditional_only(self):
        with tempfile.TemporaryDirectory() as t:
            root = Path(t)
            game = root / 'assets.jar'
            make_jar(game)
            row = next(candidates(123, 8192))
            output = root / 'tower.json'
            code = main(['tower-project', '--version', '1.21.8', '--seed', '123',
                         '--chunk-x', str(row['chunk_x']), '--chunk-z', str(row['chunk_z']),
                         '--game-jar', str(game), '--world-surface-wg', '-30',
                         '--out', str(output)])
            self.assertEqual(code, 0)
            result = json.loads(output.read_text())
            self.assertEqual(result['base_min_y'], -31)
            self.assertEqual(result['tower_min_y'], -28)
            self.assertEqual(result['classification'], 'conditional_on_external_worldgen_height')
            self.assertFalse(result['vanilla_generated'])

    def test_reject_wrong_random_candidate(self):
        with tempfile.TemporaryDirectory() as t:
            root = Path(t)
            game = root / 'assets.jar'
            make_jar(game)
            code = main(['tower-project', '--seed', '123', '--chunk-x', '1', '--chunk-z', '2',
                         '--game-jar', str(game), '--world-surface-wg', '-30'])
            self.assertEqual(code, 2)

if __name__ == '__main__':
    unittest.main()
