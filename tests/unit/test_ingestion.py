"""S1-2: section-aware paper ingestion v2 (no truncation).

Uses committed fixtures under tests/fixtures/ — no network in tests.
"""

import json
import shutil
from pathlib import Path

import numpy as np

from ai_research_engineer.tools import ingestion


FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"


def _working_dir_with(tmp_path, fixture_name, paper_id, ext):
    """Copy a fixture into <tmp>/literature/<paper_id>.<ext> and return the dir."""
    lit = tmp_path / "literature"
    lit.mkdir(parents=True, exist_ok=True)
    shutil.copy(FIXTURES / fixture_name, lit / f"{paper_id}.{ext}")
    return str(tmp_path)


# --------------------------------------------------------------------------- #
# arXiv HTML ingestion
# --------------------------------------------------------------------------- #
class TestHtmlIngestion:
    PAPER = "2401.00001"

    def _ingest(self, tmp_path):
        wd = _working_dir_with(tmp_path, "sample_arxiv.html", self.PAPER, "html")
        return wd, ingestion.ingest_paper(self.PAPER, wd)

    def test_sections_json_structure(self, tmp_path):
        wd, sections = self._ingest(tmp_path)
        assert isinstance(sections, list) and sections
        for s in sections:
            assert set(s.keys()) == {"section_path", "title", "markdown"}
            assert isinstance(s["section_path"], list) and s["section_path"]
            assert isinstance(s["title"], str)
            assert isinstance(s["markdown"], str)
        titles = [s["title"] for s in sections]
        assert "Abstract" in titles
        assert any("Experiments" in t for t in titles)

        # Persisted to disk exactly as returned.
        on_disk = json.loads((Path(wd) / "literature" / self.PAPER / "sections.json").read_text())
        assert on_disk == sections
        assert (Path(wd) / "literature" / self.PAPER / "full.md").exists()

    def test_markdown_table_survives(self, tmp_path):
        _, sections = self._ingest(tmp_path)
        all_md = "\n".join(s["markdown"] for s in sections)
        assert "| Model | Accuracy |" in all_md
        assert "| Baseline | 0.72 |" in all_md
        assert "| Ours | 0.91 |" in all_md

    def test_latex_equation_survives_verbatim(self, tmp_path):
        _, sections = self._ingest(tmp_path)
        all_md = "\n".join(s["markdown"] for s in sections)
        # The exact LaTeX from the <math alttext="..."> must be preserved inline.
        assert r"\mathcal{L} = -\sum_i y_i \log \hat{y}_i" in all_md

    def test_read_paper_toc_mode_not_a_blob(self, tmp_path):
        wd, _ = self._ingest(tmp_path)
        out = ingestion.read_paper(self.PAPER, wd)  # no section -> TOC mode
        assert "Table of contents" in out
        assert "Abstract" in out
        assert "TRUNCATED" not in out
        # A table of contents + abstract + first section is compact, not a 40k blob.
        assert len(out) < 5000

    def test_read_paper_returns_only_requested_section(self, tmp_path):
        wd, _ = self._ingest(tmp_path)
        out = ingestion.read_paper(self.PAPER, wd, section="experiments")
        assert out.startswith("# ") and "Experiments" in out.splitlines()[0]
        assert "91%" in out
        # Content from OTHER sections must not leak in.
        assert "PLANTED_UNIQUE_TOKEN_XYZ" not in out  # that lives in the Method section
        assert "Introduction" not in out

    def test_search_paper_finds_planted_string(self, tmp_path, monkeypatch):
        wd = _working_dir_with(tmp_path, "sample_arxiv.html", self.PAPER, "html")

        # Deterministic offline embeddings: the planted marker gets a distinct
        # vector so the chunk containing it is the nearest neighbour of the query.
        def fake_embed(texts, model_name=None):
            token = "PLANTED_UNIQUE_TOKEN_XYZ"
            return np.array([[1.0, 0.0] if token in t else [0.0, 1.0] for t in texts], dtype=np.float32)

        monkeypatch.setattr("ai_research_engineer.core.embeddings.embed_texts", fake_embed)

        out = ingestion.search_paper(self.PAPER, "PLANTED_UNIQUE_TOKEN_XYZ", wd, top_k=3)
        assert "PLANTED_UNIQUE_TOKEN_XYZ" in out
        # Index was cached under literature/<paper_id>/index/.
        assert (Path(wd) / "literature" / self.PAPER / "index" / "chunks.json").exists()


# --------------------------------------------------------------------------- #
# PDF ingestion (pymupdf4llm, not PyPDF2)
# --------------------------------------------------------------------------- #
class TestPdfIngestion:
    PAPER = "2402.02222"

    def test_pdf_ingestion_sections_and_no_truncation(self, tmp_path):
        wd = _working_dir_with(tmp_path, "sample_2page.pdf", self.PAPER, "pdf")
        sections = ingestion.ingest_paper(self.PAPER, wd)
        assert sections, "PDF should yield at least one section"
        titles = " ".join(s["title"] for s in sections)
        assert "Introduction" in titles and "Experiments" in titles
        all_md = "\n".join(s["markdown"] for s in sections)
        assert "PDF_PLANTED_MARKER_42" in all_md

        out = ingestion.read_paper(self.PAPER, wd)
        assert "Table of contents" in out
        assert "TRUNCATED" not in out


# --------------------------------------------------------------------------- #
# The 40k truncation stripper is gone
# --------------------------------------------------------------------------- #
def test_40000_truncation_removed_from_research_ops():
    research_ops = Path(ingestion.__file__).parent / "research_ops.py"
    text = research_ops.read_text(encoding="utf-8")
    assert "40000" not in text, "the 40000-char truncation must be gone from research_ops"
    assert "PyPDF2" not in text, "PyPDF2 path must be gone from research_ops"
