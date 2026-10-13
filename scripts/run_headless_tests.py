#!/usr/bin/env python3
"""Run every test that does not require a graphical Tk interpreter."""
from __future__ import annotations

from pathlib import Path
import sys
import unittest


GUI_TEST_MODULES = frozenset({
    "test_explorer_gui",
    "test_full_map_gui_tk",
    "test_gui_english",
    "test_gui_lifecycle",
    "test_main_gui_close",
    "test_v2_gui_progress",
})


def headless_test_modules(test_root: Path) -> list[str]:
    """Return sorted test-module stems safe for a headless interpreter."""
    return sorted(
        path.stem
        for path in test_root.glob("test_*.py")
        if path.stem not in GUI_TEST_MODULES
    )


def main() -> int:
    project_root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(project_root))
    test_root = project_root / "tests"
    sys.path.insert(0, str(test_root))
    names = [f"tests.{name}" for name in headless_test_modules(test_root)]
    suite = unittest.defaultTestLoader.loadTestsFromNames(names)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
