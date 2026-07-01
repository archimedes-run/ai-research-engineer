import json
import os
import threading
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional


_lock = threading.Lock()


def _atomic_write(path: Path, data: str) -> None:
    """Write *data* to *path* atomically via a sibling temp file."""
    tmp = path.with_suffix(".tmp")
    tmp.write_text(data, encoding="utf-8")
    os.replace(tmp, path)


class Storage:
    DATA_DIR = Path(".data")
    SESSIONS_DIR = DATA_DIR / "sessions"
    SUBMISSIONS_FILE = DATA_DIR / "submissions.json"
    COUNTER_FILE = DATA_DIR / "counter.json"

    @classmethod
    def init(cls):
        cls.DATA_DIR.mkdir(exist_ok=True)
        cls.SESSIONS_DIR.mkdir(exist_ok=True)
        if not cls.SUBMISSIONS_FILE.exists():
            cls.SUBMISSIONS_FILE.write_text("[]")
        if not cls.COUNTER_FILE.exists():
            cls.COUNTER_FILE.write_text('{"count": 0}')

    @classmethod
    def next_display_id(cls) -> str:
        with _lock:
            data = json.loads(cls.COUNTER_FILE.read_text())
            data["count"] += 1
            _atomic_write(cls.COUNTER_FILE, json.dumps(data))
        return f"ARC-{datetime.now().year}-{data['count']:03d}"

    @classmethod
    def save_submission(cls, data: Dict) -> Dict:
        data["id"] = str(uuid.uuid4())
        data["submitted_at"] = datetime.now().isoformat()
        with _lock:
            submissions = json.loads(cls.SUBMISSIONS_FILE.read_text())
            submissions.append(data)
            _atomic_write(cls.SUBMISSIONS_FILE, json.dumps(submissions, indent=2))
        return data

    @classmethod
    def save_session(cls, session: Dict) -> None:
        path = cls.SESSIONS_DIR / f"{session['session_id']}.json"
        with _lock:
            _atomic_write(path, json.dumps(session, indent=2))

    @classmethod
    def get_session(cls, session_id: str) -> Optional[Dict]:
        path = cls.SESSIONS_DIR / f"{session_id}.json"
        with _lock:
            if not path.exists():
                return None
            return json.loads(path.read_text())

    @classmethod
    def list_sessions(cls) -> List[Dict]:
        sessions = []
        with _lock:
            paths = sorted(
                cls.SESSIONS_DIR.glob("*.json"),
                key=lambda p: p.stat().st_mtime,
                reverse=True,
            )
        for path in paths:
            try:
                with _lock:
                    data = json.loads(path.read_text())
                # Strip heavy events list from index
                sessions.append({k: v for k, v in data.items() if k != "events"})
            except Exception:
                pass
        return sessions

    @classmethod
    def update_session(cls, session_id: str, updates: Dict) -> None:
        with _lock:
            path = cls.SESSIONS_DIR / f"{session_id}.json"
            if not path.exists():
                return
            session = json.loads(path.read_text())
            session.update(updates)
            _atomic_write(path, json.dumps(session, indent=2))
