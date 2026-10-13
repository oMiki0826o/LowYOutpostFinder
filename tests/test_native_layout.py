"""Native source and build-tool layout contracts."""
from __future__ import annotations

from pathlib import Path
import subprocess
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]


class NativeLayoutTests(unittest.TestCase):
    def test_native_sources_are_grouped(self) -> None:
        self.assertTrue((ROOT / "native" / "src" / "region_scan.c").is_file())
        self.assertTrue((ROOT / "native" / "src" / "outpost_scan.c").is_file())
        self.assertFalse((ROOT / "src").exists())

    def test_one_build_entry_point_exposes_both_targets(self) -> None:
        result = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "build_native.py"), "--help"],
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("region", result.stdout)
        self.assertIn("terrain", result.stdout)
        self.assertFalse((ROOT / "build.sh").exists())
        self.assertFalse((ROOT / "scripts" / "build_region_scan.py").exists())

    def test_examples_and_dependency_manifests_are_explicit(self) -> None:
        self.assertTrue((ROOT / "examples" / "seeds.txt").is_file())
        self.assertTrue((ROOT / "requirements.txt").is_file())
        self.assertTrue((ROOT / "requirements-dev.txt").is_file())


if __name__ == "__main__":
    unittest.main()
