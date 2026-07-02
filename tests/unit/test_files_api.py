"""
Unit tests for the sandboxed file-serving endpoints:
  GET /api/sessions/{id}/files
  GET /api/sessions/{id}/files/{path}
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _init_store(tmp_path: Path):
    from ai_research_engineer.server.run_store import RunStore

    db = tmp_path / "test.db"
    RunStore.init(db_path=db)
    # Point DATA_DIR at tmp_path so working dirs are created under tmp_path/runs/
    RunStore.DATA_DIR = tmp_path
    return RunStore


def _make_session(store, session_id: str = "sess-001") -> str:
    store.save_session(
        {
            "session_id": session_id,
            "status": "running",
            "title": "Test",
            "topic": "test topic",
            "agent_type": "adk",
            "started_at": datetime.now().isoformat(),
        }
    )
    return session_id


@pytest.fixture()
def client(tmp_path):
    from ai_research_engineer.server.app import app
    from ai_research_engineer.server.run_store import RunStore

    _original_data_dir = RunStore.DATA_DIR
    store = _init_store(tmp_path)

    yield TestClient(app, raise_server_exceptions=True), store, tmp_path

    RunStore.DATA_DIR = _original_data_dir


# ---------------------------------------------------------------------------
# Helper: build a fake working dir
# ---------------------------------------------------------------------------


def _make_working_dir(tmp_path: Path, session_id: str) -> Path:
    wd = tmp_path / "runs" / session_id
    wd.mkdir(parents=True, exist_ok=True)
    return wd


# ---------------------------------------------------------------------------
# GET /api/sessions/{id}/files
# ---------------------------------------------------------------------------


class TestFileTree:
    def test_404_when_session_unknown(self, client):
        c, store, tmp_path = client
        r = c.get("/api/sessions/no-such-session/files")
        assert r.status_code == 404

    def test_404_when_working_dir_missing(self, client):
        c, store, tmp_path = client
        sid = _make_session(store, "sess-no-dir")
        # working dir is never created
        r = c.get(f"/api/sessions/{sid}/files")
        assert r.status_code == 404

    def test_returns_file_list(self, client):
        c, store, tmp_path = client
        sid = _make_session(store)
        wd = _make_working_dir(tmp_path, sid)
        (wd / "main.py").write_text("print('hello')")
        (wd / "README.md").write_text("# readme")

        r = c.get(f"/api/sessions/{sid}/files")
        assert r.status_code == 200
        paths = {e["path"] for e in r.json()}
        assert "main.py" in paths
        assert "README.md" in paths

    def test_excludes_git_dir(self, client):
        c, store, tmp_path = client
        sid = _make_session(store, "sess-git")
        wd = _make_working_dir(tmp_path, sid)
        (wd / ".git").mkdir()
        (wd / ".git" / "HEAD").write_text("ref: refs/heads/main")
        (wd / "script.py").write_text("pass")

        r = c.get(f"/api/sessions/{sid}/files")
        assert r.status_code == 200
        paths = {e["path"] for e in r.json()}
        assert not any(".git" in p for p in paths)
        assert "script.py" in paths

    def test_excludes_node_modules(self, client):
        c, store, tmp_path = client
        sid = _make_session(store, "sess-nm")
        wd = _make_working_dir(tmp_path, sid)
        nm = wd / "node_modules" / "lodash"
        nm.mkdir(parents=True)
        (nm / "index.js").write_text("module.exports = {}")
        (wd / "index.ts").write_text("export {}")

        r = c.get(f"/api/sessions/{sid}/files")
        assert r.status_code == 200
        paths = {e["path"] for e in r.json()}
        assert not any("node_modules" in p for p in paths)
        assert "index.ts" in paths

    def test_excludes_pycache(self, client):
        c, store, tmp_path = client
        sid = _make_session(store, "sess-pyc")
        wd = _make_working_dir(tmp_path, sid)
        pc = wd / "__pycache__"
        pc.mkdir()
        (pc / "mod.cpython-311.pyc").write_bytes(b"\x00\x00")
        (wd / "mod.py").write_text("x = 1")

        r = c.get(f"/api/sessions/{sid}/files")
        paths = {e["path"] for e in r.json()}
        assert not any("__pycache__" in p for p in paths)
        assert "mod.py" in paths

    def test_excludes_graphify_out(self, client):
        c, store, tmp_path = client
        sid = _make_session(store, "sess-gph")
        wd = _make_working_dir(tmp_path, sid)
        go = wd / "graphify-out"
        go.mkdir()
        (go / "graph.json").write_text("{}")
        (wd / "agent.py").write_text("pass")

        r = c.get(f"/api/sessions/{sid}/files")
        paths = {e["path"] for e in r.json()}
        assert not any("graphify-out" in p for p in paths)
        assert "agent.py" in paths

    def test_nested_dir_included(self, client):
        c, store, tmp_path = client
        sid = _make_session(store, "sess-nested")
        wd = _make_working_dir(tmp_path, sid)
        sub = wd / "src" / "utils"
        sub.mkdir(parents=True)
        (sub / "helpers.py").write_text("def f(): pass")

        r = c.get(f"/api/sessions/{sid}/files")
        assert r.status_code == 200
        paths = {e["path"] for e in r.json()}
        assert "src" in paths


# ---------------------------------------------------------------------------
# GET /api/sessions/{id}/files/{path}
# ---------------------------------------------------------------------------


class TestFileContent:
    def test_404_when_session_unknown(self, client):
        c, store, tmp_path = client
        r = c.get("/api/sessions/no-such/files/main.py")
        assert r.status_code == 404

    def test_404_when_file_missing(self, client):
        c, store, tmp_path = client
        sid = _make_session(store, "sess-fc")
        _make_working_dir(tmp_path, sid)
        r = c.get(f"/api/sessions/{sid}/files/nonexistent.py")
        assert r.status_code == 404

    def test_returns_content(self, client):
        c, store, tmp_path = client
        sid = _make_session(store, "sess-content")
        wd = _make_working_dir(tmp_path, sid)
        (wd / "hello.py").write_text("print('hello')")

        r = c.get(f"/api/sessions/{sid}/files/hello.py")
        assert r.status_code == 200
        body = r.json()
        assert body["binary"] is False
        assert body["too_large"] is False
        assert "print('hello')" in body["content"]

    def test_rejects_path_traversal(self, client):
        c, store, tmp_path = client
        sid = _make_session(store, "sess-trav")
        _make_working_dir(tmp_path, sid)
        r = c.get(f"/api/sessions/{sid}/files/../../etc/passwd")
        assert r.status_code in (403, 404)

    def test_rejects_dotenv(self, client):
        c, store, tmp_path = client
        sid = _make_session(store, "sess-env")
        wd = _make_working_dir(tmp_path, sid)
        (wd / ".env").write_text("SECRET=hunter2")
        r = c.get(f"/api/sessions/{sid}/files/.env")
        assert r.status_code == 403

    def test_flags_binary_file(self, client):
        c, store, tmp_path = client
        sid = _make_session(store, "sess-bin")
        wd = _make_working_dir(tmp_path, sid)
        (wd / "model.pkl").write_bytes(b"\x80\x04\x95\x00")

        r = c.get(f"/api/sessions/{sid}/files/model.pkl")
        assert r.status_code == 200
        body = r.json()
        assert body["binary"] is True
        assert "content" not in body

    def test_flags_null_byte_binary(self, client):
        c, store, tmp_path = client
        sid = _make_session(store, "sess-null")
        wd = _make_working_dir(tmp_path, sid)
        (wd / "data.bin").write_bytes(b"hello\x00world")

        r = c.get(f"/api/sessions/{sid}/files/data.bin")
        assert r.status_code == 200
        assert r.json()["binary"] is True

    def test_flags_too_large(self, client, monkeypatch):
        import ai_research_engineer.server.app as app_mod

        monkeypatch.setattr(app_mod, "_MAX_FILE_BYTES", 10)
        c, store, tmp_path = client
        sid = _make_session(store, "sess-large")
        wd = _make_working_dir(tmp_path, sid)
        (wd / "big.txt").write_text("x" * 100)

        r = c.get(f"/api/sessions/{sid}/files/big.txt")
        assert r.status_code == 200
        body = r.json()
        assert body["too_large"] is True
        assert "content" not in body

    def test_redacts_api_key(self, client):
        c, store, tmp_path = client
        sid = _make_session(store, "sess-redact")
        wd = _make_working_dir(tmp_path, sid)
        (wd / "config.py").write_text('api_key = "sk-supersecret123456"')

        r = c.get(f"/api/sessions/{sid}/files/config.py")
        assert r.status_code == 200
        body = r.json()
        assert "supersecret123456" not in body["content"]
        assert body["redacted"] is True

    def test_no_redaction_flag_for_clean_file(self, client):
        c, store, tmp_path = client
        sid = _make_session(store, "sess-clean")
        wd = _make_working_dir(tmp_path, sid)
        (wd / "main.py").write_text("def hello():\n    return 42\n")

        r = c.get(f"/api/sessions/{sid}/files/main.py")
        assert r.status_code == 200
        assert r.json()["redacted"] is False

    def test_nested_path(self, client):
        c, store, tmp_path = client
        sid = _make_session(store, "sess-np")
        wd = _make_working_dir(tmp_path, sid)
        (wd / "src").mkdir()
        (wd / "src" / "utils.py").write_text("UTIL = True")

        r = c.get(f"/api/sessions/{sid}/files/src/utils.py")
        assert r.status_code == 200
        assert "UTIL = True" in r.json()["content"]
