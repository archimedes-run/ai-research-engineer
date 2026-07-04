"""S1-7: unit tests for the citation-graph serving endpoints:
  GET /api/sessions/{id}/graphs
  GET /api/sessions/{id}/graphs/{name}
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


def _init_store(tmp_path: Path):
    from ai_research_engineer.server.run_store import RunStore

    RunStore.init(db_path=tmp_path / "test.db")
    RunStore.DATA_DIR = tmp_path  # working dirs under tmp_path/runs/
    return RunStore


def _make_session(store, session_id: str = "sess-g") -> str:
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


def _graphs_dir(tmp_path: Path, session_id: str) -> Path:
    d = tmp_path / "runs" / session_id / "knowledge_base" / "graphs"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _write_graph(tmp_path: Path, session_id: str, name: str, data: dict) -> Path:
    d = _graphs_dir(tmp_path, session_id)
    p = d / name
    p.write_text(json.dumps(data), encoding="utf-8")
    return p


@pytest.fixture()
def client(tmp_path):
    from ai_research_engineer.server.app import app
    from ai_research_engineer.server.run_store import RunStore

    original = RunStore.DATA_DIR
    store = _init_store(tmp_path)
    yield TestClient(app, raise_server_exceptions=True), store, tmp_path
    RunStore.DATA_DIR = original


_SAMPLE = {
    "seeds": ["SEED"],
    "hops": 1,
    "node_count": 3,
    "edge_count": 2,
    "nodes": [
        {"id": "SEED", "label": "Seed", "year": 2021, "group": "seed", "influential_citations": 50},
        {"id": "A1", "label": "Ancestor", "year": 2019, "group": "ancestor", "influential_citations": 10},
        {"id": "D1", "label": "Descendant", "year": 2024, "group": "descendant", "influential_citations": 5},
    ],
    "edges": [
        {"source": "A1", "target": "SEED"},
        {"source": "SEED", "target": "D1"},
    ],
}


# --------------------------------------------------------------------------- #
# GET /api/sessions/{id}/graphs  (list)
# --------------------------------------------------------------------------- #
class TestListGraphs:
    def test_404_when_session_unknown(self, client):
        c, _, _ = client
        assert c.get("/api/sessions/nope/graphs").status_code == 404

    def test_empty_list_when_no_graphs_dir(self, client):
        c, store, _ = client
        sid = _make_session(store, "sess-nograph")
        r = c.get(f"/api/sessions/{sid}/graphs")
        assert r.status_code == 200
        assert r.json() == []  # resilient: missing graphs dir -> empty, not 404

    def test_lists_graphs_with_metadata(self, client):
        c, store, tmp_path = client
        sid = _make_session(store, "sess-list")
        _write_graph(tmp_path, sid, "graph_20260101_000000_000000.json", _SAMPLE)

        r = c.get(f"/api/sessions/{sid}/graphs")
        assert r.status_code == 200
        body = r.json()
        assert len(body) == 1
        entry = body[0]
        assert entry["name"].endswith(".json")
        assert entry["node_count"] == 3
        assert entry["edge_count"] == 2
        assert entry["seeds"] == ["SEED"]

    def test_derives_counts_when_absent(self, client):
        c, store, tmp_path = client
        sid = _make_session(store, "sess-derive")
        _write_graph(tmp_path, sid, "g.json", {"nodes": [{"id": "x"}], "edges": []})
        entry = c.get(f"/api/sessions/{sid}/graphs").json()[0]
        assert entry["node_count"] == 1  # derived from len(nodes)
        assert entry["edge_count"] == 0

    def test_corrupt_graph_listed_with_null_counts(self, client):
        c, store, tmp_path = client
        sid = _make_session(store, "sess-corrupt")
        d = _graphs_dir(tmp_path, sid)
        (d / "bad.json").write_text("{not valid json")
        entry = c.get(f"/api/sessions/{sid}/graphs").json()[0]
        assert entry["name"] == "bad.json"
        assert entry["node_count"] is None


# --------------------------------------------------------------------------- #
# GET /api/sessions/{id}/graphs/{name}  (fetch)
# --------------------------------------------------------------------------- #
class TestFetchGraph:
    def test_404_when_session_unknown(self, client):
        c, _, _ = client
        assert c.get("/api/sessions/nope/graphs/g.json").status_code == 404

    def test_returns_full_graph(self, client):
        c, store, tmp_path = client
        sid = _make_session(store, "sess-fetch")
        _write_graph(tmp_path, sid, "graph_x.json", _SAMPLE)

        r = c.get(f"/api/sessions/{sid}/graphs/graph_x.json")
        assert r.status_code == 200
        body = r.json()
        assert body["node_count"] == 3
        assert {n["group"] for n in body["nodes"]} == {"seed", "ancestor", "descendant"}
        assert {"source": "A1", "target": "SEED"} in body["edges"]

    def test_404_when_graph_missing(self, client):
        c, store, tmp_path = client
        sid = _make_session(store, "sess-missing")
        _graphs_dir(tmp_path, sid)
        assert c.get(f"/api/sessions/{sid}/graphs/nope.json").status_code == 404

    def test_rejects_non_json_name(self, client):
        c, store, _ = client
        sid = _make_session(store, "sess-ext")
        assert c.get(f"/api/sessions/{sid}/graphs/secret.txt").status_code == 403

    def test_rejects_path_traversal(self, client):
        c, store, tmp_path = client
        sid = _make_session(store, "sess-trav")
        _graphs_dir(tmp_path, sid)
        # '..' is rejected before any filesystem access.
        r = c.get(f"/api/sessions/{sid}/graphs/..%2f..%2fpipeline.json")
        assert r.status_code in (403, 404)

    def test_422_on_corrupt_json(self, client):
        c, store, tmp_path = client
        sid = _make_session(store, "sess-badjson")
        d = _graphs_dir(tmp_path, sid)
        (d / "bad.json").write_text("{not valid json")
        assert c.get(f"/api/sessions/{sid}/graphs/bad.json").status_code == 422
