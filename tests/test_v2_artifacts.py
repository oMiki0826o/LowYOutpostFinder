"""File: test_v2_artifacts.py
Modification: 2026-10-13 — prevent report path collisions and evidence loss.
"""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from finder import main

class ArtifactSafetyTests(unittest.TestCase):
    def test_summary_collision_rejected_before_world_is_read(self):
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/'result.csv'
            with patch('finder.confirmed_world') as read_world:
                self.assertEqual(main(['search-live','--world',td,
                                       '--out',str(path),'--summary',str(path)]),2)
                read_world.assert_not_called()
            self.assertFalse(path.exists())

    def test_checkpoint_cannot_overwrite_filtered_hits(self):
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/'result.csv'
            with patch('finder.confirmed_world') as read_world:
                self.assertEqual(main(['search-live','--world',td,
                                       '--out',str(path),'--checkpoint',str(path)]),2)
                read_world.assert_not_called()

if __name__=='__main__':unittest.main()
