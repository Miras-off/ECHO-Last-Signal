@echo off
chcp 65001 >nul
cd /d "%~dp0"
title ECHO - установка игры
set "PYEXE="
if not exist ".venv\Scripts\python.exe" (
  py -3.12 -m venv .venv 2>nul
  if not exist ".venv\Scripts\python.exe" py -3.11 -m venv .venv 2>nul
  if not exist ".venv\Scripts\python.exe" py -3 -m venv .venv 2>nul
  if not exist ".venv\Scripts\python.exe" python -m venv .venv 2>nul
)
if not exist ".venv\Scripts\python.exe" (
  echo Не удалось создать среду. Установи Python 3.11 или 3.12.
  pause
  exit /b 1
)
set "PYEXE=.venv\Scripts\python.exe"
echo Устанавливаю Pygame-ce...
"%PYEXE%" -m pip install -r requirements-game.txt
if errorlevel 1 (
  echo Ошибка установки. Проверь интернет и версию Python.
  pause
  exit /b 1
)
echo.
echo Игра установлена. Запуск: 02_RUN.bat
 echo Для голосового управления выполни 03_DOWNLOAD_VOICE_MODEL.bat
pause
