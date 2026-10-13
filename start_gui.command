#!/bin/sh
# File: start_gui.command
# Modification: 2026-10-12 — macOS double-click launcher.
set -eu
cd "$(dirname "$0")"
exec python3 start_gui.py
