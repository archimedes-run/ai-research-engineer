import json
import logging
import sqlite3
import threading
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional


logger = logging.getLogger(__name__)

_lock = threading.Lock()

_DB_PATH: Optional[Path] = None


def _conn() -> sqlite3.Connection:
    assert _DB_PATH is not None, "RunStore.init() must be called first"
    con = sqlite3.connect(str(_DB_PATH), check_same_thread=False)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA foreign_keys=ON")
    return con


_SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
  session_id    TEXT PRIMARY KEY,
  display_id    TEXT,
  user_id       TEXT,
  title         TEXT,
  topic         TEXT,
  status        TEXT,
  agent_type    TEXT,
  domain        TEXT,
  research_mode TEXT,
  template      TEXT,
  hitl_enabled  INTEGER DEFAULT 0,
  current_stage TEXT,
  working_dir   TEXT,
  files_created TEXT DEFAULT '[]',
  started_at    TEXT,
  completed_at  TEXT,
  duration      REAL,
  created_at    TEXT,
  updated_at    TEXT
);

CREATE TABLE IF NOT EXISTS session_events (
  id         INTEGER PRIMARY KEY AUTOINCREMENT,
  session_id TEXT NOT NULL,
  seq        INTEGER NOT NULL,
  type       TEXT,
  payload    TEXT NOT NULL,
  created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_events_session_seq ON session_events(session_id, seq);

CREATE TABLE IF NOT EXISTS submissions (
  id           TEXT PRIMARY KEY,
  payload      TEXT NOT NULL,
  submitted_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT);

CREATE TABLE IF NOT EXISTS run_checkpoints (
  session_id TEXT NOT NULL,
  stage_key  TEXT NOT NULL,
  state_json TEXT NOT NULL,
  created_at TEXT NOT NULL,
  PRIMARY KEY (session_id, stage_key)
);

CREATE TABLE IF NOT EXISTS hitl_requests (
  request_id  TEXT PRIMARY KEY,
  session_id  TEXT NOT NULL,
  stage_key   TEXT NOT NULL,
  question    TEXT NOT NULL,
  context_md  TEXT,
  options     TEXT,
  status      TEXT DEFAULT 'pending',
  answer      TEXT,
  created_at  TEXT,
  answered_at TEXT
);

CREATE TABLE IF NOT EXISTS usage (
  id                  TEXT PRIMARY KEY,
  session_id          TEXT NOT NULL,
  seq                 INTEGER NOT NULL,
  engine              TEXT,
  model               TEXT,
  input_tokens        INTEGER NOT NULL DEFAULT 0,
  cached_input_tokens INTEGER NOT NULL DEFAULT 0,
  output_tokens       INTEGER NOT NULL DEFAULT 0,
  cost_usd            REAL    NOT NULL DEFAULT 0.0,
  created_at          TEXT    NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_usage_session ON usage(session_id);
"""

# Columns we write directly; any extra keys in a session dict are stored as JSON
_SESSION_COLUMNS = {
    "session_id",
    "display_id",
    "user_id",
    "title",
    "topic",
    "status",
    "agent_type",
    "domain",
    "research_mode",
    "template",
    "hitl_enabled",
    "current_stage",
    "working_dir",
    "files_created",
    "started_at",
    "completed_at",
    "duration",
    "created_at",
    "updated_at",
}


class RunStore:
    DATA_DIR = Path(".data")
    DB_PATH = DATA_DIR / "pipeline.db"

    # Legacy paths (JSON era) — kept so migration can read them
    _SESSIONS_DIR = DATA_DIR / "sessions"
    _SUBMISSIONS_FILE = DATA_DIR / "submissions.json"
    _COUNTER_FILE = DATA_DIR / "counter.json"

    @classmethod
    def init(cls, db_path: Optional[Path] = None) -> None:
        global _DB_PATH
        _DB_PATH = db_path or cls.DB_PATH
        _DB_PATH.parent.mkdir(parents=True, exist_ok=True)

        with _lock:
            con = _conn()
            con.executescript(_SCHEMA)
            con.commit()
            con.close()

        cls._maybe_migrate()

    # ------------------------------------------------------------------
    # Display ID counter
    # ------------------------------------------------------------------

    @classmethod
    def next_display_id(cls) -> str:
        with _lock:
            con = _conn()
            try:
                row = con.execute("SELECT value FROM meta WHERE key='display_counter'").fetchone()
                count = int(row["value"]) + 1 if row else 1
                con.execute(
                    "INSERT OR REPLACE INTO meta(key, value) VALUES ('display_counter', ?)",
                    (str(count),),
                )
                con.commit()
            finally:
                con.close()
        return f"ARC-{datetime.now().year}-{count:03d}"

    # ------------------------------------------------------------------
    # Submissions
    # ------------------------------------------------------------------

    @classmethod
    def save_submission(cls, data: Dict) -> Dict:
        data = dict(data)
        data["id"] = str(uuid.uuid4())
        data["submitted_at"] = datetime.now().isoformat()
        with _lock:
            con = _conn()
            try:
                con.execute(
                    "INSERT INTO submissions(id, payload, submitted_at) VALUES (?, ?, ?)",
                    (data["id"], json.dumps(data), data["submitted_at"]),
                )
                con.commit()
            finally:
                con.close()
        return data

    # ------------------------------------------------------------------
    # Sessions
    # ------------------------------------------------------------------

    @classmethod
    def _row_to_session(cls, row: sqlite3.Row) -> Dict:
        d = dict(row)
        for col in ("files_created",):
            if isinstance(d.get(col), str):
                try:
                    d[col] = json.loads(d[col])
                except (json.JSONDecodeError, TypeError):
                    d[col] = []
        return d

    @classmethod
    def save_session(cls, session: Dict) -> None:
        now = datetime.now().isoformat()
        s = {k: v for k, v in session.items() if k in _SESSION_COLUMNS and k != "events"}
        s.setdefault("created_at", now)
        s["updated_at"] = now
        if isinstance(s.get("files_created"), list):
            s["files_created"] = json.dumps(s["files_created"])

        cols = list(s.keys())
        placeholders = ", ".join("?" * len(cols))
        col_str = ", ".join(cols)
        with _lock:
            con = _conn()
            try:
                con.execute(
                    f"INSERT OR REPLACE INTO sessions({col_str}) VALUES ({placeholders})",
                    [s[c] for c in cols],
                )
                con.commit()
            finally:
                con.close()

    @classmethod
    def get_session(cls, session_id: str) -> Optional[Dict]:
        con = _conn()
        try:
            row = con.execute("SELECT * FROM sessions WHERE session_id = ?", (session_id,)).fetchone()
        finally:
            con.close()
        if not row:
            return None
        result = cls._row_to_session(row)
        # Attach ordered event payloads so existing stream-replay code works unchanged
        result["events"] = cls.get_events(session_id, after_seq=0)
        return result

    @classmethod
    def update_session(cls, session_id: str, updates: Dict) -> None:
        now = datetime.now().isoformat()
        filtered = {k: v for k, v in updates.items() if k in _SESSION_COLUMNS and k != "events"}
        filtered["updated_at"] = now
        if isinstance(filtered.get("files_created"), list):
            filtered["files_created"] = json.dumps(filtered["files_created"])

        if not filtered:
            return
        set_clause = ", ".join(f"{k} = ?" for k in filtered)
        vals = list(filtered.values()) + [session_id]
        with _lock:
            con = _conn()
            try:
                con.execute(f"UPDATE sessions SET {set_clause} WHERE session_id = ?", vals)
                con.commit()
            finally:
                con.close()

    @classmethod
    def list_sessions(cls) -> List[Dict]:
        con = _conn()
        try:
            rows = con.execute("SELECT * FROM sessions ORDER BY updated_at DESC").fetchall()
        finally:
            con.close()
        return [cls._row_to_session(r) for r in rows]

    # ------------------------------------------------------------------
    # Events
    # ------------------------------------------------------------------

    @classmethod
    def append_event(cls, session_id: str, payload: Dict) -> int:
        now = datetime.now().isoformat()
        event_type = payload.get("type", "")
        with _lock:
            con = _conn()
            try:
                row = con.execute(
                    "SELECT COALESCE(MAX(seq), 0) as max_seq FROM session_events WHERE session_id = ?",
                    (session_id,),
                ).fetchone()
                seq = row["max_seq"] + 1
                con.execute(
                    "INSERT INTO session_events(session_id, seq, type, payload, created_at) VALUES (?, ?, ?, ?, ?)",
                    (session_id, seq, event_type, json.dumps(payload), now),
                )
                con.commit()
            finally:
                con.close()
        return seq

    @classmethod
    def get_events(cls, session_id: str, after_seq: int = 0) -> List[Dict]:
        con = _conn()
        try:
            rows = con.execute(
                "SELECT seq, payload FROM session_events WHERE session_id = ? AND seq > ? ORDER BY seq",
                (session_id, after_seq),
            ).fetchall()
        finally:
            con.close()
        result = []
        for row in rows:
            try:
                ev = json.loads(row["payload"])
                ev["seq"] = row["seq"]
                result.append(ev)
            except (json.JSONDecodeError, TypeError):
                pass
        return result

    # ------------------------------------------------------------------
    # Usage accounting
    # ------------------------------------------------------------------

    @classmethod
    def add_usage(
        cls,
        session_id: str,
        seq: int,
        input_tokens: int,
        output_tokens: int,
        cached_input_tokens: int = 0,
        model: Optional[str] = None,
        engine: Optional[str] = None,
        cost_usd: float = 0.0,
    ) -> None:
        now = datetime.now().isoformat()
        row_id = str(uuid.uuid4())
        with _lock:
            con = _conn()
            try:
                con.execute(
                    """
                    INSERT INTO usage(id, session_id, seq, engine, model,
                                      input_tokens, cached_input_tokens,
                                      output_tokens, cost_usd, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (row_id, session_id, seq, engine, model,
                     input_tokens, cached_input_tokens,
                     output_tokens, cost_usd, now),
                )
                con.commit()
            finally:
                con.close()

    @classmethod
    def get_usage(cls, session_id: str) -> Dict:
        con = _conn()
        try:
            rows = con.execute(
                """
                SELECT model, engine,
                       SUM(input_tokens)        AS input_tokens,
                       SUM(cached_input_tokens) AS cached_input_tokens,
                       SUM(output_tokens)       AS output_tokens,
                       SUM(cost_usd)            AS cost_usd
                FROM usage
                WHERE session_id = ?
                GROUP BY model, engine
                ORDER BY model
                """,
                (session_id,),
            ).fetchall()
            totals_row = con.execute(
                """
                SELECT SUM(input_tokens)        AS input_tokens,
                       SUM(cached_input_tokens) AS cached_input_tokens,
                       SUM(output_tokens)       AS output_tokens,
                       SUM(cost_usd)            AS cost_usd
                FROM usage
                WHERE session_id = ?
                """,
                (session_id,),
            ).fetchone()
        finally:
            con.close()

        by_model = [dict(r) for r in rows]
        totals = dict(totals_row) if totals_row else {}
        # Replace None sums (no rows) with 0
        for key in ("input_tokens", "cached_input_tokens", "output_tokens", "cost_usd"):
            if totals.get(key) is None:
                totals[key] = 0

        return {"totals": totals, "by_model": by_model}

    # ------------------------------------------------------------------
    # One-time JSON migration
    # ------------------------------------------------------------------

    @classmethod
    def _maybe_migrate(cls) -> None:
        con = _conn()
        try:
            count = con.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
        finally:
            con.close()

        if count > 0:
            return  # already migrated or populated — skip

        sessions_dir = cls._SESSIONS_DIR
        if not sessions_dir.exists() or not any(sessions_dir.glob("*.json")):
            return

        imported = 0
        for path in sessions_dir.glob("*.json"):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                events = data.pop("events", [])
                cls.save_session(data)
                for i, ev in enumerate(events, start=1):
                    now = datetime.now().isoformat()
                    with _lock:
                        con = _conn()
                        try:
                            con.execute(
                                "INSERT INTO session_events(session_id, seq, type, payload, created_at) VALUES (?, ?, ?, ?, ?)",
                                (data["session_id"], i, ev.get("type", ""), json.dumps(ev), now),
                            )
                            con.commit()
                        finally:
                            con.close()
                imported += 1
            except Exception as exc:
                logger.warning("Migration: skipped %s — %s", path.name, exc)

        # Migrate counter
        counter_file = cls._COUNTER_FILE
        if counter_file.exists():
            try:
                cdata = json.loads(counter_file.read_text(encoding="utf-8"))
                count_val = cdata.get("count", 0)
                with _lock:
                    con = _conn()
                    try:
                        con.execute(
                            "INSERT OR IGNORE INTO meta(key, value) VALUES ('display_counter', ?)",
                            (str(count_val),),
                        )
                        con.commit()
                    finally:
                        con.close()
            except Exception as exc:
                logger.warning("Migration: could not read counter.json — %s", exc)

        # Migrate submissions
        sub_file = cls._SUBMISSIONS_FILE
        if sub_file.exists():
            try:
                subs = json.loads(sub_file.read_text(encoding="utf-8"))
                for sub in subs:
                    sub_id = sub.get("id", str(uuid.uuid4()))
                    submitted_at = sub.get("submitted_at", datetime.now().isoformat())
                    with _lock:
                        con = _conn()
                        try:
                            con.execute(
                                "INSERT OR IGNORE INTO submissions(id, payload, submitted_at) VALUES (?, ?, ?)",
                                (sub_id, json.dumps(sub), submitted_at),
                            )
                            con.commit()
                        finally:
                            con.close()
            except Exception as exc:
                logger.warning("Migration: could not read submissions.json — %s", exc)

        logger.info("RunStore migration: imported %d session(s) from JSON.", imported)
