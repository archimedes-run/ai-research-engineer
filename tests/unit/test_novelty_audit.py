"""S2-8: novelty audit persistence + serving endpoint."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from ai_research_engineer.core.novelty.audit import append_audit, build_audit_entry, load_audits


# --------------------------------------------------------------------------- #
# Audit append + round-trip
# --------------------------------------------------------------------------- #
def _entry(title, severity):
    idea = {"title": title, "description": f"desc {title}"}
    verdict = {"approved": severity != "core", "verdict": "reject" if severity == "core" else "approve",
               "reason": "r", "falsifier_rounds": 1, "killing_works": []}
    table = [{"work_id": "W1", "overlap_summary": "s", "differs_because": "d", "overlap_severity": severity}]
    prefiltered = [{"id": "W1", "title": "Prior Work", "url": "http://x", "source": "openalex", "score": 0.8}]
    recall = {"per_channel_counts": {"openalex": 3, "paperswithcode": 0}, "channel_status": {"openalex": "live", "paperswithcode": "dead"}}
    return build_audit_entry(idea, verdict=verdict, table=table, prefiltered=prefiltered, recall=recall)


def test_append_per_idea_and_round_trip(tmp_path):
    assert load_audits(str(tmp_path)) == []                 # empty before anything

    append_audit(str(tmp_path), _entry("idea A", "partial"))
    append_audit(str(tmp_path), _entry("idea B", "core"))

    audits = load_audits(str(tmp_path))
    assert len(audits) == 2                                  # one entry appended per idea
    assert [a["idea_title"] for a in audits] == ["idea A", "idea B"]

    # Round-trips through the on-disk JSON array unchanged.
    raw = json.loads((tmp_path / "knowledge_base" / "novelty_audit.json").read_text())
    assert raw == audits


def test_build_entry_joins_table_to_prefiltered():
    entry = _entry("idea C", "partial")
    card = entry["differentiation_table"][0]
    assert card["title"] == "Prior Work"                     # joined from prefiltered by work_id
    assert card["url"] == "http://x"
    assert card["source"] == "openalex"
    assert card["overlap_severity"] == "partial"
    # recall channel_status carried through (incl. the dead channel)
    assert entry["recall"]["channel_status"]["paperswithcode"] == "dead"
    assert entry["falsifier"]["verdict"] == "approve"


def test_load_corrupt_returns_empty(tmp_path):
    p = tmp_path / "knowledge_base" / "novelty_audit.json"
    p.parent.mkdir(parents=True)
    p.write_text("{not valid json")
    assert load_audits(str(tmp_path)) == []


# --------------------------------------------------------------------------- #
# GET /api/sessions/{id}/novelty_audit  (same hardening as S1-7)
# --------------------------------------------------------------------------- #
def _make_session(store, sid="sess-nov"):
    store.save_session({"session_id": sid, "status": "running", "title": "T", "topic": "t",
                        "agent_type": "adk", "started_at": datetime.now().isoformat()})
    return sid


@pytest.fixture()
def client(tmp_path):
    from ai_research_engineer.server.app import app
    from ai_research_engineer.server.run_store import RunStore

    original = RunStore.DATA_DIR
    RunStore.init(db_path=tmp_path / "t.db")
    RunStore.DATA_DIR = tmp_path
    yield TestClient(app, raise_server_exceptions=True), RunStore, tmp_path
    RunStore.DATA_DIR = original


def _audit_file(tmp_path: Path, sid: str) -> Path:
    d = tmp_path / "runs" / sid / "knowledge_base"
    d.mkdir(parents=True, exist_ok=True)
    return d / "novelty_audit.json"


def test_endpoint_404_unknown_session(client):
    c, _, _ = client
    assert c.get("/api/sessions/nope/novelty_audit").status_code == 404


def test_endpoint_empty_list_when_missing(client):
    c, store, _ = client
    sid = _make_session(store, "sess-empty")
    (client[2] / "runs" / sid).mkdir(parents=True, exist_ok=True)
    r = c.get(f"/api/sessions/{sid}/novelty_audit")
    assert r.status_code == 200 and r.json() == []           # resilient: no audit -> []


def test_endpoint_returns_audit(client):
    c, store, tmp_path = client
    sid = _make_session(store, "sess-has")
    audits = [_entry("idea A", "partial"), _entry("idea B", "core")]
    _audit_file(tmp_path, sid).write_text(json.dumps(audits))
    r = c.get(f"/api/sessions/{sid}/novelty_audit")
    assert r.status_code == 200
    body = r.json()
    assert len(body) == 2
    assert body[1]["approved"] is False


def test_endpoint_corrupt_is_422(client):
    c, store, tmp_path = client
    sid = _make_session(store, "sess-bad")
    _audit_file(tmp_path, sid).write_text("{not json")
    assert c.get(f"/api/sessions/{sid}/novelty_audit").status_code == 422


def test_endpoint_traversal_session_id_rejected(client):
    c, _, _ = client
    # a traversal attempt in the session id fails the session lookup -> 404
    assert c.get("/api/sessions/..%2f..%2fetc/novelty_audit").status_code in (404, 400)
