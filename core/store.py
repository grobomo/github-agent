"""SQLite-backed event store with full-text search.

Source-agnostic: stores events from GitHub, Teams, or any future source.
Schema compatible with teams-agent's MessageStore for cross-agent queries.
"""

import sqlite3
import json
import os
from pathlib import Path
from typing import Optional


DEFAULT_DB_PATH = str(Path(__file__).parent.parent / 'data' / 'events.db')

SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL,
    account TEXT NOT NULL,
    channel TEXT NOT NULL,
    event_id TEXT NOT NULL UNIQUE,
    event_type TEXT NOT NULL,
    actor TEXT NOT NULL,
    title TEXT NOT NULL DEFAULT '',
    body TEXT NOT NULL DEFAULT '',
    metadata TEXT,
    timestamp TEXT NOT NULL,
    created_at TEXT DEFAULT (datetime('now')),
    processed INTEGER NOT NULL DEFAULT 0,
    action_taken TEXT
);

CREATE INDEX IF NOT EXISTS idx_events_source ON events(source);
CREATE INDEX IF NOT EXISTS idx_events_account ON events(account);
CREATE INDEX IF NOT EXISTS idx_events_channel ON events(channel);
CREATE INDEX IF NOT EXISTS idx_events_timestamp ON events(timestamp);
CREATE INDEX IF NOT EXISTS idx_events_processed ON events(processed);
CREATE INDEX IF NOT EXISTS idx_events_type ON events(event_type);

CREATE VIRTUAL TABLE IF NOT EXISTS events_fts USING fts5(
    title, body, actor, channel,
    content=events,
    content_rowid=id
);

CREATE TRIGGER IF NOT EXISTS events_ai AFTER INSERT ON events BEGIN
    INSERT INTO events_fts(rowid, title, body, actor, channel)
    VALUES (new.id, new.title, new.body, new.actor, new.channel);
END;

CREATE TRIGGER IF NOT EXISTS events_ad AFTER DELETE ON events BEGIN
    INSERT INTO events_fts(events_fts, rowid, title, body, actor, channel)
    VALUES ('delete', old.id, old.title, old.body, old.actor, old.channel);
END;
"""


class EventStore:
    """Source-agnostic event store with FTS."""

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or DEFAULT_DB_PATH
        if self.db_path != ':memory:':
            os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.executescript(SCHEMA)

    def insert(self, source: str, account: str, channel: str, event_id: str,
               event_type: str, actor: str, title: str = '', body: str = '',
               metadata: Optional[dict] = None, timestamp: str = '') -> bool:
        """Insert an event. Returns True if new, False if duplicate."""
        try:
            self.conn.execute(
                """INSERT INTO events
                   (source, account, channel, event_id, event_type, actor,
                    title, body, metadata, timestamp)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (source, account, channel, event_id, event_type, actor,
                 title, body[:4000], json.dumps(metadata) if metadata else None,
                 timestamp),
            )
            self.conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False

    def get_recent(self, channel: Optional[str] = None,
                   source: Optional[str] = None,
                   account: Optional[str] = None,
                   limit: int = 50) -> list[dict]:
        """Get recent events with optional filters."""
        conditions, params = [], []
        if channel:
            conditions.append("channel = ?")
            params.append(channel)
        if source:
            conditions.append("source = ?")
            params.append(source)
        if account:
            conditions.append("account = ?")
            params.append(account)
        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        rows = self.conn.execute(
            f"SELECT * FROM events {where} ORDER BY timestamp DESC LIMIT ?",
            params + [limit],
        ).fetchall()
        return [dict(r) for r in rows]

    def get_unprocessed(self, limit: int = 100) -> list[dict]:
        """Get events not yet analyzed by the brain."""
        rows = self.conn.execute(
            "SELECT * FROM events WHERE processed = 0 "
            "ORDER BY timestamp ASC LIMIT ?",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]

    def mark_processed(self, event_id: str,
                       action_taken: Optional[dict] = None):
        """Mark an event as processed."""
        self.conn.execute(
            "UPDATE events SET processed = 1, action_taken = ? "
            "WHERE event_id = ?",
            (json.dumps(action_taken) if action_taken else None, event_id),
        )
        self.conn.commit()

    def mark_actioned(self, event_id: str, action_taken: dict):
        """Mark an event as actioned (response sent, task dispatched, etc.)."""
        self.conn.execute(
            "UPDATE events SET processed = 2, action_taken = ? "
            "WHERE event_id = ?",
            (json.dumps(action_taken), event_id),
        )
        self.conn.commit()

    def search(self, query: str, limit: int = 20) -> list[dict]:
        """Full-text search across all events."""
        escaped = query.replace('"', '""')
        safe_query = f'"{escaped}"'
        rows = self.conn.execute(
            """SELECT e.* FROM events e
               JOIN events_fts f ON e.id = f.rowid
               WHERE events_fts MATCH ?
               ORDER BY rank LIMIT ?""",
            (safe_query, limit),
        ).fetchall()
        return [dict(r) for r in rows]

    def get_context_window(self, account: Optional[str] = None,
                           hours: int = 24, limit: int = 200) -> list[dict]:
        """Get all recent events for building LLM context."""
        conditions = ["timestamp > datetime('now', ? || ' hours')"]
        params = [f'-{hours}']
        if account:
            conditions.append("account = ?")
            params.append(account)
        where = f"WHERE {' AND '.join(conditions)}"
        rows = self.conn.execute(
            f"SELECT * FROM events {where} ORDER BY timestamp ASC LIMIT ?",
            params + [limit],
        ).fetchall()
        return [dict(r) for r in rows]

    def count(self, source: Optional[str] = None,
              account: Optional[str] = None) -> int:
        conditions, params = [], []
        if source:
            conditions.append("source = ?")
            params.append(source)
        if account:
            conditions.append("account = ?")
            params.append(account)
        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        row = self.conn.execute(
            f"SELECT COUNT(*) FROM events {where}", params
        ).fetchone()
        return row[0]

    def prune(self, max_age_days: int = 90, keep_min: int = 500) -> int:
        """Delete old events, keeping at least keep_min per channel."""
        cursor = self.conn.execute(
            """DELETE FROM events WHERE id IN (
                SELECT e.id FROM events e
                WHERE e.timestamp < datetime('now', ? || ' days')
                AND e.id NOT IN (
                    SELECT id FROM events e2
                    WHERE e2.channel = e.channel
                    ORDER BY e2.timestamp DESC LIMIT ?
                )
            )""",
            (f'-{max_age_days}', keep_min),
        )
        deleted = cursor.rowcount
        if deleted:
            self.conn.commit()
        return deleted

    def close(self):
        self.conn.close()


if __name__ == '__main__':
    store = EventStore()
    print(f"Database: {store.db_path}")
    print(f"Total events: {store.count()}")
    store.close()
