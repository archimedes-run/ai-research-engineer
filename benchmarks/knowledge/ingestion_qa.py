#!/usr/bin/env python3
"""Ingestion QA rubric (S1-8).

Runs the S1-2 ingestion pipeline over a set of arXiv papers (mixing HTML-native,
PDF-only, math-heavy, and table-heavy) and reports, per paper:

  * sections extracted (count),
  * whether a hyperparameter query
    ("hyperparameters OR learning rate OR training details") retrieves a section
    that contains a number, and in how many search calls (<= 2 is the target),
  * truncation events — the number of old-style truncation markers found in the
    ingested full text (must be 0 after S1-2).

Results are written to ``benchmarks/knowledge/results/ingestion_qa_<ts>.json``
and a summary table is printed.

Usage:
  uv run python -m benchmarks.knowledge.ingestion_qa            # live (default)
  uv run python -m benchmarks.knowledge.ingestion_qa --fixtures # offline
  uv run python -m benchmarks.knowledge.ingestion_qa --limit 5
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path

from ai_research_engineer.tools.ingestion import ingest_paper, read_paper, search_paper
from ai_research_engineer.tools.research_ops import download_paper


# Per-paper subprocess wall-clock guard (seconds). A huge paper that hangs or is
# OOM-killed fails only its own row, not the whole run.
_PER_PAPER_TIMEOUT_S = 240

# arXiv asks for ~3s between API requests; the PDF-fallback path hits their API,
# so we pace between papers and retry transient throttling.
_INTER_PAPER_DELAY_S = 4
_DOWNLOAD_RETRIES = 3
_RETRYABLE = ("429", "503", "timeout", "temporarily", "connection")


# A 15-paper set mixing HTML-native, PDF-fallback, math-heavy, and table-heavy.
DEFAULT_PAPERS = [
    ("1706.03762", "Attention Is All You Need", "html/table-heavy"),
    ("1810.04805", "BERT", "html"),
    ("1512.03385", "ResNet", "html/table-heavy"),
    ("1409.1556", "VGG", "html/table-heavy"),
    ("2005.14165", "GPT-3", "html/large"),
    ("1412.6980", "Adam", "math-heavy"),
    ("1406.2661", "GAN", "math-heavy"),
    ("1312.6114", "VAE (Auto-Encoding Variational Bayes)", "math-heavy"),
    ("2006.11239", "DDPM", "math-heavy"),
    ("1905.11946", "EfficientNet", "table-heavy"),
    ("2010.11929", "Vision Transformer", "table-heavy"),
    ("1502.03167", "Batch Normalization", "math/table"),
    ("1301.3781", "word2vec", "older/pdf-fallback"),
    ("1608.06993", "DenseNet", "table-heavy"),
    ("1611.03530", "Rethinking Generalization", "table-heavy"),
]

HYPERPARAM_QUERY = "hyperparameters OR learning rate OR training details"
REFINE_QUERY = "learning rate batch size epochs optimizer weight decay"

# Old-style truncation markers that S1-2 removed; any occurrence is a failure.
_TRUNCATION_MARKERS = ("[Content truncated", "Content truncated at", "40000", "40,000")

_HAS_NUMBER = re.compile(r"\d")


def _network_up() -> bool:
    import urllib.request

    try:
        urllib.request.urlopen("https://arxiv.org", timeout=6)
        return True
    except Exception:
        return False


def _count_truncation_events(paper_id: str, working_dir: str) -> int:
    """Count truncation markers in the ingested full text + a read_paper render."""
    events = 0
    full_md = Path(working_dir) / "literature" / paper_id / "full.md"
    texts = []
    if full_md.exists():
        texts.append(full_md.read_text(encoding="utf-8", errors="replace"))
    texts.append(read_paper(paper_id, working_dir))
    for text in texts:
        for marker in _TRUNCATION_MARKERS:
            events += text.count(marker)
    return events


def _hyperparam_answerable(paper_id: str, working_dir: str) -> tuple[bool, int]:
    """Return (answerable, calls_used). Answerable == a retrieved section with a
    number. First tries the rubric query; if that misses, one refined retry."""
    calls = 0
    for query in (HYPERPARAM_QUERY, REFINE_QUERY):
        calls += 1
        result = search_paper(paper_id, query, working_dir, top_k=3)
        if _HAS_NUMBER.search(result) and not result.startswith("Error"):
            return True, calls
        if calls >= 2:
            break
    return False, calls


def _run_paper(paper_id: str, working_dir: str, live: bool) -> dict:
    row = {"paper_id": paper_id, "sections": 0, "answerable": False,
           "calls": 0, "truncation_events": 0, "mode": "live" if live else "fixture",
           "error": None}
    try:
        if live:
            msg = download_paper(paper_id, working_dir)
            if msg.startswith("Error"):
                row["error"] = msg
                return row
        sections = ingest_paper(paper_id, working_dir)
        if not sections:
            row["error"] = "no sections (paper not downloaded?)"
            return row
        row["sections"] = len(sections)
        row["answerable"], row["calls"] = _hyperparam_answerable(paper_id, working_dir)
        row["truncation_events"] = _count_truncation_events(paper_id, working_dir)
    except Exception as exc:  # keep the harness resilient
        row["error"] = f"{type(exc).__name__}: {exc}"
    return row


def _stage_fixtures(working_dir: str) -> list[tuple[str, str, str]]:
    """Copy committed HTML/PDF fixtures into the working dir as pseudo-papers."""
    fixtures = Path(__file__).resolve().parents[2] / "tests" / "fixtures"
    lit = Path(working_dir) / "literature"
    lit.mkdir(parents=True, exist_ok=True)
    mapping = [
        ("sample_arxiv_long", "sample_arxiv_long.html", "fixture:BERT html (large)"),
        ("sample_arxiv", "sample_arxiv.html", "fixture:html"),
        ("sample_2page", "sample_2page.pdf", "fixture:pdf"),
    ]
    staged = []
    for pid, fname, tag in mapping:
        src = fixtures / fname
        if src.exists():
            shutil.copy(src, lit / f"{pid}{src.suffix}")
            staged.append((pid, tag, tag))
    return staged


def _run_paper_isolated(paper_id: str) -> dict:
    """Run one paper in a fresh subprocess so its memory is fully reclaimed and a
    single OOM/timeout fails only this row."""
    try:
        proc = subprocess.run(
            [sys.executable, "-m", "benchmarks.knowledge.ingestion_qa", "--single", paper_id],
            capture_output=True, text=True, timeout=_PER_PAPER_TIMEOUT_S,
        )
    except subprocess.TimeoutExpired:
        return {"paper_id": paper_id, "sections": 0, "answerable": False, "calls": 0,
                "truncation_events": 0, "mode": "live", "error": "timeout"}
    # The worker prints exactly one JSON line prefixed with RESULT: on success.
    for line in proc.stdout.splitlines():
        if line.startswith("RESULT:"):
            try:
                return json.loads(line[len("RESULT:"):])
            except Exception:
                break
    reason = "killed (oom/crash)" if proc.returncode in (137, -9) else f"worker exit {proc.returncode}"
    return {"paper_id": paper_id, "sections": 0, "answerable": False, "calls": 0,
            "truncation_events": 0, "mode": "live", "error": reason}


def run(papers: list[tuple[str, str, str]], live: bool) -> dict:
    working_dir = tempfile.mkdtemp(prefix="ingestion_qa_")
    started = time.time()
    if not live:
        staged = _stage_fixtures(working_dir)
        papers = [(pid, note, cat) for pid, note, cat in staged]

    rows = []
    for i, (pid, _title, _cat) in enumerate(papers):
        print(f"  ... {pid}", flush=True)
        if not live:
            rows.append(_run_paper(pid, working_dir, live))
            continue
        # Isolate each paper (memory reclaim + resilience to a single kill), and
        # retry transient arXiv throttling (429/503) with backoff.
        if i:
            time.sleep(_INTER_PAPER_DELAY_S)
        row = _run_paper_isolated(pid)
        for attempt in range(1, _DOWNLOAD_RETRIES):
            err = (row.get("error") or "").lower()
            if row["sections"] > 0 or not any(k in err for k in _RETRYABLE):
                break
            backoff = _INTER_PAPER_DELAY_S * (attempt + 1)
            print(f"      retry {pid} in {backoff}s ({row['error']})", flush=True)
            time.sleep(backoff)
            row = _run_paper_isolated(pid)
        rows.append(row)

    n = len(rows)
    summary = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "mode": "live" if live else "fixture",
        "elapsed_s": round(time.time() - started, 1),
        "n_papers": n,
        "sections_extracted": sum(1 for r in rows if r["sections"] > 0),
        "answerable_le_2_calls": sum(1 for r in rows if r["answerable"] and r["calls"] <= 2),
        "total_truncation_events": sum(r["truncation_events"] for r in rows),
        "rows": rows,
    }
    shutil.rmtree(working_dir, ignore_errors=True)
    return summary


def _print_table(summary: dict) -> None:
    print("\n=== Ingestion QA ===")
    print(f"mode={summary['mode']}  papers={summary['n_papers']}  elapsed={summary['elapsed_s']}s")
    print(f"{'paper_id':<14}{'sections':>9}{'answerable':>12}{'calls':>7}{'trunc':>7}  note")
    for r in summary["rows"]:
        note = r["error"] or ""
        print(f"{r['paper_id']:<14}{r['sections']:>9}{str(r['answerable']):>12}"
              f"{r['calls']:>7}{r['truncation_events']:>7}  {note}")
    n = summary["n_papers"]
    print(f"\nsections extracted:    {summary['sections_extracted']}/{n}  (target {n}/{n})")
    print(f"answerable <=2 calls:  {summary['answerable_le_2_calls']}/{n}  (target >=13/15)")
    print(f"truncation events:     {summary['total_truncation_events']}  (target 0)")


def main() -> None:
    ap = argparse.ArgumentParser(description="Stage 1 ingestion QA rubric (S1-8)")
    ap.add_argument("--fixtures", action="store_true", help="offline: run on committed fixtures")
    ap.add_argument("--limit", type=int, default=None, help="only the first N papers")
    ap.add_argument("--ids", nargs="*", help="override arXiv id list")
    ap.add_argument("--single", help="internal: run one paper live and print RESULT:<json>")
    args = ap.parse_args()

    # Worker mode: run one paper in this (isolated) process and emit one JSON line.
    if args.single:
        wd = tempfile.mkdtemp(prefix="ingestion_qa_single_")
        try:
            row = _run_paper(args.single, wd, live=True)
            print("RESULT:" + json.dumps(row), flush=True)
        finally:
            shutil.rmtree(wd, ignore_errors=True)
        return

    live = not args.fixtures and _network_up()
    if not args.fixtures and not live:
        print("[ingestion_qa] network down — falling back to fixtures")

    papers = DEFAULT_PAPERS
    if args.ids:
        papers = [(i, i, "custom") for i in args.ids]
    if args.limit:
        papers = papers[: args.limit]

    print(f"[ingestion_qa] mode={'live' if live else 'fixture'} papers={len(papers) if live else 'fixtures'}")
    summary = run(papers, live)

    out_dir = Path(__file__).resolve().parent / "results"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"ingestion_qa_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    out_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    _print_table(summary)
    print(f"\nwrote {out_path}")


if __name__ == "__main__":
    main()
