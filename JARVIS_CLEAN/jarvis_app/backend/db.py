"""
db.py — SQLite database for JARVIS
Architecture: one shared DB + per-user tables created on first login/register.

Global tables  : users, chat_history (legacy), notes
Per-user tables: sessions_<user>, messages_<user>
"""
import sqlite3, re, os

DB_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "jarvis.db"))


def _safe(username: str) -> str:
    """Sanitise username so it is safe as a table-name suffix."""
    return re.sub(r"[^a-zA-Z0-9_]", "_", username).lower()


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    conn = get_conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            username       TEXT UNIQUE NOT NULL,
            password_hash  TEXT NOT NULL,
            salt           TEXT NOT NULL,
            created_at     TEXT DEFAULT (datetime('now')),
            last_login     TEXT,
            total_messages INTEGER DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS chat_history (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            username  TEXT NOT NULL DEFAULT 'default',
            role      TEXT NOT NULL,
            content   TEXT NOT NULL,
            source    TEXT NOT NULL DEFAULT 'text',
            timestamp TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS notes (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            username   TEXT NOT NULL,
            title      TEXT NOT NULL DEFAULT '',
            content    TEXT NOT NULL,
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE INDEX IF NOT EXISTS idx_notes_user ON notes(username);
    """)
    conn.commit()
    # Ensure every existing user has per-user tables
    for row in conn.execute("SELECT username FROM users").fetchall():
        _create_user_tables(conn, row["username"])
    conn.close()
    print("✅ Database initialised")


def _create_user_tables(conn, username: str):
    u = _safe(username)
    conn.executescript(f"""
        CREATE TABLE IF NOT EXISTS sessions_{u} (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT UNIQUE NOT NULL,
            title      TEXT NOT NULL DEFAULT 'New Chat',
            msg_count  INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS messages_{u} (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            role       TEXT NOT NULL,
            content    TEXT NOT NULL,
            source     TEXT NOT NULL DEFAULT 'text',
            timestamp  TEXT NOT NULL DEFAULT (datetime('now'))
        );
        CREATE INDEX IF NOT EXISTS idx_msg_{u}_sid ON messages_{u}(session_id);
    """)
    conn.commit()


def provision_user(username: str):
    """Ensure per-user tables exist and update last_login."""
    conn = get_conn()
    _create_user_tables(conn, username)
    conn.execute("UPDATE users SET last_login=datetime('now') WHERE username=?", (username,))
    conn.commit()
    conn.close()


# ── User info ─────────────────────────────────────────────────────────────────

def get_user_info(username: str) -> dict:
    conn = get_conn()
    row = conn.execute(
        "SELECT username, created_at, last_login, total_messages FROM users WHERE username=?",
        (username,)
    ).fetchone()
    if not row:
        conn.close()
        return {}
    u = _safe(username)
    try:
        sc = conn.execute(f"SELECT COUNT(*) as n FROM sessions_{u}").fetchone()["n"]
    except Exception:
        sc = 0
    try:
        mc = conn.execute(f"SELECT COUNT(*) as n FROM messages_{u}").fetchone()["n"]
    except Exception:
        mc = row["total_messages"] or 0
    conn.close()
    return {
        "username":       row["username"],
        "created_at":     row["created_at"],
        "last_login":     row["last_login"],
        "total_messages": mc,
        "session_count":  sc,
    }


# ── Session helpers ───────────────────────────────────────────────────────────

MAX_SESSIONS = 10


def create_session(username: str, session_id: str, title: str = "New Chat"):
    conn = get_conn()
    u = _safe(username)
    rows = conn.execute(
        f"SELECT session_id FROM sessions_{u} ORDER BY updated_at ASC"
    ).fetchall()
    while len(rows) >= MAX_SESSIONS:
        old = rows[0]["session_id"]
        conn.execute(f"DELETE FROM sessions_{u} WHERE session_id=?", (old,))
        conn.execute(f"DELETE FROM messages_{u} WHERE session_id=?", (old,))
        rows = rows[1:]
    conn.execute(
        f"INSERT OR REPLACE INTO sessions_{u} "
        f"(session_id, title, created_at, updated_at) VALUES (?,?,datetime('now'),datetime('now'))",
        (session_id, title)
    )
    conn.commit()
    conn.close()


def update_session_title(username: str, session_id: str, title: str):
    conn = get_conn()
    u = _safe(username)
    conn.execute(
        f"UPDATE sessions_{u} SET title=?, updated_at=datetime('now') WHERE session_id=?",
        (title, session_id)
    )
    conn.commit()
    conn.close()


def get_sessions(username: str) -> list:
    conn = get_conn()
    u = _safe(username)
    try:
        rows = conn.execute(
            f"SELECT session_id, title, msg_count, created_at, updated_at "
            f"FROM sessions_{u} ORDER BY updated_at DESC"
        ).fetchall()
    except Exception:
        rows = []
    conn.close()
    return [dict(r) for r in rows]


def session_exists(username: str, session_id: str) -> bool:
    conn = get_conn()
    u = _safe(username)
    try:
        row = conn.execute(
            f"SELECT 1 FROM sessions_{u} WHERE session_id=?", (session_id,)
        ).fetchone()
    except Exception:
        row = None
    conn.close()
    return row is not None


def delete_session(username: str, session_id: str):
    conn = get_conn()
    u = _safe(username)
    conn.execute(f"DELETE FROM sessions_{u} WHERE session_id=?", (session_id,))
    conn.execute(f"DELETE FROM messages_{u} WHERE session_id=?", (session_id,))
    conn.commit()
    conn.close()


def delete_all_sessions(username: str):
    conn = get_conn()
    u = _safe(username)
    conn.execute(f"DELETE FROM sessions_{u}")
    conn.execute(f"DELETE FROM messages_{u}")
    conn.commit()
    conn.close()


def save_message(username: str, session_id: str, role: str, content: str, source: str = "text"):
    conn = get_conn()
    u = _safe(username)
    conn.execute(
        f"INSERT INTO messages_{u} (session_id, role, content, source, timestamp) "
        f"VALUES (?,?,?,?,datetime('now'))",
        (session_id, role, content, source)
    )
    conn.execute(
        f"UPDATE sessions_{u} SET updated_at=datetime('now'), msg_count=msg_count+1 WHERE session_id=?",
        (session_id,)
    )
    conn.execute(
        "UPDATE users SET total_messages=total_messages+1 WHERE username=?", (username,)
    )
    conn.commit()
    conn.close()


def load_messages(username: str, session_id: str, limit: int = 100) -> list:
    conn = get_conn()
    u = _safe(username)
    try:
        rows = conn.execute(
            f"SELECT role, content, source, timestamp FROM messages_{u} "
            f"WHERE session_id=? ORDER BY id DESC LIMIT ?",
            (session_id, limit)
        ).fetchall()
    except Exception:
        rows = []
    conn.close()
    return list(reversed([dict(r) for r in rows]))


# ── Legacy helpers ────────────────────────────────────────────────────────────

def save_msg(username, role, content, source="text"):
    conn = get_conn()
    conn.execute(
        "INSERT INTO chat_history (username,role,content,source,timestamp) VALUES (?,?,?,?,datetime('now'))",
        (username, role, content, source)
    )
    conn.commit()
    conn.close()


def load_history(username, limit=100):
    conn = get_conn()
    rows = conn.execute(
        "SELECT role,content,source,timestamp FROM chat_history "
        "WHERE username=? ORDER BY id DESC LIMIT ?",
        (username, limit)
    ).fetchall()
    conn.close()
    return list(reversed([dict(r) for r in rows]))
