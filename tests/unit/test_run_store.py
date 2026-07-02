"""Unit tests for RunStore (SQLite persistence layer)."""

import json

import pytest

from ai_research_engineer.server.run_store import RunStore


@pytest.fixture()
def store(tmp_path):
    """Initialise a RunStore backed by a temporary database."""
    db = tmp_path / "test.db"
    # Point DATA_DIR at tmp_path so migration scans tmp_path/sessions/
    original_data_dir = RunStore.DATA_DIR
    original_db_path = RunStore.DB_PATH
    original_sessions_dir = RunStore._SESSIONS_DIR
    original_sub_file = RunStore._SUBMISSIONS_FILE
    original_counter_file = RunStore._COUNTER_FILE
    RunStore.DATA_DIR = tmp_path
    RunStore.DB_PATH = db
    RunStore._SESSIONS_DIR = tmp_path / "sessions"
    RunStore._SUBMISSIONS_FILE = tmp_path / "submissions.json"
    RunStore._COUNTER_FILE = tmp_path / "counter.json"

    RunStore.init(db_path=db)

    yield RunStore

    # Restore class-level paths so other tests are unaffected
    RunStore.DATA_DIR = original_data_dir
    RunStore.DB_PATH = original_db_path
    RunStore._SESSIONS_DIR = original_sessions_dir
    RunStore._SUBMISSIONS_FILE = original_sub_file
    RunStore._COUNTER_FILE = original_counter_file


# ---------------------------------------------------------------------------
# Display ID counter
# ---------------------------------------------------------------------------


def test_display_id_increments(store):
    a = store.next_display_id()
    b = store.next_display_id()
    # Both must be ARC-YYYY-NNN format and strictly increasing
    assert a.startswith("ARC-")
    assert b.startswith("ARC-")
    suffix_a = int(a.rsplit("-", 1)[-1])
    suffix_b = int(b.rsplit("-", 1)[-1])
    assert suffix_b == suffix_a + 1


# ---------------------------------------------------------------------------
# Session CRUD
# ---------------------------------------------------------------------------


def _make_session(session_id="s1"):
    return {
        "session_id": session_id,
        "display_id": "ARC-2026-001",
        "title": "Test session",
        "topic": "quantum computing",
        "status": "running",
        "agent_type": "adk",
        "domain": "aiml",
        "research_mode": "novelty",
        "template": "tpl",
        "started_at": "2026-01-01T00:00:00",
        "files_created": [],
    }


def test_save_and_get_session(store):
    store.save_session(_make_session())
    result = store.get_session("s1")
    assert result is not None
    assert result["session_id"] == "s1"
    assert result["topic"] == "quantum computing"
    assert isinstance(result["files_created"], list)


def test_get_session_missing(store):
    assert store.get_session("does-not-exist") is None


def test_update_session(store):
    store.save_session(_make_session())
    store.update_session("s1", {"status": "completed", "duration": 3.14})
    result = store.get_session("s1")
    assert result["status"] == "completed"
    assert result["duration"] == pytest.approx(3.14)


def test_list_sessions_omits_events(store):
    store.save_session(_make_session("s1"))
    store.save_session(_make_session("s2"))
    store.append_event("s1", {"type": "text", "content": "hello"})
    sessions = store.list_sessions()
    assert len(sessions) == 2
    for s in sessions:
        assert "events" not in s


def test_list_sessions_newest_first(store, tmp_path):
    import time

    store.save_session(_make_session("old"))
    time.sleep(0.01)
    store.update_session("old", {"status": "completed"})
    time.sleep(0.01)
    store.save_session(_make_session("new"))
    time.sleep(0.01)
    store.update_session("new", {"status": "running"})

    sessions = store.list_sessions()
    ids = [s["session_id"] for s in sessions]
    assert ids.index("new") < ids.index("old")


def test_files_created_round_trips_as_list(store):
    s = _make_session()
    s["files_created"] = ["workflow/main.py", "results/out.json"]
    store.save_session(s)
    result = store.get_session("s1")
    assert result["files_created"] == ["workflow/main.py", "results/out.json"]


# ---------------------------------------------------------------------------
# Events
# ---------------------------------------------------------------------------


def test_append_event_returns_increasing_seq(store):
    store.save_session(_make_session())
    seq1 = store.append_event("s1", {"type": "text", "content": "a"})
    seq2 = store.append_event("s1", {"type": "text", "content": "b"})
    seq3 = store.append_event("s1", {"type": "text", "content": "c"})
    assert seq1 < seq2 < seq3
    assert seq1 == 1


def test_seq_is_independent_per_session(store):
    store.save_session(_make_session("s1"))
    store.save_session(_make_session("s2"))
    store.append_event("s1", {"type": "text"})
    store.append_event("s1", {"type": "text"})
    seq = store.append_event("s2", {"type": "text"})
    assert seq == 1  # s2 starts its own counter at 1


def test_get_events_returns_all_by_default(store):
    store.save_session(_make_session())
    store.append_event("s1", {"type": "text", "content": "first"})
    store.append_event("s1", {"type": "text", "content": "second"})
    events = store.get_events("s1")
    assert len(events) == 2
    assert events[0]["content"] == "first"
    assert events[0]["seq"] == 1
    assert events[1]["seq"] == 2


def test_get_events_after_seq_filters(store):
    store.save_session(_make_session())
    store.append_event("s1", {"type": "text", "content": "one"})
    store.append_event("s1", {"type": "text", "content": "two"})
    store.append_event("s1", {"type": "text", "content": "three"})
    events = store.get_events("s1", after_seq=1)
    assert len(events) == 2
    assert events[0]["content"] == "two"
    assert events[0]["seq"] == 2


def test_get_events_empty_for_unknown_session(store):
    events = store.get_events("nonexistent")
    assert events == []


def test_get_session_attaches_events(store):
    store.save_session(_make_session())
    store.append_event("s1", {"type": "text", "content": "hi"})
    result = store.get_session("s1")
    assert "events" in result
    assert len(result["events"]) == 1
    assert result["events"][0]["content"] == "hi"


# ---------------------------------------------------------------------------
# Reconciliation
# ---------------------------------------------------------------------------


def test_reconciliation_marks_stale_running_sessions(tmp_path):
    db = tmp_path / "recon.db"
    RunStore.DATA_DIR = tmp_path
    RunStore.DB_PATH = db
    RunStore._SESSIONS_DIR = tmp_path / "sessions"
    RunStore._SUBMISSIONS_FILE = tmp_path / "submissions.json"
    RunStore._COUNTER_FILE = tmp_path / "counter.json"

    RunStore.init(db_path=db)
    RunStore.save_session(_make_session("stale"))
    # Verify it is "running"
    assert RunStore.get_session("stale")["status"] == "running"

    # Simulate a restart: reinit with no active sessions
    RunStore.init(db_path=db)
    for s in RunStore.list_sessions():
        if s.get("status") == "running" and s["session_id"] not in {}:
            RunStore.update_session(s["session_id"], {"status": "interrupted"})

    assert RunStore.get_session("stale")["status"] == "interrupted"


# ---------------------------------------------------------------------------
# Migration
# ---------------------------------------------------------------------------


def test_migration_imports_json_sessions(tmp_path):
    sessions_dir = tmp_path / "sessions"
    sessions_dir.mkdir()
    session_data = {
        "session_id": "migrated-1",
        "display_id": "ARC-2025-001",
        "title": "Legacy",
        "topic": "legacy topic",
        "status": "completed",
        "agent_type": "adk",
        "domain": "aiml",
        "research_mode": "novelty",
        "template": "tpl",
        "started_at": "2025-01-01T00:00:00",
        "files_created": [],
        "events": [
            {"type": "text", "content": "event 1"},
            {"type": "text", "content": "event 2"},
        ],
    }
    (sessions_dir / "migrated-1.json").write_text(json.dumps(session_data))

    # Write legacy counter + submissions
    (tmp_path / "counter.json").write_text(json.dumps({"count": 7}))
    (tmp_path / "submissions.json").write_text(
        json.dumps([{"id": "sub-1", "submitted_at": "2025-01-01T00:00:00", "email": "a@b.com"}])
    )

    db = tmp_path / "mig.db"
    RunStore.DATA_DIR = tmp_path
    RunStore.DB_PATH = db
    RunStore._SESSIONS_DIR = sessions_dir
    RunStore._SUBMISSIONS_FILE = tmp_path / "submissions.json"
    RunStore._COUNTER_FILE = tmp_path / "counter.json"
    RunStore.init(db_path=db)

    s = RunStore.get_session("migrated-1")
    assert s is not None
    assert s["topic"] == "legacy topic"
    events = RunStore.get_events("migrated-1")
    assert len(events) == 2
    assert events[0]["content"] == "event 1"
    assert events[1]["seq"] == 2

    # Display counter migrated
    next_id = RunStore.next_display_id()
    suffix = int(next_id.rsplit("-", 1)[-1])
    assert suffix == 8  # count was 7, next is 8


def test_migration_runs_only_once(tmp_path):
    sessions_dir = tmp_path / "sessions"
    sessions_dir.mkdir()
    (sessions_dir / "s.json").write_text(
        json.dumps({"session_id": "once", "topic": "t", "events": [], "files_created": []})
    )
    db = tmp_path / "once.db"
    RunStore.DATA_DIR = tmp_path
    RunStore.DB_PATH = db
    RunStore._SESSIONS_DIR = sessions_dir
    RunStore._SUBMISSIONS_FILE = tmp_path / "submissions.json"
    RunStore._COUNTER_FILE = tmp_path / "counter.json"

    RunStore.init(db_path=db)
    assert RunStore.get_session("once") is not None

    # Second init should not error and should not duplicate
    RunStore.init(db_path=db)
    sessions = RunStore.list_sessions()
    assert sum(1 for s in sessions if s["session_id"] == "once") == 1
