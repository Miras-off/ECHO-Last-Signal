@echo off
chcp 65001 >nul
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo First run 01_SETUP.bat
    pause
    exit /b 1
)
".venv\Scripts\python.exe" download_voice_model.py
pause
