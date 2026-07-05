"""S2-7: novelty benchmark harness + datasets."""

import re
from pathlib import Path

from benchmarks.novelty import run_novelty_bench as B


_DATASETS = Path("benchmarks/novelty/datasets")


def _shingles(text, n=8):
    """Set of n-word verbatim spans (normalized: lowercased, alnum-only)."""
    words = re.sub(r"[^a-z0-9]+", " ", (text or "").lower()).split()
    return {" ".join(words[i : i + n]) for i in range(len(words) - n + 1)}


# --------------------------------------------------------------------------- #
# Dataset schema + composition
# --------------------------------------------------------------------------- #
def test_known_50_schema_and_composition():
    _, rows = B.load_dataset(_DATASETS / "known_50.jsonl")
    assert len(rows) == 50
    assert B.validate_rows(rows, "known") == []  # every row well-formed
    from collections import Counter

    cats = Counter(r["category"] for r in rows)
    assert cats["canonical"] == 25 and cats["recent"] == 15 and cats["code_only"] == 10
    # descriptions must not be trivially empty / must be paraphrase-length
    assert all(len(r["idea_description"]) > 40 for r in rows)


def test_plausible_dataset_is_draft_pending_expansion():
    header, rows = B.load_dataset(_DATASETS / "plausible_30.jsonl")
    # After review, 22 rows had prior art and 4 were close-calls, leaving 4
    # high-confidence-open rows. The set is DRAFT (not signed off) and must be
    # expanded by the maintainer to a robust N before any FRR is reported.
    assert B.signed_off(header) is False           # blocks the live run
    assert header.get("confident_count") == len(rows)
    assert B.validate_rows(rows, "plausible") == []  # the remaining rows are well-formed
    assert all(r.get("rationale") and r.get("confidence") for r in rows)


# --------------------------------------------------------------------------- #
# Metrics arithmetic on a synthetic result set
# --------------------------------------------------------------------------- #
def test_metrics_recall_and_frr():
    results = [
        {
            "ground_truth": "reject",
            "category": "canonical",
            "predicted": "reject",
            "channel": "openalex",
            "cost_usd": 0.1,
            "latency_s": 1.0,
        },
        {
            "ground_truth": "reject",
            "category": "canonical",
            "predicted": "approve",
            "channel": None,
            "cost_usd": 0.1,
            "latency_s": 1.0,
        },
        {
            "ground_truth": "reject",
            "category": "code_only",
            "predicted": "reject",
            "channel": "github",
            "cost_usd": 0.1,
            "latency_s": 1.0,
        },
        {"ground_truth": "approve", "category": "open", "predicted": "approve", "cost_usd": 0.1, "latency_s": 1.0},
        {"ground_truth": "approve", "category": "open", "predicted": "reject", "cost_usd": 0.1, "latency_s": 1.0},
    ]
    m = B.compute_metrics(results)
    assert m["rejection_recall_known"] == 0.6667  # 2/3 known rejected
    assert m["per_category_recall"]["canonical"] == {"n": 2, "recall": 0.5}
    assert m["per_category_recall"]["code_only"] == {"n": 1, "recall": 1.0}
    assert m["false_rejection_rate_plausible"] == 0.5  # 1/2 plausible wrongly rejected
    assert m["channel_attribution"] == {"openalex": 1, "github": 1}
    assert m["cost_usd_total"] == 0.5
    assert m["cost_usd_per_idea"] == 0.1


# --------------------------------------------------------------------------- #
# Budget halt — persist completed rows, status budget_halted
# --------------------------------------------------------------------------- #
def test_budget_halt_persists_completed_rows():
    rows = [{"id": f"r{i}", "ground_truth": "reject"} for i in range(10)]

    # fake pricing counter: each row costs $0.30 -> cumulative crosses $1.00 at row 4
    def engine(row):
        return {
            "id": row["id"],
            "ground_truth": "reject",
            "category": "c",
            "predicted": "reject",
            "correct": True,
            "channel": "openalex",
            "cost_usd": 0.30,
            "latency_s": 0.0,
        }

    run = B.run_benchmark(rows, engine, budget_usd=1.00)
    assert run["status"] == "budget_halted"
    assert run["rows_completed"] == 4  # 0.30*4 = 1.20 >= 1.00, halted
    assert run["rows_completed"] < len(rows)  # did NOT run everything
    assert len(run["results"]) == 4  # partial results persisted (valid)
    assert run["total_cost_usd"] >= 1.00

    # no budget -> runs all
    assert B.run_benchmark(rows, engine)["rows_completed"] == 10


# --------------------------------------------------------------------------- #
# Stratified subsample keeps per-category proportions
# --------------------------------------------------------------------------- #
def test_stratified_subsample_keeps_proportions():
    rows = (
        [{"ground_truth": "reject", "category": "canonical"} for _ in range(25)]
        + [{"ground_truth": "reject", "category": "recent"} for _ in range(15)]
        + [{"ground_truth": "reject", "category": "code_only"} for _ in range(10)]
        + [{"ground_truth": "approve", "category": "open"} for _ in range(30)]
    )  # 80 rows, proportions 25/15/10/30
    sub = B.stratified_subsample(rows, 16)  # ~1/5 of each stratum
    from collections import Counter

    cats = Counter((r["ground_truth"], r["category"]) for r in sub)
    assert cats[("reject", "canonical")] == 5  # 25 * 16/80
    assert cats[("reject", "recent")] == 3  # 15 * 16/80
    assert cats[("reject", "code_only")] == 2  # 10 * 16/80
    assert cats[("approve", "open")] == 6  # 30 * 16/80
    assert len(sub) == 16


# --------------------------------------------------------------------------- #
# CI-lite end-to-end on fixtures + model recorded in header
# --------------------------------------------------------------------------- #
def test_ci_lite_end_to_end_plumbing():
    rows = B._ci_lite_rows()
    assert len(rows) == 8  # 5 KNOWN + 3 PLAUSIBLE
    engine = B.make_ci_lite_engine(k=3)
    run = B.run_benchmark(rows, engine)
    # plumbing: every prediction matches ground truth (known->reject, plausible->approve)
    assert all(r["correct"] for r in run["results"]), [r["id"] for r in run["results"] if not r["correct"]]
    m = B.compute_metrics(run["results"])
    assert m["rejection_recall_known"] == 1.0
    assert m["false_rejection_rate_plausible"] == 0.0


def test_no_verbatim_leakage_idea_vs_killing_abstract():
    """Each KNOWN idea_description must PARAPHRASE — no 8-word verbatim span from
    the killing work's abstract may appear in it. Rows without an abstract in the
    row (code-only repos, and a few venues whose abstract isn't cleanly fetchable)
    are skipped with a recorded reason."""
    _, rows = B.load_dataset(_DATASETS / "known_50.jsonl")
    leaks, checked, skipped = [], 0, {}
    for r in rows:
        abstract = (r.get("killing_work") or {}).get("abstract")
        if not abstract:
            skipped[r["id"]] = (
                "code-only: no flagship-paper abstract"
                if "github.com" in r["killing_work"]["url"]
                else "killing-work abstract unavailable for this venue"
            )
            continue
        checked += 1
        overlap = _shingles(r["idea_description"]) & _shingles(abstract)
        if overlap:
            leaks.append((r["id"], sorted(overlap)))

    assert not leaks, f"verbatim 8-word leakage between idea and killing-work abstract: {leaks}"
    # Not vacuous: the large majority of KNOWN rows are actually checked.
    assert checked >= 30, f"only {checked} rows carry an abstract — guard is too weak"
    assert all(skipped.values()), "every skipped row must record a reason"


def test_model_recorded_in_result_header():
    run = {"status": "completed", "rows_completed": 0, "rows_total": 0, "results": []}
    result = B.build_result(run, model="anthropic/claude-x", mode="full", args={"budget_usd": 5.0})
    assert result["model"] == "anthropic/claude-x"  # no number without its model
    assert result["mode"] == "full"
    assert result["budget_usd"] == 5.0
    assert "metrics" in result
