@echo off
rem File: start_gui.bat
rem Modification: 2026-10-12 — Windows launcher.
cd /d "%~dp0"
py -3 start_gui.py
if errorlevel 9009 python start_gui.py
pause
