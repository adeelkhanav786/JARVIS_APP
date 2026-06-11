@echo off
title JARVIS Backend
cd /d "%~dp0backend"

echo [JARVIS] Checking Python...
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found. Install from https://python.org
    pause & exit
)

echo [JARVIS] Installing dependencies...
pip install -r requirements.txt -q

echo [JARVIS] Starting backend on http://localhost:8000 ...
echo [JARVIS] Open your browser to http://localhost:8000
echo [JARVIS] Press Ctrl+C to stop.
echo.
python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
pause
