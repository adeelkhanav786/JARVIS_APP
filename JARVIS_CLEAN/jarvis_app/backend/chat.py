"""
chat.py  —  JARVIS AI Agent
Upgrade: full ReAct tool-use loop via google-genai (new SDK).
Tools: get_weather · web_search · save_note · read_notes · calculate · get_datetime
All previous features preserved: app opener, sessions, WebSocket, REST, file context.
"""

import os, re, json, uuid, math, datetime, asyncio, logging
from typing import Any
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException
from pydantic import BaseModel
from db import (
    create_session, update_session_title, get_sessions,
    delete_session, delete_all_sessions, session_exists,
    save_message, load_messages, provision_user,
    save_msg, load_history, get_conn,          # legacy + notes
)

log    = logging.getLogger("jarvis.chat")
router = APIRouter()

# ── Config ────────────────────────────────────────────────────────────────────
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_MODEL   = os.environ.get("GEMINI_MODEL", "gemini-3.5-flash")   # ← updated from retired 2.0-flash
WEATHER_KEY    = os.environ.get("OPENWEATHER_KEY", "")                # optional
MAX_TOOL_ROUNDS = 6   # max back-and-forth tool calls per message

SYSTEM_PROMPT = """You are J.A.R.V.I.S. — Just A Rather Very Intelligent System, \
the AI assistant from Iron Man. You are witty, precise, and proactive.

You have access to real tools. Use them whenever the user asks for:
- Current weather, temperature, forecast
- Any fact that may be recent or changing
- Calculations, math, unit conversions
- Saving or reading personal notes/reminders
- Current date, time, day of the week

Rules:
- Always use the tool rather than guessing.
- Never fabricate weather data, news, or calculations.
- Keep replies concise and in-character.
- After getting a tool result, respond naturally — don't just echo the raw data.
- For multi-step requests, chain tool calls automatically."""

# ── APP LINKS (deep-links + web fallbacks) ────────────────────────────────────
APP_LINKS = {
    "youtube":       ("youtube://",                    "https://www.youtube.com",          "▶"),
    "instagram":     ("instagram://",                  "https://www.instagram.com",        "📸"),
    "whatsapp":      ("whatsapp://",                   "https://web.whatsapp.com",         "💬"),
    "facebook":      ("fb://",                         "https://www.facebook.com",         "👍"),
    "twitter":       ("twitter://",                    "https://www.twitter.com",          "🐦"),
    "x":             ("twitter://",                    "https://www.x.com",                "🐦"),
    "snapchat":      ("snapchat://",                   "https://www.snapchat.com",         "👻"),
    "telegram":      ("tg://",                         "https://telegram.org",             "✈"),
    "discord":       ("discord://",                    "https://discord.com",              "🎮"),
    "linkedin":      ("linkedin://",                   "https://www.linkedin.com",         "💼"),
    "reddit":        ("reddit://",                     "https://www.reddit.com",           "🔴"),
    "tiktok":        ("snssdk1233://",                 "https://www.tiktok.com",           "🎵"),
    "pinterest":     ("pinterest://",                  "https://www.pinterest.com",        "📌"),
    "sharechat":     ("sharechat://",                  "https://sharechat.com",            "🗣"),
    "netflix":       ("nflx://",                       "https://www.netflix.com",          "🎬"),
    "spotify":       ("spotify://",                    "https://open.spotify.com",         "🎵"),
    "hotstar":       ("hotstar://",                    "https://www.hotstar.com",          "⭐"),
    "prime video":   ("aiv://",                        "https://www.primevideo.com",       "📦"),
    "prime":         ("aiv://",                        "https://www.primevideo.com",       "📦"),
    "twitch":        ("twitch://",                     "https://www.twitch.tv",            "🟣"),
    "mxplayer":      ("mx://",                         "https://www.mxplayer.in",          "🎞"),
    "youtube music": ("youtubemusic://",               "https://music.youtube.com",        "🎶"),
    "gmail":         ("googlegmail://",                "https://mail.google.com",          "📧"),
    "maps":          ("comgooglemaps://",              "https://maps.google.com",          "🗺"),
    "google maps":   ("comgooglemaps://",              "https://maps.google.com",          "🗺"),
    "google":        ("googlechrome://",               "https://www.google.com",           "🔍"),
    "google drive":  ("googledrive://",                "https://drive.google.com",         "💾"),
    "drive":         ("googledrive://",                "https://drive.google.com",         "💾"),
    "google meet":   ("meet://",                       "https://meet.google.com",          "📹"),
    "meet":          ("meet://",                       "https://meet.google.com",          "📹"),
    "google photos": ("googlephotos://",               "https://photos.google.com",        "🖼"),
    "translate":     ("googletranslate://",            "https://translate.google.com",     "🌐"),
    "amazon":        ("com.amazon.mobile.shopping://", "https://www.amazon.com",           "🛒"),
    "flipkart":      ("flipkart://",                   "https://www.flipkart.com",         "🛍"),
    "meesho":        ("meesho://",                     "https://www.meesho.com",           "🏷"),
    "myntra":        ("myntra://",                     "https://www.myntra.com",           "👗"),
    "ajio":          ("ajio://",                       "https://www.ajio.com",             "🛍"),
    "gpay":          ("tez://",                        "https://pay.google.com",           "💳"),
    "google pay":    ("tez://",                        "https://pay.google.com",           "💳"),
    "phonepe":       ("phonepe://",                    "https://www.phonepe.com",          "💜"),
    "paytm":         ("paytmmp://",                    "https://paytm.com",                "💰"),
    "bhim":          ("bhim://",                       "https://bhimupi.org.in",           "🇮🇳"),
    "swiggy":        ("swiggy://",                     "https://www.swiggy.com",           "🍔"),
    "zomato":        ("zomato://",                     "https://www.zomato.com",           "🍕"),
    "uber":          ("uber://",                       "https://www.uber.com",             "🚗"),
    "ola":           ("olacabs://",                    "https://www.olacabs.com",          "🚕"),
    "rapido":        ("rapido://",                     "https://rapido.bike",              "🏍"),
    "makemytrip":    ("makemytrip://",                 "https://www.makemytrip.com",       "✈"),
    "irctc":         ("irctc://",                      "https://www.irctc.co.in",          "🚂"),
    "zoom":          ("zoomus://",                     "https://zoom.us",                  "📡"),
    "teams":         ("msteams://",                    "https://teams.microsoft.com",      "📋"),
    "slack":         ("slack://",                      "https://slack.com",                "💬"),
    "notion":        ("notion://",                     "https://www.notion.so",            "📓"),
    "github":        ("github://",                     "https://www.github.com",           "🐙"),
    "pharmeasy":     ("pharmeasy://",                  "https://pharmeasy.in",             "💊"),
    "1mg":           ("onemg://",                      "https://www.1mg.com",              "🏥"),
    "practo":        ("practo://",                     "https://www.practo.com",           "👨‍⚕️"),
    "wikipedia":     ("wikipedia://",                  "https://www.wikipedia.org",        "📖"),
    "duolingo":      ("duolingo://",                   "https://www.duolingo.com",         "🦉"),
    "chatgpt":       ("",                              "https://chat.openai.com",          "🤖"),
    "phone":         ("tel:",                          "",                                 "📞"),
    "call":          ("tel:",                          "",                                 "📞"),
    "email":         ("mailto:",                       "",                                 "📧"),
    "sms":           ("sms:",                          "",                                 "💬"),
}

# ── DB: notes/reminders table ─────────────────────────────────────────────────

def _ensure_notes_table():
    """Create notes table if not exists (called once at startup)."""
    conn = get_conn()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS notes (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            username   TEXT NOT NULL,
            title      TEXT NOT NULL DEFAULT '',
            content    TEXT NOT NULL,
            created_at TEXT DEFAULT (datetime('now'))
        )
    """)
    conn.commit()
    conn.close()

# ── TOOL DEFINITIONS (schema for Gemini) ─────────────────────────────────────

def _build_tools():
    """Build Gemini Tool objects using the new google-genai SDK."""
    import google.genai.types as t

    weather_fn = t.FunctionDeclaration(
        name="get_weather",
        description=(
            "Get the current weather and temperature for any city. "
            "Use this whenever the user asks about weather, temperature, "
            "humidity, rain, or forecast."
        ),
        parameters=t.Schema(
            type="OBJECT",
            properties={
                "city": t.Schema(
                    type="STRING",
                    description="City name, e.g. 'Prayagraj', 'Mumbai', 'London'"
                )
            },
            required=["city"],
        ),
    )

    search_fn = t.FunctionDeclaration(
        name="web_search",
        description=(
            "Search the web for current information, recent news, facts, "
            "people, events, definitions, or anything that may have changed "
            "recently. Use this for questions about current events, scores, "
            "prices, or any factual query you're not certain about."
        ),
        parameters=t.Schema(
            type="OBJECT",
            properties={
                "query": t.Schema(
                    type="STRING",
                    description="A concise search query, e.g. 'IPL 2026 winner'"
                )
            },
            required=["query"],
        ),
    )

    save_note_fn = t.FunctionDeclaration(
        name="save_note",
        description=(
            "Save a note, reminder, task, or piece of information for the user. "
            "Use when the user says 'remember', 'note', 'remind me', 'save', "
            "or 'don't forget'."
        ),
        parameters=t.Schema(
            type="OBJECT",
            properties={
                "title":   t.Schema(type="STRING", description="Short title for the note"),
                "content": t.Schema(type="STRING", description="Full content of the note"),
            },
            required=["title", "content"],
        ),
    )

    read_notes_fn = t.FunctionDeclaration(
        name="read_notes",
        description=(
            "Retrieve the user's saved notes, reminders, or tasks. "
            "Use when the user asks 'what are my notes', 'show my reminders', "
            "'what did I save', or similar."
        ),
        parameters=t.Schema(
            type="OBJECT",
            properties={
                "query": t.Schema(
                    type="STRING",
                    description="Optional keyword to filter notes, or empty for all",
                    nullable=True,
                )
            },
            required=[],
        ),
    )

    calculate_fn = t.FunctionDeclaration(
        name="calculate",
        description=(
            "Evaluate a mathematical expression or do unit conversion. "
            "Use for arithmetic, percentages, square roots, trigonometry, "
            "or any calculation. Examples: '245 * 18', 'sqrt(144)', "
            "'sin(30 degrees)', '100 USD to INR estimate'."
        ),
        parameters=t.Schema(
            type="OBJECT",
            properties={
                "expression": t.Schema(
                    type="STRING",
                    description="The math expression to evaluate"
                )
            },
            required=["expression"],
        ),
    )

    datetime_fn = t.FunctionDeclaration(
        name="get_datetime",
        description=(
            "Get the current date, time, day of the week, or timezone info. "
            "Use whenever the user asks 'what time is it', 'what day is today', "
            "'what's today's date', or anything time-related."
        ),
        parameters=t.Schema(
            type="OBJECT",
            properties={
                "timezone": t.Schema(
                    type="STRING",
                    description="Timezone name, e.g. 'Asia/Kolkata'. Defaults to IST.",
                    nullable=True,
                )
            },
            required=[],
        ),
    )

    return t.Tool(
        function_declarations=[
            weather_fn, search_fn, save_note_fn,
            read_notes_fn, calculate_fn, datetime_fn,
        ]
    )

# ── TOOL EXECUTORS ────────────────────────────────────────────────────────────

async def _tool_get_weather(args: dict) -> str:
    city = (args.get("city") or "").strip()
    if not city:
        return "No city specified."
    if not WEATHER_KEY:
        # Graceful degradation — no key, still useful reply
        return (
            f"I don't have a live weather API key configured, so I can't fetch "
            f"real-time data for {city}. Ask your developer to set OPENWEATHER_KEY."
        )
    try:
        import httpx
        async with httpx.AsyncClient(timeout=8) as client:
            r = await client.get(
                "https://api.openweathermap.org/data/2.5/weather",
                params={"q": city, "appid": WEATHER_KEY, "units": "metric"},
            )
        if r.status_code == 404:
            return f"City '{city}' not found. Try a different spelling."
        if r.status_code != 200:
            return f"Weather API error {r.status_code} for {city}."
        d = r.json()
        return (
            f"{city.title()}: {d['weather'][0]['description'].capitalize()}, "
            f"{d['main']['temp']:.1f}°C (feels like {d['main']['feels_like']:.1f}°C), "
            f"humidity {d['main']['humidity']}%, "
            f"wind {d['wind']['speed']} m/s."
        )
    except Exception as e:
        return f"Weather fetch failed: {e}"


async def _tool_web_search(args: dict) -> str:
    query = (args.get("query") or "").strip()
    if not query:
        return "No search query provided."
    try:
        import httpx
        # DuckDuckGo Instant Answer API — no key required
        # Must request JSON explicitly; some CDN nodes return HTML without proper Accept header
        async with httpx.AsyncClient(timeout=12, follow_redirects=True) as client:
            r = await client.get(
                "https://api.duckduckgo.com/",
                params={"q": query, "format": "json", "no_html": "1", "skip_disambig": "1"},
                headers={
                    "User-Agent": "Mozilla/5.0 (compatible; JARVIS/1.0)",
                    "Accept": "application/json",
                },
            )
        # Guard against HTML response (happens when DDG rate-limits or redirects)
        ct = r.headers.get("content-type", "")
        if "html" in ct or not r.text.strip().startswith("{"):
            return (
                f"Search unavailable right now for '{query}'. "
                f"Try asking me to open Google: 'open google'"
            )
        d = r.json()
        parts = []

        abstract = (d.get("AbstractText") or "").strip()
        if abstract:
            parts.append(abstract[:600])

        answer = (d.get("Answer") or "").strip()
        if answer and answer not in parts:
            parts.append(answer[:300])

        if not parts:
            topics = [
                tp.get("Text", "").strip()
                for tp in d.get("RelatedTopics", [])
                if isinstance(tp, dict) and tp.get("Text")
            ]
            parts = [tp[:200] for tp in topics[:4]]

        if not parts:
            return (
                f"No instant answer found for '{query}'. "
                f"I can open Google for you — just say 'open google'."
            )
        return "\n".join(parts)
    except Exception as e:
        log.warning("web_search failed: %s", e)
        return f"Search unavailable right now: {e}"


async def _tool_save_note(args: dict, username: str) -> str:
    title   = (args.get("title")   or "Note").strip()[:120]
    content = (args.get("content") or "").strip()
    if not content:
        return "Nothing to save — content was empty."
    try:
        conn = get_conn()
        conn.execute(
            "INSERT INTO notes (username, title, content) VALUES (?,?,?)",
            (username, title, content)
        )
        conn.commit()
        conn.close()
        return f"Note saved: '{title}'"
    except Exception as e:
        return f"Failed to save note: {e}"


async def _tool_read_notes(args: dict, username: str) -> str:
    query = (args.get("query") or "").strip()
    try:
        conn = get_conn()
        if query:
            rows = conn.execute(
                "SELECT title, content, created_at FROM notes "
                "WHERE username=? AND (title LIKE ? OR content LIKE ?) "
                "ORDER BY id DESC LIMIT 10",
                (username, f"%{query}%", f"%{query}%")
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT title, content, created_at FROM notes "
                "WHERE username=? ORDER BY id DESC LIMIT 10",
                (username,)
            ).fetchall()
        conn.close()
        if not rows:
            return "No notes found." if not query else f"No notes matching '{query}'."
        lines = []
        for r in rows:
            ts = r["created_at"][:10] if r["created_at"] else ""
            lines.append(f"• [{ts}] {r['title']}: {r['content'][:150]}")
        return "\n".join(lines)
    except Exception as e:
        return f"Failed to read notes: {e}"


async def _tool_calculate(args: dict) -> str:
    expr = (args.get("expression") or "").strip()
    if not expr:
        return "No expression to calculate."
    try:
        # Safe math-only eval
        safe_globals = {k: getattr(math, k) for k in dir(math) if not k.startswith("_")}
        safe_globals.update({"abs": abs, "round": round, "pow": pow, "int": int, "float": float})
        # Convert degree trig shorthand: sin(30 degrees) → sin(radians(30))
        expr_eval = re.sub(
            r'(sin|cos|tan)\(([^)]+?)\s+degrees?\)',
            lambda m: f"{m.group(1)}(radians({m.group(2)}))",
            expr, flags=re.IGNORECASE
        )
        result = eval(expr_eval, {"__builtins__": {}}, safe_globals)
        # Format nicely
        if isinstance(result, float):
            result = round(result, 10)
            if result == int(result):
                result = int(result)
        return f"{expr} = {result}"
    except ZeroDivisionError:
        return "Division by zero."
    except Exception:
        # Try basic arithmetic with ast
        try:
            import ast as _ast
            tree = _ast.parse(expr, mode="eval")
            result = eval(compile(tree, "<calc>", "eval"), {"__builtins__": {}}, {})
            return f"{expr} = {result}"
        except Exception as e2:
            return f"Could not evaluate '{expr}': {e2}"


async def _tool_get_datetime(args: dict) -> str:
    tz_name = (args.get("timezone") or "Asia/Kolkata").strip()
    try:
        import zoneinfo
        tz = zoneinfo.ZoneInfo(tz_name)
    except Exception:
        try:
            import zoneinfo
            tz = zoneinfo.ZoneInfo("Asia/Kolkata")
            tz_name = "Asia/Kolkata"
        except Exception:
            now = datetime.datetime.now()
            return (
                f"Date: {now.strftime('%A, %d %B %Y')}\n"
                f"Time: {now.strftime('%I:%M %p')} (server local time)"
            )
    now = datetime.datetime.now(tz)
    return (
        f"Date: {now.strftime('%A, %d %B %Y')}\n"
        f"Time: {now.strftime('%I:%M %p')} {tz_name}"
    )


async def _execute_tool(name: str, args: dict, username: str) -> str:
    """Dispatch to the right tool executor."""
    if name == "get_weather":   return await _tool_get_weather(args)
    if name == "web_search":    return await _tool_web_search(args)
    if name == "save_note":     return await _tool_save_note(args, username)
    if name == "read_notes":    return await _tool_read_notes(args, username)
    if name == "calculate":     return await _tool_calculate(args)
    if name == "get_datetime":  return await _tool_get_datetime(args)
    return f"Unknown tool: {name}"

# ── RATE-LIMIT QUEUE (shared across all users, respects free-tier RPM) ────────

_rpm         = int(os.environ.get("GEMINI_RPM", "10"))
_min_gap     = 60.0 / _rpm          # seconds between calls
_last_call   = 0.0
_call_lock   = asyncio.Lock()

async def _throttled_call(coro):
    """Ensures no more than GEMINI_RPM calls per minute across all users."""
    global _last_call
    async with _call_lock:
        import time
        wait = (_last_call + _min_gap) - time.monotonic()
        if wait > 0:
            await asyncio.sleep(wait)
        result = await coro
        _last_call = time.monotonic()
        return result

# ── GEMINI CLIENT (new SDK) ───────────────────────────────────────────────────

_gemini_client = None

def _get_client():
    global _gemini_client
    if _gemini_client is None:
        import google.genai as genai
        _gemini_client = genai.Client(api_key=GEMINI_API_KEY)
    return _gemini_client

# ── AGENT LOOP ────────────────────────────────────────────────────────────────

async def run_agent(username: str, user_text: str) -> str:
    """
    Full ReAct agent loop:
      User message → Gemini thinks → maybe calls tool(s) → sees results → final reply
    Falls back gracefully if API key missing or quota hit.
    """
    if not GEMINI_API_KEY:
        return "⚠️ GEMINI_API_KEY is not set on the server."

    import google.genai as genai
    import google.genai.types as t

    client = _get_client()
    tools  = _build_tools()

    config = t.GenerateContentConfig(
        system_instruction=SYSTEM_PROMPT,
        tools=[tools],
        tool_config=t.ToolConfig(
            function_calling_config=t.FunctionCallingConfig(mode="AUTO")
        ),
        max_output_tokens=1024,
        temperature=0.7,
    )

    # Conversation history for this agent run (single-turn multi-step)
    contents: list[t.Content] = [
        t.Content(role="user", parts=[t.Part(text=user_text)])
    ]

    for round_num in range(MAX_TOOL_ROUNDS):
        try:
            response = await _throttled_call(
                asyncio.to_thread(
                    client.models.generate_content,
                    model=GEMINI_MODEL,
                    contents=contents,
                    config=config,
                )
            )
        except Exception as e:
            err = str(e)
            if "quota" in err.lower() or "429" in err:
                return "⚠️ AI quota reached. Please wait a moment and try again."
            if "API_KEY_INVALID" in err or "API key not valid" in err:
                return "⚠️ Invalid Gemini API key. Check server configuration."
            if "not found" in err.lower() and "model" in err.lower():
                return f"⚠️ Model '{GEMINI_MODEL}' not available. Set GEMINI_MODEL env var."
            log.error("Gemini error round %d: %s", round_num, err)
            return f"⚠️ AI error: {err[:200]}"

        candidate = response.candidates[0] if response.candidates else None
        if not candidate or not candidate.content or not candidate.content.parts:
            return "I'm not sure how to respond to that."

        parts = candidate.content.parts

        # Collect any function calls in this response
        function_calls = [p.function_call for p in parts if p.function_call]
        text_parts     = [p.text for p in parts if p.text]

        # No function calls → model gave final text answer
        if not function_calls:
            return " ".join(text_parts).strip() if text_parts else "Done."

        # Add model's response (with function calls) to conversation
        contents.append(candidate.content)

        # Execute every function call the model requested (may be parallel)
        tool_results = []
        for fc in function_calls:
            fn_name = fc.name
            fn_args = dict(fc.args) if fc.args else {}
            log.info("[agent:%s] tool call: %s(%s)", username, fn_name, fn_args)
            result = await _execute_tool(fn_name, fn_args, username)
            log.info("[agent:%s] tool result: %s", username, result[:120])
            tool_results.append(
                t.Part(
                    function_response=t.FunctionResponse(
                        name=fn_name,
                        response={"result": result},
                    )
                )
            )

        # Feed all tool results back as a single user turn
        contents.append(t.Content(role="user", parts=tool_results))

    # Hit max rounds — return whatever text we have
    return "I've completed the requested tasks."


# ── APP OPENER (unchanged logic, preserved exactly) ───────────────────────────

def resolve_open_request(query: str):
    q = query.lower().strip()
    if not any(w in q for w in ["open ", "launch ", "go to ", "visit ", "start "]):
        return None
    target = re.sub(r"^(open|launch|go to|visit|start)\s+", "", q).strip()
    # Sort by length descending so longer/more-specific keywords match first
    # e.g. "youtube music" before "youtube", "google maps" before "google", "x" last
    sorted_links = sorted(APP_LINKS.items(), key=lambda kv: len(kv[0]), reverse=True)
    for keyword, (scheme, web, emoji) in sorted_links:
        # Match whole-word to avoid "x" matching inside "netflix" or "mix"
        pattern = r"(?<![\w])" + re.escape(keyword) + r"(?![\w])"
        if re.search(pattern, target):
            return {"scheme": scheme, "web": web, "label": keyword.title(), "emoji": emoji}
    m = re.search(r'[\w-]+\.(com|org|net|io|co|in|edu|gov|ai|app|tv|me)', target)
    if m:
        url = f"https://www.{m.group(0)}"
        return {"scheme": "", "web": url, "label": m.group(0), "emoji": "🔗"}
    # Fallback to Google search
    search_url = f"https://www.google.com/search?q={target.replace(' ', '+')}"
    return {"scheme": "", "web": search_url, "label": f"Search: {target}", "emoji": "🔍"}


# ── SESSION HELPERS ───────────────────────────────────────────────────────────

def _auto_title(username: str, session_id: str, first_msg: str):
    sessions = get_sessions(username)
    for s in sessions:
        if s["session_id"] == session_id and s["title"] in ("New Chat", ""):
            title = first_msg[:42].strip() + ("…" if len(first_msg) > 42 else "")
            update_session_title(username, session_id, title)
            break


def _ensure_session(username: str, session_id: str):
    if not session_exists(username, session_id):
        provision_user(username)
        create_session(username, session_id)


# ── CORE HANDLER (shared by REST + WebSocket) ─────────────────────────────────

async def _handle_message(
    username: str,
    text: str,
    source: str,
    session_id: str,
    file_context: str,
) -> dict:
    """
    Returns:
      { reply, open (dict|None), is_open (bool), session_id }
    """
    sid = session_id or str(uuid.uuid4())
    _ensure_session(username, sid)
    save_message(username, sid, "user", text, source)
    _auto_title(username, sid, text)

    # 1. App-open intent (fast path — no AI needed)
    open_data = resolve_open_request(text)
    if open_data:
        reply = f"Opening {open_data['label']} for you, sir."
        save_message(username, sid, "assistant", reply, "ai")
        return {"reply": reply, "open": open_data, "is_open": True, "session_id": sid}

    # 2. Build full prompt (include file context if any)
    full_text = f"{file_context}\n\nUser question: {text}" if file_context else text

    # 3. Agent loop
    reply = await run_agent(username, full_text)
    save_message(username, sid, "assistant", reply, "ai")
    return {"reply": reply, "open": None, "is_open": False, "session_id": sid}


# ── REST ENDPOINTS ────────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    username:     str
    message:      str
    source:       str = "text"
    session_id:   str = ""
    file_context: str = ""


@router.post("/message")
async def send_message(req: ChatRequest):
    text = req.message.strip()
    if not text:
        raise HTTPException(400, "Empty message")
    result = await _handle_message(
        req.username, text, req.source, req.session_id, req.file_context
    )
    return result


# ── SESSION ENDPOINTS ─────────────────────────────────────────────────────────

@router.get("/sessions/{username}")
def list_sessions(username: str):
    provision_user(username)
    return get_sessions(username)


@router.post("/sessions/{username}")
def new_session(username: str):
    provision_user(username)
    sid = str(uuid.uuid4())
    create_session(username, sid)
    return {"session_id": sid, "title": "New Chat"}


@router.get("/sessions/{username}/{session_id}")
def get_session_messages(username: str, session_id: str, limit: int = 100):
    return load_messages(username, session_id, limit)


@router.delete("/sessions/{username}/{session_id}")
def remove_session(username: str, session_id: str):
    delete_session(username, session_id)
    return {"success": True}


@router.delete("/sessions/{username}")
def clear_all_sessions(username: str):
    delete_all_sessions(username)
    return {"success": True}


# ── LEGACY ENDPOINTS ──────────────────────────────────────────────────────────

@router.get("/history/{username}")
def get_history(username: str, limit: int = 100):
    return load_history(username, limit)


@router.delete("/history/{username}")
def clear_history(username: str):
    conn = get_conn()
    conn.execute("DELETE FROM chat_history WHERE username=?", (username,))
    conn.commit()
    conn.close()
    return {"success": True}


# ── NOTES ENDPOINT ────────────────────────────────────────────────────────────

@router.get("/notes/{username}")
async def get_notes(username: str):
    result = await _tool_read_notes({}, username)
    return {"notes": result}


# ── WEBSOCKET ─────────────────────────────────────────────────────────────────

async def ws_endpoint(websocket: WebSocket, username: str):
    await websocket.accept()
    try:
        while True:
            raw    = await websocket.receive_text()
            parsed = json.loads(raw)

            text     = parsed.get("message",      "").strip()
            source   = parsed.get("source",       "text")
            sid      = parsed.get("session_id",   "")
            file_ctx = parsed.get("file_context", "")

            if not text:
                continue

            # Acknowledge immediately so UI can show typing indicator
            result = await _handle_message(username, text, source, sid, file_ctx)

            await websocket.send_text(json.dumps({
                "role":       "assistant",
                "content":    result["reply"],
                "open":       result["open"],
                "is_open":    result["is_open"],
                "source":     "ai",
                "session_id": result["session_id"],
            }))

    except WebSocketDisconnect:
        pass
    except Exception as e:
        log.error("[ws:%s] %s", username, e)
        try:
            await websocket.send_text(json.dumps({
                "role": "assistant",
                "content": "⚠️ Connection error. Please refresh.",
                "open": None, "is_open": False, "source": "error", "session_id": "",
            }))
        except Exception:
            pass
