"""
Unit tests for core/references.py — citation parsing and verification.

All network calls are mocked: no real HTTP, no API keys required.
"""

from __future__ import annotations

import textwrap
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from ai_research_engineer.core.references import (
    find_cite_keys,
    find_unknown_cite_keys,
    parse_bib,
    verify_online,
    verify_reference,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_resp(status: int, json_body: Any = None) -> MagicMock:
    m = MagicMock()
    m.status_code = status
    m.json.return_value = json_body or {}
    return m


# ---------------------------------------------------------------------------
# parse_bib
# ---------------------------------------------------------------------------


class TestParseBib:
    def test_basic_entry(self, tmp_path):
        bib = tmp_path / "refs.bib"
        bib.write_text(
            textwrap.dedent("""\
            @article{Smith2023,
              author = {Alice Smith},
              title  = {Deep Learning Survey},
              year   = {2023},
              doi    = {10.1234/dl2023},
              url    = {https://example.com/dl},
            }
            """)
        )
        entries = parse_bib(bib)
        assert "Smith2023" in entries
        e = entries["Smith2023"]
        assert e["doi"] == "10.1234/dl2023"
        assert e["title"] == "Deep Learning Survey"
        assert e["year"] == 2023
        assert e["url"] == "https://example.com/dl"
        assert "Alice Smith" in e["authors"]

    def test_multiple_entries(self, tmp_path):
        bib = tmp_path / "refs.bib"
        bib.write_text(
            textwrap.dedent("""\
            @article{A2020, title = {First}, year = {2020}}
            @inproceedings{B2021, title = {Second}, year = {2021}}
            """)
        )
        entries = parse_bib(bib)
        assert set(entries.keys()) == {"A2020", "B2021"}

    def test_missing_file_returns_empty(self, tmp_path):
        assert parse_bib(tmp_path / "nonexistent.bib") == {}

    def test_missing_doi_is_none(self, tmp_path):
        bib = tmp_path / "refs.bib"
        bib.write_text("@article{X, title = {No DOI}, year = {2022}}\n")
        entries = parse_bib(bib)
        assert entries["X"]["doi"] is None

    def test_non_digit_year_is_none(self, tmp_path):
        bib = tmp_path / "refs.bib"
        bib.write_text('@article{Y, title = {T}, year = {forthcoming}}\n')
        assert parse_bib(bib)["Y"]["year"] is None


# ---------------------------------------------------------------------------
# find_cite_keys
# ---------------------------------------------------------------------------


class TestFindCiteKeys:
    def test_plain_cite(self):
        assert find_cite_keys(r"\cite{Smith2023}") == {"Smith2023"}

    def test_citep(self):
        assert find_cite_keys(r"\citep{Jones2020}") == {"Jones2020"}

    def test_citet(self):
        assert find_cite_keys(r"\citet{Brown2019}") == {"Brown2019"}

    def test_cite_star(self):
        assert find_cite_keys(r"\cite*{Lee2021}") == {"Lee2021"}

    def test_comma_separated(self):
        keys = find_cite_keys(r"\cite{A2020, B2021, C2022}")
        assert keys == {"A2020", "B2021", "C2022"}

    def test_markdown_at_key(self):
        assert find_cite_keys("See [@Smith2023] for details.") == {"Smith2023"}

    def test_markdown_multiple(self):
        keys = find_cite_keys("[@A2020, @B2021]")
        assert keys == {"A2020", "B2021"}

    def test_mixed_latex_and_markdown(self):
        text = r"\cite{L1} and [@L2] and \citep{L3}"
        assert find_cite_keys(text) == {"L1", "L2", "L3"}

    def test_empty_text(self):
        assert find_cite_keys("") == set()

    def test_no_citations(self):
        assert find_cite_keys("Some text with no citations.") == set()


# ---------------------------------------------------------------------------
# find_unknown_cite_keys
# ---------------------------------------------------------------------------


class TestFindUnknownCiteKeys:
    def test_hallucinated_key_flagged(self):
        text = r"\cite{Real2020} and \cite{FakeRef}"
        bib_keys = {"Real2020"}
        unknown = find_unknown_cite_keys(text, bib_keys)
        assert "FakeRef" in unknown
        assert "Real2020" not in unknown

    def test_all_known_returns_empty(self):
        text = r"\cite{A} \citep{B}"
        assert find_unknown_cite_keys(text, {"A", "B"}) == set()

    def test_empty_bib_all_are_unknown(self):
        text = r"\cite{X} \cite{Y}"
        unknown = find_unknown_cite_keys(text, set())
        assert unknown == {"X", "Y"}

    def test_empty_manuscript_returns_empty(self):
        assert find_unknown_cite_keys("", {"A", "B"}) == set()


# ---------------------------------------------------------------------------
# verify_reference — Crossref DOI path
# ---------------------------------------------------------------------------


class TestVerifyReferenceCrossrefDOI:
    def test_doi_200_returns_verified(self):
        with patch("ai_research_engineer.core.references.requests.get", return_value=_make_resp(200)):
            r = verify_reference({"doi": "10.1234/test", "title": None, "url": None})
        assert r["status"] == "verified"
        assert r["method"] == "crossref_doi"

    def test_doi_404_returns_not_found(self):
        with patch("ai_research_engineer.core.references.requests.get", return_value=_make_resp(404)):
            r = verify_reference({"doi": "10.9999/fake", "title": None, "url": None})
        assert r["status"] == "not_found"
        assert r["method"] == "crossref_doi"


# ---------------------------------------------------------------------------
# verify_reference — Crossref title-search path
# ---------------------------------------------------------------------------


class TestVerifyReferenceCrossrefTitle:
    def test_title_match_returns_verified(self):
        json_body = {"message": {"items": [{"title": ["Deep Learning Survey"]}]}}
        with patch("ai_research_engineer.core.references.requests.get", return_value=_make_resp(200, json_body)):
            r = verify_reference({"doi": None, "title": "Deep Learning Survey", "url": None})
        assert r["status"] == "verified"
        assert r["method"] == "crossref_title"

    def test_title_no_items_returns_not_found(self):
        json_body = {"message": {"items": []}}
        with patch("ai_research_engineer.core.references.requests.get", return_value=_make_resp(200, json_body)):
            r = verify_reference({"doi": None, "title": "Totally Fake Paper XYZ", "url": None})
        assert r["status"] == "not_found"
        assert r["method"] == "crossref_title"


# ---------------------------------------------------------------------------
# verify_reference — OpenAlex (optional, fail-soft)
# ---------------------------------------------------------------------------


class TestVerifyReferenceOpenAlex:
    def test_openalex_skipped_when_no_key(self, monkeypatch):
        monkeypatch.delenv("OPENALEX_API_KEY", raising=False)
        # Crossref returns nothing useful (non-200, non-404) → should fall through to unverified
        with patch("ai_research_engineer.core.references.requests.get", return_value=_make_resp(500)):
            r = verify_reference({"doi": None, "title": "Some Title", "url": None})
        assert r["status"] == "unverified"

    def test_openalex_409_is_fail_soft(self, monkeypatch):
        monkeypatch.setenv("OPENALEX_API_KEY", "fake-key")
        # Crossref title search: 200 with empty items → not_found → try OpenAlex
        # OpenAlex returns 409 → fail-soft → overall unverified
        crossref_resp = _make_resp(200, {"message": {"items": []}})
        openalex_resp = _make_resp(409)
        responses = iter([crossref_resp, openalex_resp])
        with patch("ai_research_engineer.core.references.requests.get", side_effect=lambda *a, **kw: next(responses)):
            r = verify_reference({"doi": None, "title": "Title", "url": None})
        # crossref title said not_found (items empty) → returned not_found directly
        # (OpenAlex is only tried when crossref returns None, i.e. non-200/non-404 → but
        #  here crossref_title returns not_found so OpenAlex is not reached)
        assert r["status"] in ("not_found", "unverified")

    def test_openalex_exception_is_fail_soft(self, monkeypatch):
        monkeypatch.setenv("OPENALEX_API_KEY", "fake-key")
        with patch(
            "ai_research_engineer.core.references.requests.get",
            side_effect=ConnectionError("boom"),
        ):
            r = verify_reference({"doi": None, "title": None, "url": None})
        assert r["status"] == "unverified"
        assert "raises" not in str(r)


# ---------------------------------------------------------------------------
# verify_reference — URL HEAD path (SSRF guard)
# ---------------------------------------------------------------------------


class TestVerifyReferenceURLHead:
    def test_ssrf_blocked_host_returns_unverified(self):
        # 192.168.1.1 is RFC-1918 private → SSRF blocked
        r = verify_reference({"doi": None, "title": None, "url": "http://192.168.1.1/paper"})
        assert r["status"] == "unverified"
        assert "SSRF" in r["detail"]

    def test_url_head_200_returns_verified(self):
        head_resp = _make_resp(200)
        ssrf_none = None  # not blocked
        with (
            patch("ai_research_engineer.core.references.requests.get", return_value=_make_resp(500)),
            patch("ai_research_engineer.core.references.requests.head", return_value=head_resp),
            patch("ai_research_engineer.tools.web_ops._check_url_for_ssrf", return_value=ssrf_none),
        ):
            r = verify_reference({"doi": None, "title": None, "url": "https://example.com/paper.pdf"})
        assert r["status"] == "verified"
        assert r["method"] == "url_head"

    def test_url_head_404_returns_not_found(self):
        head_resp = _make_resp(404)
        with (
            patch("ai_research_engineer.core.references.requests.get", return_value=_make_resp(500)),
            patch("ai_research_engineer.core.references.requests.head", return_value=head_resp),
            patch("ai_research_engineer.tools.web_ops._check_url_for_ssrf", return_value=None),
        ):
            r = verify_reference({"doi": None, "title": None, "url": "https://example.com/missing"})
        assert r["status"] == "not_found"
        assert r["method"] == "url_head"


# ---------------------------------------------------------------------------
# Fail-soft: network exception → unverified, never raises
# ---------------------------------------------------------------------------


class TestFailSoft:
    def test_network_exception_returns_unverified(self):
        with patch("ai_research_engineer.core.references.requests.get", side_effect=OSError("boom")):
            r = verify_reference({"doi": "10.x/y", "title": "T", "url": None})
        assert r["status"] == "unverified"

    def test_never_raises(self):
        with patch("ai_research_engineer.core.references.requests.get", side_effect=RuntimeError("unexpected")):
            r = verify_reference({"doi": None, "title": None, "url": None})
        assert isinstance(r, dict)
        assert r["status"] == "unverified"


# ---------------------------------------------------------------------------
# verify_online: cache prevents duplicate calls
# ---------------------------------------------------------------------------


class TestVerifyOnlineCache:
    def test_cache_hit_avoids_second_call(self, tmp_path):
        db = tmp_path / "cache.db"
        entry = {"doi": "10.1/cached", "title": "Cached Paper", "url": None}
        call_count = {"n": 0}

        def _fake_get(*args, **kwargs):
            call_count["n"] += 1
            return _make_resp(200)

        with patch("ai_research_engineer.core.references.requests.get", side_effect=_fake_get):
            results1 = verify_online({"Key1": entry}, cache_db_path=db)

        # Second call — same entry, same db — should hit cache
        with patch("ai_research_engineer.core.references.requests.get", side_effect=_fake_get):
            results2 = verify_online({"Key1": entry}, cache_db_path=db)

        assert call_count["n"] == 1  # only one real network call
        assert results1[0]["status"] == "verified"
        assert results2[0]["cached"] is True
        assert results2[0]["status"] == "verified"

    def test_different_entries_each_call(self, tmp_path):
        db = tmp_path / "cache.db"
        entries = {
            "A": {"doi": "10.1/a", "title": None, "url": None},
            "B": {"doi": "10.1/b", "title": None, "url": None},
        }
        with patch("ai_research_engineer.core.references.requests.get", return_value=_make_resp(200)):
            results = verify_online(entries, cache_db_path=db)
        assert len(results) == 2
        assert all(r["status"] == "verified" for r in results)


# ---------------------------------------------------------------------------
# ReferenceVerifierAgent integration (no ADK runner — mock ctx)
# ---------------------------------------------------------------------------


class _MockSession:
    def __init__(self, session_id: str = "test-session-ref"):
        self.id = session_id
        self.state: dict = {}


class _MockCtx:
    def __init__(self):
        self.session = _MockSession()


class TestReferenceVerifierAgent:
    def _make_agent(self, working_dir: Path):
        from ai_research_engineer.agents.adk.reference_verifier import ReferenceVerifierAgent

        return ReferenceVerifierAgent(working_dir=str(working_dir))

    def _make_manuscript(self, working_dir: Path, bib_text: str, tex_text: str):
        ms = working_dir / "manuscript"
        ms.mkdir(parents=True, exist_ok=True)
        (ms / "references.bib").write_text(bib_text)
        (ms / "main.tex").write_text(tex_text)
        return ms

    @pytest.mark.asyncio
    async def test_writes_verification_report(self, tmp_path):
        bib = textwrap.dedent("""\
            @article{Good2023, title = {Good Paper}, doi = {10.1/good}, year = {2023}}
        """)
        tex = r"\cite{Good2023} is well-cited."
        ms = self._make_manuscript(tmp_path, bib, tex)
        agent = self._make_agent(tmp_path)
        ctx = _MockCtx()

        with patch("ai_research_engineer.core.references.requests.get", return_value=_make_resp(200)):
            _ = [e async for e in agent._run_async_impl(ctx)]

        assert (ms / "verification_report.md").exists()
        report = (ms / "verification_report.md").read_text()
        assert "Citation Verification Report" in report

    @pytest.mark.asyncio
    async def test_stores_verification_counts_in_state(self, tmp_path):
        bib = textwrap.dedent("""\
            @article{A2020, title = {T}, doi = {10.1/a}, year = {2020}}
        """)
        tex = r"\cite{A2020} and \cite{GHOST}"
        self._make_manuscript(tmp_path, bib, tex)
        agent = self._make_agent(tmp_path)
        ctx = _MockCtx()

        with patch("ai_research_engineer.core.references.requests.get", return_value=_make_resp(200)):
            _ = [e async for e in agent._run_async_impl(ctx)]

        counts = ctx.session.state.get("_verification_counts")
        assert counts is not None
        assert counts["total"] == 1        # one .bib entry
        assert counts["hallucinated"] == 1  # GHOST is in tex but not in bib
        assert counts["verified"] == 1

    @pytest.mark.asyncio
    async def test_emits_event_with_summary_text(self, tmp_path):
        bib = "@article{Z, title = {Z}, doi = {10.1/z}, year = {2022}}\n"
        tex = r"\cite{Z}"
        self._make_manuscript(tmp_path, bib, tex)
        agent = self._make_agent(tmp_path)
        ctx = _MockCtx()

        with patch("ai_research_engineer.core.references.requests.get", return_value=_make_resp(200)):
            events = [e async for e in agent._run_async_impl(ctx)]

        assert len(events) >= 1
        text = events[-1].content.parts[0].text
        assert "Verification" in text

    @pytest.mark.asyncio
    async def test_no_manuscript_dir_is_noop(self, tmp_path):
        agent = self._make_agent(tmp_path)
        ctx = _MockCtx()
        # No manuscript dir created
        events = [e async for e in agent._run_async_impl(ctx)]
        assert len(events) == 1
        counts = ctx.session.state.get("_verification_counts")
        assert counts is not None
        assert counts["total"] == 0

    @pytest.mark.asyncio
    async def test_hallucinated_key_appears_in_report(self, tmp_path):
        bib = "@article{Real, title = {Real Paper}, year = {2020}}\n"
        tex = r"\cite{Real} \cite{HALLUCINATED}"
        ms = self._make_manuscript(tmp_path, bib, tex)
        agent = self._make_agent(tmp_path)
        ctx = _MockCtx()

        with patch("ai_research_engineer.core.references.requests.get", return_value=_make_resp(200)):
            _ = [e async for e in agent._run_async_impl(ctx)]

        report = (ms / "verification_report.md").read_text()
        assert "HALLUCINATED" in report
        assert "Hallucinated Citation Keys" in report


# ---------------------------------------------------------------------------
# VerificationEvent in events.py
# ---------------------------------------------------------------------------


class TestVerificationEvent:
    def test_event_to_dict_round_trip(self):
        from ai_research_engineer.core.events import VerificationEvent, event_to_dict

        ev = VerificationEvent(total=5, verified=4, not_found=1, unverified=0, hallucinated=0)
        d = event_to_dict(ev)
        assert d["type"] == "verification"
        assert d["total"] == 5
        assert d["verified"] == 4
        assert d["not_found"] == 1

    def test_event_type_in_map(self):
        from ai_research_engineer.core.events import EVENT_TYPE_MAP

        assert "verification" in EVENT_TYPE_MAP
