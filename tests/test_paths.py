"""Path resolution contracts for the packaged application."""
from __future__ import annotations

import os
from pathlib import Path
import sys
import unittest


class PathTests(unittest.TestCase):
    def test_cli_command_uses_module_entry_point(self) -> None:
        from lowy_outpost_finder.paths import cli_command

        self.assertEqual(
            cli_command("candidates", "--seed", "123"),
            [sys.executable, "-m", "lowy_outpost_finder", "candidates", "--seed", "123"],
        )

    def test_native_binary_resolves_beneath_project_bin(self) -> None:
        from lowy_outpost_finder.paths import PROJECT_ROOT, native_binary

        suffix = ".exe" if os.name == "nt" else ""
        self.assertEqual(native_binary("region_scan"), PROJECT_ROOT / "bin" / f"region_scan{suffix}")

    def test_project_root_contains_version_file(self) -> None:
        from lowy_outpost_finder.paths import PROJECT_ROOT

        self.assertTrue((Path(PROJECT_ROOT) / "VERSION").is_file())


if __name__ == "__main__":
    unittest.main()
