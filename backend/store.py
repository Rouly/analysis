"""本地 SQLite 存储：我的声纹向量、会话文字稿、复盘结果。
只存文字与向量，绝不存音频文件。"""
import sqlite3
import json
import os
import time

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "sales_replay.db")


def _conn():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    c = sqlite3.connect(DB_PATH)
    c.execute("""CREATE TABLE IF NOT EXISTS voiceprint(
        name TEXT PRIMARY KEY, vector TEXT, updated REAL)""")
    c.execute("""CREATE TABLE IF NOT EXISTS sessions(
        id INTEGER PRIMARY KEY AUTOINCREMENT, created REAL,
        title TEXT, dialogue TEXT, analysis TEXT)""")
    return c


# ── 声纹 ───────────────────────────────────────────
def save_voiceprint(vector, name="我"):
    c = _conn()
    c.execute("REPLACE INTO voiceprint(name, vector, updated) VALUES(?,?,?)",
              (name, json.dumps([float(x) for x in vector]), time.time()))
    c.commit(); c.close()


def load_voiceprint(name="我"):
    c = _conn()
    row = c.execute("SELECT vector FROM voiceprint WHERE name=?", (name,)).fetchone()
    c.close()
    return json.loads(row[0]) if row else None


def has_voiceprint(name="我"):
    return load_voiceprint(name) is not None


def delete_voiceprint(name="我"):
    c = _conn()
    c.execute("DELETE FROM voiceprint WHERE name=?", (name,))
    c.commit(); c.close()


# ── 会话 ───────────────────────────────────────────
def save_session(dialogue, analysis=None, title=None):
    c = _conn()
    title = title or time.strftime("%Y-%m-%d %H:%M", time.localtime())
    cur = c.execute("INSERT INTO sessions(created, title, dialogue, analysis) VALUES(?,?,?,?)",
                    (time.time(), title,
                     json.dumps(dialogue, ensure_ascii=False),
                     json.dumps(analysis, ensure_ascii=False) if analysis else None))
    c.commit(); sid = cur.lastrowid; c.close()
    return sid


def list_sessions(limit=50):
    c = _conn()
    rows = c.execute("SELECT id, created, title FROM sessions ORDER BY created DESC LIMIT ?",
                     (limit,)).fetchall()
    c.close()
    return [{"id": r[0], "created": r[1], "title": r[2]} for r in rows]


def get_session(sid):
    c = _conn()
    r = c.execute("SELECT id, created, title, dialogue, analysis FROM sessions WHERE id=?",
                  (sid,)).fetchone()
    c.close()
    if not r:
        return None
    return {"id": r[0], "created": r[1], "title": r[2],
            "dialogue": json.loads(r[3]) if r[3] else [],
            "analysis": json.loads(r[4]) if r[4] else None}


def clear_all():
    c = _conn()
    c.execute("DELETE FROM sessions"); c.execute("DELETE FROM voiceprint")
    c.commit(); c.close()
