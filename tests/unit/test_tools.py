"""
Unit tests for tools module.

Tests all file operations, web fetch, database operations,
academic research tools (Semantic Scholar, ArXiv, findpapers),
and code graph functionality (Graphify).
Includes security boundary validation and edge cases.
"""

import base64
import json
from unittest.mock import MagicMock, Mock, patch

import pytest

from ai_research_engineer.tools import (
    build_citation_graph,
    build_knowledge_graph,
    compile_latex_to_pdf,
    directory_tree,
    fetch_url,
    get_file_info,
    get_paper_details,
    list_directory,
    omni_search_papers,
    query_code_structure,
    query_duckdb,
    read_file,
    read_media_file,
    search_files,
    semantic_search_papers,
)


@pytest.fixture
def temp_workspace(tmp_path):
    """
    Create a temporary workspace with test files.

    Returns
    -------
    Path
        Path to temporary workspace directory
    """
    # Create directory structure
    (tmp_path / "subdir").mkdir()
    (tmp_path / "subdir" / "nested").mkdir()
    (tmp_path / "knowledge_base").mkdir()

    # Create text files
    (tmp_path / "test.txt").write_text("Hello, world!")
    (tmp_path / "data.csv").write_text("name,value\nalice,100\nbob,200")
    (tmp_path / "subdir" / "nested" / "deep.txt").write_text("Deep content")

    # Create a file with multiple lines for head/tail testing
    lines = [f"Line {i}" for i in range(1, 11)]
    (tmp_path / "multiline.txt").write_text("\n".join(lines))

    # Create a binary file (simple image-like data)
    binary_data = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"
    (tmp_path / "image.png").write_bytes(binary_data)

    # Create Python files for search testing
    (tmp_path / "main.py").write_text("print('main')")
    (tmp_path / "subdir" / "utils.py").write_text("print('utils')")

    return tmp_path


# ==========================================
# FILE OPS TESTS
# ==========================================


class TestReadFile:
    """Tests for read_file function."""

    def test_read_file_success(self, temp_workspace):
        result = read_file("test.txt", str(temp_workspace))
        assert result == "Hello, world!"

    def test_read_file_with_path_in_subdir(self, temp_workspace):
        result = read_file("subdir/nested/deep.txt", str(temp_workspace))
        assert result == "Deep content"

    def test_read_file_head(self, temp_workspace):
        result = read_file("multiline.txt", str(temp_workspace), head=3)
        expected = "Line 1\nLine 2\nLine 3"
        assert result == expected

    def test_read_file_tail(self, temp_workspace):
        result = read_file("multiline.txt", str(temp_workspace), tail=3)
        expected = "Line 8\nLine 9\nLine 10"
        assert result == expected

    def test_read_file_nonexistent(self, temp_workspace):
        result = read_file("missing.txt", str(temp_workspace))
        assert "Error" in result

    def test_read_file_directory(self, temp_workspace):
        result = read_file("subdir", str(temp_workspace))
        assert "Error" in result

    def test_read_file_outside_working_dir(self, temp_workspace):
        result = read_file("../outside.txt", str(temp_workspace))
        assert "Error" in result
        assert "outside" in result.lower()


class TestReadMediaFile:
    """Tests for read_media_file function."""

    def test_read_media_file_success(self, temp_workspace):
        result = read_media_file("image.png", str(temp_workspace))
        data = json.loads(result)
        assert "data" in data
        assert data["mimeType"] == "image/png"
        decoded = base64.b64decode(data["data"])
        assert decoded.startswith(b"\x89PNG")

    def test_read_media_file_outside_working_dir(self, temp_workspace):
        result = read_media_file("../outside.png", str(temp_workspace))
        assert "Error" in result


class TestListDirectory:
    """Tests for list_directory function."""

    def test_list_directory_success(self, temp_workspace):
        result = list_directory(".", str(temp_workspace))
        assert "[FILE]" in result
        assert "[DIR]" in result
        assert "test.txt" in result

    def test_list_directory_outside_working_dir(self, temp_workspace):
        result = list_directory("..", str(temp_workspace))
        assert "Error" in result


class TestDirectoryTree:
    """Tests for directory_tree function."""

    def test_directory_tree_success(self, temp_workspace):
        result = directory_tree(".", str(temp_workspace))
        tree = json.loads(result)
        assert isinstance(tree, list)
        assert len(tree) > 0

    def test_directory_tree_with_exclusions(self, temp_workspace):
        result = directory_tree(".", str(temp_workspace), exclude_patterns=["*.png", "__pycache__"])
        assert "image.png" not in result


class TestSearchFiles:
    """Tests for search_files function."""

    def test_search_files_success(self, temp_workspace):
        result = search_files("*.py", str(temp_workspace))
        assert "main.py" in result
        assert "utils.py" in result


class TestGetFileInfo:
    """Tests for get_file_info function."""

    def test_get_file_info_success(self, temp_workspace):
        result = get_file_info("test.txt", str(temp_workspace))
        assert "name: test.txt" in result
        assert "type: file" in result


class TestFetchUrl:
    """Tests for fetch_url function."""

    @patch("ai_research_engineer.tools.web_ops.requests.get")
    @patch("ai_research_engineer.tools.web_ops.socket.getaddrinfo")
    def test_fetch_url_success(self, mock_dns, mock_get):
        import socket

        # Resolve to a public address so SSRF check passes
        mock_dns.return_value = [(socket.AF_INET, None, None, "", ("93.184.216.34", 0))]
        mock_response = Mock()
        mock_response.text = "Success content"
        mock_response.is_redirect = False
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response
        result = fetch_url("https://example.com")
        assert result == "Success content"

    @patch("ai_research_engineer.tools.web_ops.socket.getaddrinfo")
    def test_fetch_url_blocks_loopback(self, mock_dns):
        import socket

        mock_dns.return_value = [(socket.AF_INET, None, None, "", ("127.0.0.1", 0))]
        result = fetch_url("http://localhost/admin")
        assert "Error" in result
        assert "blocked" in result.lower()

    @patch("ai_research_engineer.tools.web_ops.socket.getaddrinfo")
    def test_fetch_url_blocks_metadata_endpoint(self, mock_dns):
        import socket

        # AWS/GCP metadata IP
        mock_dns.return_value = [(socket.AF_INET, None, None, "", ("169.254.169.254", 0))]
        result = fetch_url("http://169.254.169.254/latest/meta-data/")
        assert "Error" in result
        assert "blocked" in result.lower()

    @patch("ai_research_engineer.tools.web_ops.socket.getaddrinfo")
    def test_fetch_url_blocks_private_range(self, mock_dns):
        import socket

        mock_dns.return_value = [(socket.AF_INET, None, None, "", ("192.168.1.1", 0))]
        result = fetch_url("http://192.168.1.1/internal")
        assert "Error" in result
        assert "blocked" in result.lower()

    @patch("ai_research_engineer.tools.web_ops.requests.get")
    @patch("ai_research_engineer.tools.web_ops.socket.getaddrinfo")
    def test_fetch_url_redirect_to_private_blocked(self, mock_dns, mock_get):
        """A public URL that 302-redirects to a private address must be blocked."""
        import socket

        # First DNS call is for the public host (safe), second for the redirect target
        public_addr = [(socket.AF_INET, None, None, "", ("93.184.216.34", 0))]
        private_addr = [(socket.AF_INET, None, None, "", ("10.0.0.1", 0))]
        mock_dns.side_effect = [public_addr, private_addr]

        redirect_resp = Mock()
        redirect_resp.is_redirect = True
        redirect_resp.headers = {"Location": "http://10.0.0.1/secret"}
        mock_get.return_value = redirect_resp

        result = fetch_url("https://example.com/redirect")
        assert "Error" in result
        assert "blocked" in result.lower()


class TestSecurityValidation:
    """Additional security-focused tests."""

    def test_symlink_escape_attempt(self, temp_workspace):
        outside_dir = temp_workspace.parent / "outside"
        outside_dir.mkdir(exist_ok=True)
        (outside_dir / "secret.txt").write_text("secret")

        symlink_path = temp_workspace / "escape_link"
        symlink_path.symlink_to(outside_dir / "secret.txt")

        result = read_file("escape_link", str(temp_workspace))
        assert "Error" in result or "secret" not in result

    def test_absolute_path_within_working_dir(self, temp_workspace):
        test_file = temp_workspace / "test.txt"
        result = read_file(str(test_file), str(temp_workspace))
        assert result == "Hello, world!"


# ==========================================
# DATA OPS TESTS (DuckDB)
# ==========================================


class TestDataOps:
    """Tests for DuckDB data operations."""

    @patch("ai_research_engineer.tools.data_ops.duckdb.connect")
    def test_query_duckdb_success(self, mock_connect, temp_workspace):
        """A plain SELECT passes validation and is forwarded to DuckDB."""
        mock_con = MagicMock()
        mock_df = MagicMock()
        mock_df.to_markdown.return_value = "| name | value |\n|---|---|\n| alice | 100 |"
        mock_df.__len__.return_value = 2
        mock_con.execute.return_value.fetchdf.return_value = mock_df
        mock_connect.return_value = mock_con

        result = query_duckdb("SELECT * FROM 'data.csv'", str(temp_workspace))

        assert "alice" in result
        # The SELECT call itself (not the SET calls) must contain LIMIT
        select_calls = [call for call in mock_con.execute.call_args_list if "SELECT" in str(call).upper()]
        assert any("LIMIT 1000" in str(c) for c in select_calls)

    def test_query_duckdb_drop_rejected(self, temp_workspace):
        result = query_duckdb("DROP TABLE data", str(temp_workspace))
        assert "Error" in result

    def test_query_duckdb_delete_rejected(self, temp_workspace):
        result = query_duckdb("DELETE FROM data WHERE id=1", str(temp_workspace))
        assert "Error" in result

    def test_query_duckdb_copy_to_rejected(self, temp_workspace):
        """COPY ... TO is a data-exfiltration vector and must be rejected."""
        result = query_duckdb("COPY data TO '/tmp/out.csv'", str(temp_workspace))
        assert "Error" in result

    def test_query_duckdb_attach_rejected(self, temp_workspace):
        result = query_duckdb("ATTACH '/etc/shadow' AS s", str(temp_workspace))
        assert "Error" in result

    def test_query_duckdb_absolute_path_rejected(self, temp_workspace):
        """Absolute file paths in query strings are rejected."""
        result = query_duckdb("SELECT * FROM '/etc/passwd'", str(temp_workspace))
        assert "Error" in result

    def test_query_duckdb_column_with_create_not_rejected(self, temp_workspace):
        """
        Regression: a WHERE clause filtering on a value that contains 'CREATE'
        (e.g. column_name = 'date_created') must NOT be rejected.
        The old substring blocklist would have false-positived here.
        """
        from ai_research_engineer.tools.data_ops import _validate_query

        # The first keyword is SELECT — validator must accept this.
        err = _validate_query("SELECT * FROM t WHERE col = 'date_created' LIMIT 5")
        assert err is None, f"Unexpected rejection: {err}"

    def test_query_duckdb_with_clause_allowed(self, temp_workspace):
        """WITH ... SELECT is a valid read-only construct."""
        from ai_research_engineer.tools.data_ops import _validate_query

        err = _validate_query("WITH cte AS (SELECT 1 AS x) SELECT * FROM cte")
        assert err is None, f"Unexpected rejection: {err}"


# ==========================================
# SEMANTIC SCHOLAR OPS TESTS
# ==========================================


class TestSemanticScholarOps:
    """Tests for Semantic Scholar integrations."""

    @patch("ai_research_engineer.tools.semantic_scholar_ops.sch")
    def test_semantic_search_papers(self, mock_sch, temp_workspace):
        mock_paper = MagicMock(
            paperId="123",
            title="AI Test",
            year=2024,
            citationCount=50,
            abstract="Test abstract",
            url="http://test.com",
            citationStyles=None,
            authors=[],
        )
        mock_sch.search_paper.return_value = [mock_paper]

        result = semantic_search_papers("AI testing", min_citations=10, limit=1, working_dir=str(temp_workspace))
        parsed = json.loads(result)

        assert len(parsed) == 1
        assert parsed[0]["title"] == "AI Test"

        # Verify tracking file was created
        track_file = temp_workspace / ".tracked_papers.json"
        assert track_file.exists()

    @patch("ai_research_engineer.tools.semantic_scholar_ops.sch")
    def test_get_paper_details(self, mock_sch, temp_workspace):
        mock_paper = MagicMock(
            paperId="123",
            title="Detailed Paper",
            year=2024,
            citationCount=10,
            referenceCount=5,
            influentialCitationCount=2,
            abstract="Abstract",
            tldr=None,
            authors=[],
            url="",
            citationStyles=None,
        )
        mock_sch.get_paper.return_value = mock_paper

        result = get_paper_details("123", str(temp_workspace))
        parsed = json.loads(result)

        assert parsed["title"] == "Detailed Paper"
        assert parsed["references"] == 5


# ==========================================
# RESEARCH OPS TESTS (ArXiv / findpapers)
# ==========================================


class TestResearchOps:
    """Tests for advanced research tools."""

    def test_omni_search_papers(self, mock_search_paper):
        # Mock Semantic Scholar response for omni search
        mock_author = MagicMock()
        mock_author.name = "Author A"

        mock_paper = MagicMock(
            title="Omni Test Paper", year=2025, abstract="Omni abstract", venue="arXiv", url="http://arxiv.org/123"
        )
        mock_paper.authors = [mock_author]
        mock_search_paper.return_value = [mock_paper]

        result = omni_search_papers("test query", limit=1)
        parsed = json.loads(result)

        assert parsed[0]["title"] == "Omni Test Paper"
        assert parsed[0]["venue"] == "arXiv"
        mock_search_paper.assert_called_once()

    @patch("ai_research_engineer.tools.research_ops.sch")
    def test_build_citation_graph(self, mock_sch, temp_workspace):
        mock_paper = MagicMock(title="Root Paper", year=2023)
        mock_paper.references = [MagicMock(title="Ancestor 1", paperId="A1")]
        mock_paper.citations = [MagicMock(title="Descendant 1", paperId="D1")]
        mock_sch.get_paper.return_value = mock_paper

        result = build_citation_graph("123", str(temp_workspace))

        assert "Citation Graph: Root Paper" in result
        assert "Ancestor 1" in result
        assert "Descendant 1" in result

        # Verify it saved to knowledge_base
        kb_file = temp_workspace / "knowledge_base" / "citation_graph_123.md"
        assert kb_file.exists()


# ==========================================
# CODE GRAPH OPS TESTS (Graphify)
# ==========================================


class TestCodeGraphOps:
    """Tests for Graphify AST codebase analysis."""

    @patch("ai_research_engineer.tools.code_graph_ops.subprocess.run")
    def test_build_knowledge_graph_success(self, mock_run, temp_workspace):
        """Test successful graphify execution."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_run.return_value = mock_result

        # Fake the graphify output file so the function thinks it succeeded
        out_dir = temp_workspace / "graphify-out"
        out_dir.mkdir()
        (out_dir / "GRAPH_REPORT.md").write_text("Graph Report")

        result = build_knowledge_graph(str(temp_workspace))

        assert "Graph built successfully" in result
        assert "CRITICAL" in result
        mock_run.assert_called_with(
            ["graphify", "--no-viz"], cwd=str(temp_workspace), capture_output=True, text=True, check=False
        )

    @patch("ai_research_engineer.tools.code_graph_ops.subprocess.run")
    def test_build_knowledge_graph_failure(self, mock_run, temp_workspace):
        """Test graphify failure."""
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stderr = "Command not found"
        mock_run.return_value = mock_result

        result = build_knowledge_graph(str(temp_workspace))
        assert "Error building graph" in result

    @patch("ai_research_engineer.tools.code_graph_ops.subprocess.run")
    def test_query_code_structure_path(self, mock_run, temp_workspace):
        """Test query routing for 'Path between A and B'."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "Path traces..."
        mock_run.return_value = mock_result

        result = query_code_structure("Path between", "ModelA and ModelB", str(temp_workspace))

        assert "Path traces" in result
        # Verify it used the 'path' command due to the 'and' keyword
        args = mock_run.call_args[0][0]
        assert "path" in args
        assert "modela" in args
        assert "modelb" in args


# ==========================================
# LATEX OPS TESTS
# ==========================================


class TestLatexOps:
    """Tests for LaTeX compilation tool."""

    def test_compile_missing_file(self, temp_workspace):
        """Returns error when .tex file does not exist."""
        (temp_workspace / "manuscript").mkdir(exist_ok=True)
        result = compile_latex_to_pdf("nonexistent.tex", str(temp_workspace))
        assert "Error: Could not find" in result

    @patch("ai_research_engineer.tools.latex_ops.subprocess.run")
    def test_compile_success(self, mock_run, temp_workspace):
        """Returns SUCCESS when both pdflatex passes succeed and PDF is produced."""
        manuscript_dir = temp_workspace / "manuscript"
        manuscript_dir.mkdir(exist_ok=True)
        results_dir = temp_workspace / "results"
        results_dir.mkdir(exist_ok=True)

        # Create a fake .tex and the expected output PDF
        (manuscript_dir / "main.tex").write_text(r"\documentclass{article}\begin{document}Hello\end{document}")
        (manuscript_dir / "main.pdf").write_bytes(b"%PDF-1.4")

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_run.return_value = mock_result

        result = compile_latex_to_pdf("main.tex", str(temp_workspace))

        assert "SUCCESS" in result
        assert "final_research_paper.pdf" in result
        # PDF should have been copied to results/
        assert (results_dir / "final_research_paper.pdf").exists()
        # pdflatex is called twice
        assert mock_run.call_count == 2

    @patch("ai_research_engineer.tools.latex_ops.subprocess.run")
    def test_compile_failure_on_first_pass(self, mock_run, temp_workspace):
        """Returns FAILED message with error log snippet when pdflatex exits non-zero."""
        manuscript_dir = temp_workspace / "manuscript"
        manuscript_dir.mkdir(exist_ok=True)
        (manuscript_dir / "main.tex").write_text(r"\bad syntax")

        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = "\n".join([f"log line {i}" for i in range(30)])
        mock_run.return_value = mock_result

        result = compile_latex_to_pdf("main.tex", str(temp_workspace))

        assert "FAILED" in result
        assert "pass 1" in result
        assert "fix the syntax errors" in result
