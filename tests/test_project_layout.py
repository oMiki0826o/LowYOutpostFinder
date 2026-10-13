"""Repository layout and public entry-point contracts."""
from __future__ import annotations

import importlib
from pathlib import Path
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]


class ProjectLayoutTests(unittest.TestCase):
    def test_package_import_surface(self) -> None:
        cli = importlib.import_module("lowy_outpost_finder.cli")
        gui = importlib.import_module("lowy_outpost_finder.gui")
        full_map = importlib.import_module("lowy_outpost_finder.full_map")
        versions = importlib.import_module("lowy_outpost_finder.versions")

        for name in ("main", "candidates", "WorldChunks"):
            self.assertTrue(hasattr(cli, name), name)
        self.assertTrue(callable(gui.main))
        self.assertTrue(callable(full_map.scan))
        self.assertTrue(hasattr(versions, "VERSIONS"))

    def test_root_has_one_python_launcher(self) -> None:
        python_files = sorted(path.name for path in ROOT.glob("*.py"))
        self.assertEqual(python_files, ["LowYOutpostFinder.py"])

    def test_launcher_delegates_to_package_gui(self) -> None:
        launcher = importlib.import_module("LowYOutpostFinder")
        with patch("lowy_outpost_finder.gui.main", return_value=None) as gui_main:
            self.assertIsNone(launcher.main())
        gui_main.assert_called_once_with()

    def test_package_module_delegates_to_cli(self) -> None:
        package_main = importlib.import_module("lowy_outpost_finder.__main__")
        with patch("lowy_outpost_finder.cli.main", return_value=7) as cli_main:
            self.assertEqual(package_main.main(), 7)
        cli_main.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
