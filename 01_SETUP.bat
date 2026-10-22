@echo off
setlocal
cd /d "%~dp0"
title ECHO - Setup

echo [ECHO] Preparing Python environment...
if not exist ".venv\Scripts\python.exe" (
    py -3.12 -m venv .venv 2>nul
    if not exist ".venv\Scripts\python.exe" py -3.11 -m venv .venv 2>nul
    if not exist ".venv\Scripts\python.exe" py -3 -m venv .venv 2>nul
    if not exist ".venv\Scripts\python.exe" python -m venv .venv 2>nul
)
if not exist ".venv\Scripts\python.exe" (
    echo [ERROR] Python environment could not be created. Install Python 3.11 or 3.12.
    pause
    exit /b 1
)
echo [ECHO] Installing Pygame dependencies...
".venv\Scripts\python.exe" -m pip install -r requirements-game.txt
if errorlevel 1 (
    echo [ERROR] Dependency installation failed. Check your Internet connection.
    pause
    exit /b 1
)
echo.
echo [SUCCESS] Setup completed. Run 02_RUN.bat to play.
echo [OPTIONAL] Run 03_DOWNLOAD_VOICE_MODEL.bat for microphone voice commands.
pause
