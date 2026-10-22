@echo off
setlocal
cd /d "%~dp0"
title ECHO - Voice Setup

if not exist ".venv\Scripts\python.exe" (
    echo [ERROR] Run 01_SETUP.bat first.
    pause
    exit /b 1
)
echo [ECHO] Installing Vosk and sounddevice...
".venv\Scripts\python.exe" -m pip install "vosk>=0.3.45,<0.4" "sounddevice>=0.5,<0.6"
if errorlevel 1 (
    echo [ERROR] Could not install voice dependencies.
    pause
    exit /b 1
)
echo [ECHO] Downloading the Russian Vosk model...
".venv\Scripts\python.exe" "download_voice_model.py"
if errorlevel 1 (
    echo [ERROR] Model download failed. See error above.
)
pause
