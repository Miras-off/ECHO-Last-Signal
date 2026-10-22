@echo off
setlocal
cd /d "%~dp0"
title ECHO - Last Signal

if not exist ".venv\Scripts\python.exe" (
    echo [ERROR] Python environment is missing.
    echo Please run 01_SETUP.bat first.
    pause
    exit /b 1
)

echo [ECHO] Starting game...
".venv\Scripts\python.exe" "main.py"
if errorlevel 1 (
    echo.
    echo [ERROR] Game failed to start. Read the error above.
    echo Check crash_log.txt if it exists.
)
echo.
pause
