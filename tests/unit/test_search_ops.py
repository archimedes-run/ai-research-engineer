"""S1-3: multi-source search, findpapers builder, fetch_url v2, registry gating.

All HTTP is mocked with committed fixture payloads — no network in tests.
"""

import json
import socket
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
import requests

from ai_research_engineer.tools import search_ops
from ai_research_engineer.tools.research_ops import _to_findpapers_query
from ai_research_engineer.tools.web_ops import fetch_url


FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"
_GET = "ai_research_engineer.tools.search_ops.requests.get"
_POST = "ai_research_engineer.tools.search_ops.requests.post"


def _resp(json_data=None, status=200, text=None):
    r = Mock()
    r.status_code = status
    r.raise_for_status = Mock()
    if json_data is not None:
        r.json.return_value = json_data
    if text is not None:
        r.text = text
    return r


def _load(name):
    return json.loads((FIXTURES / name).read_text())


# --------------------------------------------------------------------------- #
# OpenAlex
# --------------------------------------------------------------------------- #
class TestOpenAlex:
    def test_happy_path_reconstructs_inverted_abstract(self):
        with patch(_GET, return_value=_resp(_load("openalex_works.json"))):
            out = json.loads(search_ops.openalex_search("attention", limit=10))
        assert len(out) == 2
        assert out[0]["title"] == "Attention Is All You Need"
        assert out[0]["year"] == 2017
        # Full ordered reconstruction, incl. words at 2+ positions:
        # models@[2,9], on@[5,11], attention@[6,12]. Scrambled key order in the
        # fixture also proves the position sort. A naive "place each word once"
        # impl would drop the second models/on/attention and fail this.
        assert (
            out[0]["abstract"]
            == "The dominant models are based on attention and the models rely on attention"
        )
        assert out[0]["cited_by_count"] == 95000
        assert out[0]["doi"].endswith("3295349")

    def test_reconstruct_repeats_word_at_multiple_positions(self):
        # Direct unit: "the" at [0, 3] must appear at BOTH positions, in order.
        inv = {"the": [0, 3], "cat": [1], "sat": [2], "mat": [4]}
        assert search_ops._reconstruct_inverted_abstract(inv) == "the cat sat the mat"

    def test_reconstruction_bites_a_naive_one_position_impl(self):
        # A naive impl that keeps only one position per word would collapse the
        # repeated words; assert the fixture actually distinguishes the two.
        inv = _load("openalex_works.json")["results"][0]["abstract_inverted_index"]
        correct = search_ops._reconstruct_inverted_abstract(inv)
        naive = " ".join(w for _, w in sorted((min(p), w) for w, p in inv.items()))
        assert naive != correct  # the fixture has repeats, so it exercises the bug

    def test_empty_results(self):
        with patch(_GET, return_value=_resp({"results": []})):
            out = search_ops.openalex_search("zzz-no-such-topic")
        assert "No OpenAlex results" in out

    def test_rate_limit_graceful(self):
        with patch(_GET, return_value=_resp(status=429)):
            out = search_ops.openalex_search("x")
        assert "429" in out and "rate limit" in out.lower()

    def test_http_error_graceful(self):
        with patch(_GET, side_effect=requests.exceptions.ConnectionError("boom")):
            out = search_ops.openalex_search("x")
        assert "failed" in out.lower()


# --------------------------------------------------------------------------- #
# Papers with Code
# --------------------------------------------------------------------------- #
class TestPapersWithCode:
    def test_happy_path_papers_and_repos(self):
        with patch(_GET, return_value=_resp(_load("paperswithcode_search.json"))):
            out = json.loads(search_ops.paperswithcode_search("bert"))
        assert len(out) == 2
        assert out[0]["title"].startswith("BERT")
        assert out[0]["repo_url"] == "https://github.com/google-research/bert"
        assert out[0]["repo_stars"] == 37000

    def test_empty_results(self):
        with patch(_GET, return_value=_resp({"results": []})):
            assert "No Papers with Code results" in search_ops.paperswithcode_search("zzz")

    def test_rate_limit_graceful(self):
        with patch(_GET, return_value=_resp(status=429)):
            assert "429" in search_ops.paperswithcode_search("x")

    def test_http_error_graceful(self):
        with patch(_GET, side_effect=requests.exceptions.Timeout("slow")):
            assert "failed" in search_ops.paperswithcode_search("x").lower()


# --------------------------------------------------------------------------- #
# GitHub
# --------------------------------------------------------------------------- #
class TestGitHub:
    def test_happy_path_repositories(self, monkeypatch):
        monkeypatch.delenv("GITHUB_TOKEN", raising=False)
        with patch(_GET, return_value=_resp(_load("github_repositories.json"))):
            out = json.loads(search_ops.github_search("bert", mode="repositories"))
        assert out[0]["full_name"] == "google-research/bert"
        assert out[0]["stars"] == 37000

    def test_honors_github_token_and_higher_page_size(self, monkeypatch):
        monkeypatch.setenv("GITHUB_TOKEN", "ghp_test")
        with patch(_GET, return_value=_resp(_load("github_repositories.json"))) as mock_get:
            search_ops.github_search("bert", limit=100)
        _, kwargs = mock_get.call_args
        assert kwargs["headers"].get("Authorization") == "Bearer ghp_test"
        assert kwargs["params"]["per_page"] == 100  # authed budget

    def test_unauthenticated_degrades_page_size(self, monkeypatch):
        monkeypatch.delenv("GITHUB_TOKEN", raising=False)
        with patch(_GET, return_value=_resp(_load("github_repositories.json"))) as mock_get:
            search_ops.github_search("bert", limit=100)
        _, kwargs = mock_get.call_args
        assert "Authorization" not in kwargs["headers"]
        assert kwargs["params"]["per_page"] == 30  # capped low without a token

    def test_empty_results(self):
        with patch(_GET, return_value=_resp({"items": []})):
            assert "No GitHub repositories results" in search_ops.github_search("zzz")

    def test_rate_limit_graceful(self, monkeypatch):
        monkeypatch.delenv("GITHUB_TOKEN", raising=False)
        with patch(_GET, return_value=_resp(status=403)):
            out = search_ops.github_search("x")
        assert "403" in out and "GITHUB_TOKEN" in out


# --------------------------------------------------------------------------- #
# Web search (provider-pluggable)
# --------------------------------------------------------------------------- #
class TestWebSearch:
    def test_provider_none_returns_not_configured(self, monkeypatch):
        monkeypatch.setenv("SEARCH_WEB_PROVIDER", "none")
        assert "not configured" in search_ops.web_search("x").lower()

    def test_tavily_happy_path(self, monkeypatch):
        monkeypatch.setenv("SEARCH_WEB_PROVIDER", "tavily")
        monkeypatch.setenv("TAVILY_API_KEY", "secret")
        data = {"results": [{"title": "Result", "url": "https://x", "content": "snippet"}]}
        with patch(_POST, return_value=_resp(data)):
            out = json.loads(search_ops.web_search("x"))
        assert out[0]["title"] == "Result"

    def test_tavily_missing_key_graceful(self, monkeypatch):
        monkeypatch.setenv("SEARCH_WEB_PROVIDER", "tavily")
        monkeypatch.delenv("TAVILY_API_KEY", raising=False)
        assert "TAVILY_API_KEY" in search_ops.web_search("x")


# --------------------------------------------------------------------------- #
# Registry gating (S1-6 seed): web_search absent from the toolbelt when none
# --------------------------------------------------------------------------- #
class TestRegistryGating:
    def test_web_search_absent_when_provider_none(self, monkeypatch):
        monkeypatch.delenv("DISABLE_NETWORK_ACCESS", raising=False)
        monkeypatch.setenv("SEARCH_WEB_PROVIDER", "none")
        from ai_research_engineer.core.tool_registry import available_tools, registered_names

        funcs = available_tools()
        assert "web_search" in registered_names()  # it IS registered ...
        assert search_ops.web_search not in funcs  # ... but NOT available -> absent from the toolbelt
        assert search_ops.openalex_search in funcs  # network tools remain available

    def test_web_search_present_when_provider_configured(self, monkeypatch):
        monkeypatch.delenv("DISABLE_NETWORK_ACCESS", raising=False)
        monkeypatch.setenv("SEARCH_WEB_PROVIDER", "tavily")
        monkeypatch.setenv("TAVILY_API_KEY", "k")
        from ai_research_engineer.core.tool_registry import available_tools

        assert search_ops.web_search in available_tools()

    def test_network_tools_absent_when_network_disabled(self, monkeypatch):
        monkeypatch.setenv("DISABLE_NETWORK_ACCESS", "true")
        from ai_research_engineer.core.tool_registry import available_tools

        assert search_ops.openalex_search not in available_tools()


# --------------------------------------------------------------------------- #
# findpapers DSL builder
# --------------------------------------------------------------------------- #
class TestFindpapersBuilder:
    @pytest.mark.parametrize(
        "nl, expected",
        [
            ("The effect of dropout on regularization", "[effect] AND [dropout] AND [regularization]"),
            (
                "Optimization of neural networks with RL",
                "([optimization] OR [optimisation]) AND [neural] AND [networks] AND ([rl] OR [reinforcement learning])",
            ),
            (
                "CNN for object detection",
                "([cnn] OR [convolutional neural network]) AND [object] AND [detection]",
            ),
            ("[transformer] AND [attention]", "[transformer] AND [attention]"),
            ("the of for with", "[research]"),
        ],
    )
    def test_nl_to_dsl(self, nl, expected):
        assert _to_findpapers_query(nl) == expected


# --------------------------------------------------------------------------- #
# fetch_url v2 (markdown extraction + offset pagination); SSRF stays in Stage 0
# --------------------------------------------------------------------------- #
class TestFetchUrlV2:
    def _fetch(self, html, **kwargs):
        dns = [(socket.AF_INET, None, None, "", ("93.184.216.34", 0))]
        r = Mock()
        r.text = html
        r.is_redirect = False
        r.raise_for_status = Mock()
        with (
            patch("ai_research_engineer.tools.web_ops.requests.get", return_value=r),
            patch("ai_research_engineer.tools.web_ops.socket.getaddrinfo", return_value=dns),
        ):
            return fetch_url("https://example.com/article", **kwargs)

    def test_markdown_extraction_strips_boilerplate(self):
        html = (FIXTURES / "web_article.html").read_text()
        out = self._fetch(html)
        assert "# Understanding Attention Mechanisms" in out  # heading kept as markdown
        assert "NAVIGATION_BOILERPLATE_SHOULD_BE_STRIPPED" not in out
        assert "FOOTER_BOILERPLATE_SHOULD_BE_STRIPPED" not in out

    def test_offset_pagination_is_continuous(self):
        html = (FIXTURES / "web_article.html").read_text()
        full = self._fetch(html, max_content_length=100_000)  # whole doc, no hint
        p1 = self._fetch(html, max_content_length=100, offset=0)
        p2 = self._fetch(html, max_content_length=100, offset=100)
        core1 = p1.split("\n\n[More content")[0]
        core2 = p2.split("\n\n[More content")[0]
        assert core1 == full[:100]
        assert core2 == full[100:200]  # contiguous continuation
        assert "More content available" in p1  # continuation hint when more remains

    def test_default_max_content_length_is_25000(self):
        import inspect

        assert inspect.signature(fetch_url).parameters["max_content_length"].default == 25000
