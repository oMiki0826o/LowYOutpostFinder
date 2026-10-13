"""Contracts for keeping Tk tests out of the cross-platform headless run."""
from __future__ import annotations

from pathlib import Path
import tempfile
import unittest


class HeadlessRunnerTests(unittest.TestCase):
    def test_selects_non_gui_modules_only(self) -> None:
        from scripts.run_headless_tests import headless_test_modules

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in ("test_core.py", "test_explorer_gui.py", "test_full_map_gui_tk.py"):
                (root / name).touch()
            self.assertEqual(headless_test_modules(root), ["test_core"])


if __name__ == "__main__":
    unittest.main()
