#!/bin/bash
cd "$(dirname "$0")/backend"
echo "[JARVIS] Installing dependencies..."
pip install -r requirements.txt -q
echo "[JARVIS] Starting on http://localhost:8000 ..."
python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
