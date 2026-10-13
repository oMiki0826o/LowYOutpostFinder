"""Launch the LowY Outpost Finder graphical interface."""
from __future__ import annotations


def main() -> int | None:
    from lowy_outpost_finder.gui import main as gui_main

    return gui_main()


if __name__ == "__main__":
    raise SystemExit(main())
