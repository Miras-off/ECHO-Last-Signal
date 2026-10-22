@echo off
chcp 65001 >nul
cd /d "%~dp0"
title ECHO: Последний сигнал
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" main.py
) else (
  echo Сначала запусти 01_SETUP.bat
  pause
  exit /b 1
)
if errorlevel 1 echo Ошибка запуска. См. crash_log.txt и README.md.
pause
