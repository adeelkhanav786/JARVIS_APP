# J.A.R.V.I.S. — AI Assistant App

## Quick Start

### Windows
Double-click `start.bat`

### Mac / Linux
```bash
bash start.sh
```

Then open **http://localhost:8000** in your browser.

---

## Setup (Required)

### 1. Set your Gemini API key

Get a free key at https://aistudio.google.com

**Windows** — in Command Prompt before running:
```
set GEMINI_API_KEY=your_key_here
```

**Mac/Linux** — in Terminal:
```bash
export GEMINI_API_KEY=your_key_here
```

Or edit `start.bat` / `start.sh` and add the key there permanently.

### 2. (Optional) Weather tool

Get a free key at https://openweathermap.org/api
```
set OPENWEATHER_KEY=your_key_here
```

---

## Features

| Feature | How to use |
|---|---|
| **AI Chat** | Type anything — powered by Gemini 1.5 Flash |
| **Agent Tools** | Ask "what's the weather in Mumbai?", "calculate 245*18", "what time is it", "save a note: buy milk", "show my notes" |
| **Open Apps** | Say "open WhatsApp", "open YouTube", "open Spotify" etc. |
| **Voice Input** | Tap the 🎤 mic button and speak |
| **Text to Speech** | Tap 🔊 SPEAK on any AI message |
| **Attach Files** | Tap ➕ to attach photos, files (PDF/TXT/CSV), or URLs |
| **Camera** | Tap ➕ → Camera (desktop opens live camera, mobile uses native) |
| **New Chat** | Tap 💬 to start fresh (saves current chat) |
| **Chat History** | Tap ⚙ Settings → Chats tab to load previous conversations |
| **Change Password** | Tap ⚙ Settings → Account tab |

---

## Agent Tools Available

- 🌤 **get_weather** — Live weather for any city (needs OPENWEATHER_KEY)
- 🔍 **web_search** — Search the web for current info
- 📝 **save_note** — Save notes and reminders to your account
- 📋 **read_notes** — Read your saved notes
- 🧮 **calculate** — Math, percentages, trig, unit conversion
- 🕐 **get_datetime** — Current date and time in any timezone

---

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `GEMINI_API_KEY` | **Yes** | Your Gemini API key |
| `GEMINI_MODEL` | No | Default: `gemini-1.5-flash` |
| `OPENWEATHER_KEY` | No | For live weather |
| `GEMINI_RPM` | No | Requests per minute cap (default: 10) |

---

## File Structure

```
jarvis_app/
├── backend/
│   ├── main.py          ← FastAPI server entry point
│   ├── chat.py          ← AI agent loop + all tools + WebSocket
│   ├── auth.py          ← Login / Register / Change Password
│   ├── db.py            ← SQLite database (per-user tables)
│   ├── requirements.txt ← Python dependencies
│   └── jarvis.db        ← Created automatically on first run
├── frontend/
│   └── public/
│       ├── index.html   ← Landing page
│       ├── login.html   ← Login / Register
│       ├── chat.html    ← Main chat UI
│       ├── app.js       ← Shared JS config
│       ├── manifest.json← PWA manifest
│       └── sw.js        ← Service worker (offline support)
├── start.bat            ← Windows launcher
└── start.sh             ← Mac/Linux launcher
```
