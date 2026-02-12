@echo off
title JARVIS Launcher
cd /d "%~dp0"
cls
echo ============================================================
echo JARVIS - AI Assistant
echo ============================================================
echo.
echo Select Mode:
echo 1. Normal Mode (Online STT / Browser)
echo 2. Service Mode (Offline / Wake Word: "Jarvis")
echo 3. Conversation Mode (LLM / Multi-turn)
echo 4. Exit
echo.

set /p choice="Enter choice (1-4): "

if "%choice%"=="1" goto normal
if "%choice%"=="2" goto service
if "%choice%"=="3" goto convo
if "%choice%"=="4" goto end

:normal
echo Starting Normal Mode...
call .venv\Scripts\activate
python jarvis.py
pause
goto end

:service
echo Starting Service Mode...
call .venv\Scripts\activate
python jarvis.py --service
pause
goto end

:convo
echo Starting Conversation Mode...
call .venv\Scripts\activate
python jarvis.py --convo
pause
goto end

:end
echo Goodbye.
