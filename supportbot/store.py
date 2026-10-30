"""SQLite log of conversations, unanswered questions and handoffs (the admin's insight data)."""
from __future__ import annotations

import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY, conversation_id TEXT, question TEXT, answer TEXT,
    answered INTEGER, sources TEXT, created_at TEXT);
CREATE TABLE IF NOT EXISTS handoffs (
    id INTEGER PRIMARY KEY, conversation_id TEXT, question TEXT, contact TEXT, created_at TEXT);
"""


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Store:
    def __init__(self, path: Path | str = ":memory:"):
        if path != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(path), check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.lock = threading.Lock()
        with self.lock:
            self.conn.executescript(SCHEMA)

    def log_message(self, conversation_id: str, question: str, answer: str, answered: bool, sources: list[str]) -> None:
        with self.lock, self.conn:
            self.conn.execute(
                "INSERT INTO messages (conversation_id, question, answer, answered, sources, created_at) VALUES (?,?,?,?,?,?)",
                (conversation_id, question, answer, int(answered), ", ".join(sources), now()))

    def log_handoff(self, conversation_id: str, question: str, contact: str = "") -> int:
        with self.lock, self.conn:
            cur = self.conn.execute(
                "INSERT INTO handoffs (conversation_id, question, contact, created_at) VALUES (?,?,?,?)",
                (conversation_id, question, contact, now()))
            return cur.lastrowid

    def set_handoff_contact(self, conversation_id: str, contact: str) -> bool:
        with self.lock, self.conn:
            cur = self.conn.execute(
                "UPDATE handoffs SET contact=? WHERE id=(SELECT MAX(id) FROM handoffs WHERE conversation_id=?)",
                (contact, conversation_id))
            return cur.rowcount > 0

    def knowledge_gaps(self, limit: int = 20) -> list[dict]:
        """Unanswered questions, most frequent first: tells the owner what to add to the docs."""
        rows = self.conn.execute(
            "SELECT lower(trim(question)) AS q, COUNT(*) AS times, MAX(created_at) AS last_asked "
            "FROM messages WHERE answered=0 GROUP BY q ORDER BY times DESC, last_asked DESC LIMIT ?", (limit,))
        return [dict(r) for r in rows]

    def stats(self) -> dict:
        row = self.conn.execute(
            "SELECT COUNT(*) AS total, COALESCE(SUM(answered),0) AS answered, "
            "COUNT(DISTINCT conversation_id) AS conversations FROM messages").fetchone()
        handoffs = self.conn.execute("SELECT COUNT(*) FROM handoffs").fetchone()[0]
        total = row["total"]
        return {"questions": total, "answered": row["answered"], "conversations": row["conversations"],
                "handoffs": handoffs, "answer_rate": round(row["answered"] / total, 3) if total else None}
