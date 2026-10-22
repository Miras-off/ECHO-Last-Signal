@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo ==========================================
echo   ECHO - setup Python environment
 echo ==========================================
if not exist ".venv\Scripts\python.exe" (
    py -3.12 -m venv .venv 2>nul
    if not exist ".venv\Scripts\python.exe" py -3.11 -m venv .venv 2>nul
    if not exist ".venv\Scripts\python.exe" py -3 -m venv .venv 2>nul
    if not exist ".venv\Scripts\python.exe" python -m venv .venv
)
if not exist ".venv\Scripts\python.exe" (
    echo Could not create venv. Install Python 3.11 or 3.12 from python.org
    pause
    exit /b 1
)
".venv\Scripts\python.exe" -m pip install --upgrade pip
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 (
    echo Packages installation failed. Check Internet and Python version.
    pause
    exit /b 1
)
echo.
echo SETUP OK. Run 02_RUN.bat. For voice: 03_DOWNLOAD_VOICE_MODEL.bat.
pause
