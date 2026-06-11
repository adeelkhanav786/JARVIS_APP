"""
Jarvis.app — FastAPI Backend
Run with: uvicorn main:app --reload --port 8000
"""

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
import os, json, asyncio
from pathlib import Path

from db import init_db
from auth import router as auth_router
from chat import router as chat_router, ws_endpoint

# ── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(title="Jarvis.app", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Init DB on startup ────────────────────────────────────────────────────────
@app.on_event("startup")
async def startup():
    init_db()
    print("✅ Jarvis.app backend started")

# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(auth_router, prefix="/api/auth", tags=["auth"])
app.include_router(chat_router, prefix="/api/chat", tags=["chat"])

# ── WebSocket ─────────────────────────────────────────────────────────────────
@app.websocket("/ws/{username}")
async def websocket_route(websocket: WebSocket, username: str):
    await ws_endpoint(websocket, username)

# ── Serve frontend (production) ───────────────────────────────────────────────
frontend_path = Path(__file__).parent.parent / "frontend" / "public"
if frontend_path.exists():
    app.mount("/", StaticFiles(directory=str(frontend_path), html=True), name="static")
