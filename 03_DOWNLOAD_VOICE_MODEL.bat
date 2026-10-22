@echo off
chcp 65001 >nul
cd /d "%~dp0"
title ECHO - установка русского распознавания голоса
if not exist ".venv\Scripts\python.exe" (
  echo Сначала запусти 01_SETUP.bat
  pause
  exit /b 1
)
echo Устанавливаю Vosk и sounddevice...
".venv\Scripts\python.exe" -m pip install "vosk>=0.3.45,<0.4" "sounddevice>=0.5,<0.6"
if errorlevel 1 (
  echo Не удалось установить голосовые библиотеки. Проверь интернет.
  pause
  exit /b 1
)
echo Скачиваю официальную модель русского языка (около 45 МБ)...
".venv\Scripts\python.exe" download_voice_model.py
pause
