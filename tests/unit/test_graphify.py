"""
Unit tests for core/graphify.py.

All tests are offline — the graphify package is either mocked or its
availability is asserted without requiring it to be installed.
"""

from __future__ import annotations

import importlib
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _reload_module():
    """Force a fresh import of graphify module so mocks apply cleanly."""
    mod_name = "ai_research_engineer.core.graphify"
    if mod_name in sys.modules:
        del sys.modules[mod_name]
    return importlib.import_module(mod_name)


# ---------------------------------------------------------------------------
# graphify_available
# ---------------------------------------------------------------------------


class TestGraphifyAvailable:
    def test_returns_true_when_graphify_spec_found(self):
        from ai_research_engineer.core.graphify import graphify_available

        with patch("importlib.util.find_spec", return_value=MagicMock()) as mock_spec:
            result = graphify_available()
        mock_spec.assert_called_once_with("graphify")
        assert result is True

    def test_returns_false_when_graphify_spec_missing(self):
        from ai_research_engineer.core.graphify import graphify_available

        with patch("importlib.util.find_spec", return_value=None):
            result = graphify_available()
        assert result is False

    def test_return_type_is_bool(self):
        from ai_research_engineer.core.graphify import graphify_available

        with patch("importlib.util.find_spec", return_value=MagicMock()):
            assert isinstance(graphify_available(), bool)


# ---------------------------------------------------------------------------
# ensure_graph — fail-soft when graphify not available
# ---------------------------------------------------------------------------


class TestEnsureGraphNotAvailable:
    def test_returns_none_when_package_missing(self, tmp_path):
        from ai_research_engineer.core.graphify import ensure_graph

        with patch("ai_research_engineer.core.graphify.graphify_available", return_value=False):
            result = ensure_graph(tmp_path)
        assert result is None

    def test_logs_warning_when_package_missing(self, tmp_path, caplog):
        import logging

        from ai_research_engineer.core.graphify import ensure_graph

        with patch("ai_research_engineer.core.graphify.graphify_available", return_value=False):
            with caplog.at_level(logging.WARNING, logger="ai_research_engineer.core.graphify"):
                ensure_graph(tmp_path)
        assert any("not installed" in r.message for r in caplog.records)


# ---------------------------------------------------------------------------
# ensure_graph — success path with mocked _rebuild_code
# ---------------------------------------------------------------------------


class TestEnsureGraphSuccess:
    def test_returns_graph_path_on_success(self, tmp_path):
        from ai_research_engineer.core.graphify import ensure_graph

        graph_path = tmp_path / "graphify-out" / "graph.json"
        graph_path.parent.mkdir(parents=True)
        graph_path.write_text("{}")

        mock_rebuild = MagicMock(return_value=True)

        with (
            patch("ai_research_engineer.core.graphify.graphify_available", return_value=True),
            patch("graphify.watch._rebuild_code", mock_rebuild, create=True),
        ):
            result = ensure_graph(tmp_path)

        assert result == graph_path

    def test_calls_rebuild_with_working_dir(self, tmp_path):
        from ai_research_engineer.core.graphify import ensure_graph

        graph_path = tmp_path / "graphify-out" / "graph.json"
        graph_path.parent.mkdir(parents=True)
        graph_path.write_text("{}")

        mock_rebuild = MagicMock(return_value=True)

        with (
            patch("ai_research_engineer.core.graphify.graphify_available", return_value=True),
            patch("graphify.watch._rebuild_code", mock_rebuild, create=True),
        ):
            ensure_graph(tmp_path)

        mock_rebuild.assert_called_once_with(tmp_path)

    def test_returns_none_when_graph_json_missing_after_build(self, tmp_path):
        from ai_research_engineer.core.graphify import ensure_graph

        mock_rebuild = MagicMock(return_value=True)

        with (
            patch("ai_research_engineer.core.graphify.graphify_available", return_value=True),
            patch("graphify.watch._rebuild_code", mock_rebuild, create=True),
        ):
            result = ensure_graph(tmp_path)

        assert result is None


# ---------------------------------------------------------------------------
# ensure_graph — fail-soft when _rebuild_code raises
# ---------------------------------------------------------------------------


class TestEnsureGraphFailSoft:
    def test_returns_none_on_import_error(self, tmp_path):
        from ai_research_engineer.core.graphify import ensure_graph

        with (
            patch("ai_research_engineer.core.graphify.graphify_available", return_value=True),
            patch("builtins.__import__", side_effect=ImportError("no graphify")),
        ):
            result = ensure_graph(tmp_path)
        assert result is None

    def test_returns_none_on_rebuild_exception(self, tmp_path):
        from ai_research_engineer.core.graphify import ensure_graph

        mock_rebuild = MagicMock(side_effect=RuntimeError("disk full"))

        with (
            patch("ai_research_engineer.core.graphify.graphify_available", return_value=True),
            patch("graphify.watch._rebuild_code", mock_rebuild, create=True),
        ):
            result = ensure_graph(tmp_path)

        assert result is None

    def test_logs_warning_on_rebuild_exception(self, tmp_path, caplog):
        import logging

        from ai_research_engineer.core.graphify import ensure_graph

        mock_rebuild = MagicMock(side_effect=RuntimeError("disk full"))

        with (
            patch("ai_research_engineer.core.graphify.graphify_available", return_value=True),
            patch("graphify.watch._rebuild_code", mock_rebuild, create=True),
            caplog.at_level(logging.WARNING, logger="ai_research_engineer.core.graphify"),
        ):
            ensure_graph(tmp_path)

        assert any("ensure_graph failed" in r.message for r in caplog.records)


# ---------------------------------------------------------------------------
# query_graph — fail-soft when graphify not available
# ---------------------------------------------------------------------------


class TestQueryGraphNotAvailable:
    def test_returns_none_when_package_missing(self, tmp_path):
        from ai_research_engineer.core.graphify import query_graph

        with patch("ai_research_engineer.core.graphify.graphify_available", return_value=False):
            result = query_graph(tmp_path, "What does main() do?")
        assert result is None


# ---------------------------------------------------------------------------
# query_graph — no graph file
# ---------------------------------------------------------------------------


class TestQueryGraphMissingFile:
    def test_returns_none_when_no_graph_json(self, tmp_path):
        from ai_research_engineer.core.graphify import query_graph

        with patch("ai_research_engineer.core.graphify.graphify_available", return_value=True):
            result = query_graph(tmp_path, "explain the code")
        assert result is None


# ---------------------------------------------------------------------------
# query_graph — success path
# ---------------------------------------------------------------------------


class TestQueryGraphSuccess:
    def _make_graph(self, tmp_path: Path) -> Path:
        graph_path = tmp_path / "graphify-out" / "graph.json"
        graph_path.parent.mkdir(parents=True)
        graph_path.write_text("{}")
        return graph_path

    def test_returns_stdout_on_success(self, tmp_path):
        from ai_research_engineer.core.graphify import query_graph

        self._make_graph(tmp_path)
        fake_proc = MagicMock()
        fake_proc.returncode = 0
        fake_proc.stdout = "  main() initialises the app\n"
        fake_proc.stderr = ""

        with (
            patch("ai_research_engineer.core.graphify.graphify_available", return_value=True),
            patch("subprocess.run", return_value=fake_proc) as mock_run,
        ):
            result = query_graph(tmp_path, "What does main() do?", budget=500)

        assert result == "main() initialises the app"
        # Verify subprocess args include the question and budget
        args = mock_run.call_args[0][0]
        assert "What does main() do?" in args
        assert "500" in args

    def test_returns_none_when_subprocess_fails(self, tmp_path):
        from ai_research_engineer.core.graphify import query_graph

        self._make_graph(tmp_path)
        fake_proc = MagicMock()
        fake_proc.returncode = 1
        fake_proc.stdout = ""
        fake_proc.stderr = "error: graphify crashed"

        with (
            patch("ai_research_engineer.core.graphify.graphify_available", return_value=True),
            patch("subprocess.run", return_value=fake_proc),
        ):
            result = query_graph(tmp_path, "describe me", budget=100)

        assert result is None

    def test_returns_none_when_stdout_empty(self, tmp_path):
        from ai_research_engineer.core.graphify import query_graph

        self._make_graph(tmp_path)
        fake_proc = MagicMock()
        fake_proc.returncode = 0
        fake_proc.stdout = "   "
        fake_proc.stderr = ""

        with (
            patch("ai_research_engineer.core.graphify.graphify_available", return_value=True),
            patch("subprocess.run", return_value=fake_proc),
        ):
            result = query_graph(tmp_path, "question", budget=100)

        assert result is None

    def test_fail_soft_on_subprocess_exception(self, tmp_path):
        from ai_research_engineer.core.graphify import query_graph

        self._make_graph(tmp_path)

        with (
            patch("ai_research_engineer.core.graphify.graphify_available", return_value=True),
            patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="python", timeout=30)),
        ):
            result = query_graph(tmp_path, "question")

        assert result is None


# ---------------------------------------------------------------------------
# Flag threading: use_graphify in session state
# ---------------------------------------------------------------------------


class TestFlagThreading:
    def test_build_initial_state_includes_use_graphify_false(self):
        """AIEngineer._build_initial_state must include use_graphify in state."""
        from ai_research_engineer.core.api import AIEngineer

        eng = AIEngineer.__new__(AIEngineer)
        from ai_research_engineer.core.api import SessionConfig

        eng.config = SessionConfig(use_graphify=False)
        eng.working_dir = Path("/tmp/test")
        state = eng._build_initial_state("hello")
        assert "use_graphify" in state
        assert state["use_graphify"] is False

    def test_build_initial_state_includes_use_graphify_true(self):
        from ai_research_engineer.core.api import AIEngineer, SessionConfig

        eng = AIEngineer.__new__(AIEngineer)
        eng.config = SessionConfig(use_graphify=True)
        eng.working_dir = Path("/tmp/test")
        state = eng._build_initial_state("hello")
        assert state["use_graphify"] is True
