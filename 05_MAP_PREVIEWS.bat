@echo off
setlocal
cd /d "%~dp0"
title ECHO - Map Previews
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" -m pip install Pillow
    ".venv\Scripts\python.exe" "scripts\export_map_previews.py"
) else (
    py -3 -m pip install Pillow
    py -3 "scripts\export_map_previews.py"
)
pause
