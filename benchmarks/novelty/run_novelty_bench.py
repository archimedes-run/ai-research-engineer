#!/usr/bin/env python3
"""Novelty benchmark harness (S2-7).

Runs the full novelty engine (recall -> prefilter -> differentiate -> falsify)
against KNOWN-50 (ground truth reject) and PLAUSIBLE (ground truth approve)
and reports rejection recall, false-rejection rate, per-channel attribution,
cost, and latency. Two modes:

  * full  (default) — live LLM engine (NOT run in CI or S2-7; that is CC-2.7),
  * --ci-lite       — 5 KNOWN + 3 PLAUSIBLE, offline, canned outputs, asserts
                      the pipeline plumbing end-to-end (not the quality numbers).

Cost controls:
  --dry-run            report estimated cost + KNOWN/PLAUSIBLE row breakdown for
                       the current selection, then exit WITHOUT any LLM/search
                       call. With --budget-usd, prints margin and exits nonzero
                       if the estimate exceeds the cap (config sanity-check).
  --budget-usd CAP     halt cleanly at the cap; completed rows are persisted and
                       the result is marked status="budget_halted" (valid result).
  --subsample N        run N rows, --stratified keeps per-category proportions.
  --model-override M    scorer+falsifier model for the run; RECORDED in the header
                       so no number is ever reported without its model attached.

Every reported metric carries the model + mode in the result header.
"""

from __future__ import annotations

import argparse
import json
import time
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Callable, List, Optional


_HERE = Path(__file__).resolve().parent
_DATASETS = _HERE / "datasets"
_RESULTS = _HERE / "results"

CI_LITE_KNOWN = ["k_attention", "k_bert", "r_mamba", "c_llamacpp", "r_dpo"]
CI_LITE_PLAUSIBLE = ["p_ctx_forgetting", "p_curriculum_from_loss_geometry", "p_crossmodal_grokking"]

# --dry-run sanity-check only. NOT a price model: during a real run the cost
# harness reports true per-row spend. $0.55 matches the budget-mode target.
EXPECTED_COST_PER_ROW = 0.55

_REQUIRED_KNOWN_FIELDS = ("id", "idea_title", "idea_description", "ground_truth", "killing_work", "category")
_REQUIRED_PLAUSIBLE_FIELDS = ("id", "idea_title", "idea_description", "ground_truth", "confidence", "rationale")


# --------------------------------------------------------------------------- #
# Dataset loading + validation
# --------------------------------------------------------------------------- #
def load_dataset(path: Path) -> tuple[dict, List[dict]]:
    """Return (header, rows). A leading ``{"__meta__": true, ...}`` line is the
    header (e.g. the PLAUSIBLE DRAFT/SIGNED_OFF flag); everything else is rows."""
    header: dict = {}
    rows: List[dict] = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        obj = json.loads(line)
        if obj.get("__meta__"):
            header = obj
        else:
            rows.append(obj)
    return header, rows


def validate_rows(rows: List[dict], kind: str) -> List[str]:
    """Return a list of schema problems (empty == valid)."""
    required = _REQUIRED_KNOWN_FIELDS if kind == "known" else _REQUIRED_PLAUSIBLE_FIELDS
    want_gt = "reject" if kind == "known" else "approve"
    problems = []
    for r in rows:
        for f in required:
            if not r.get(f):
                problems.append(f"{r.get('id', '?')}: missing {f}")
        if r.get("ground_truth") != want_gt:
            problems.append(f"{r.get('id', '?')}: ground_truth must be {want_gt}")
        if kind == "known" and not (r.get("killing_work") or {}).get("url"):
            problems.append(f"{r.get('id', '?')}: killing_work.url missing")
    return problems


def signed_off(header: dict) -> bool:
    return bool(header.get("SIGNED_OFF"))


# --------------------------------------------------------------------------- #
# Stratified subsampling (ablation runs)
# --------------------------------------------------------------------------- #
def _stratum(row: dict) -> tuple:
    return (row.get("ground_truth"), row.get("category", "open"))


def stratified_subsample(rows: List[dict], n: int) -> List[dict]:
    """Proportional subset across (ground_truth, category) strata."""
    if n >= len(rows):
        return list(rows)
    groups: dict = defaultdict(list)
    for r in rows:
        groups[_stratum(r)].append(r)
    total = len(rows)
    out: List[dict] = []
    for _key, grp in groups.items():
        take = max(1, round(n * len(grp) / total)) if grp else 0
        out.extend(grp[:take])
    # Trim any rounding overshoot deterministically.
    return out[:n] if len(out) > n else out


# --------------------------------------------------------------------------- #
# Metrics
# --------------------------------------------------------------------------- #
def compute_metrics(results: List[dict]) -> dict:
    known = [r for r in results if r["ground_truth"] == "reject"]
    plausible = [r for r in results if r["ground_truth"] == "approve"]

    def _rate(rows, pred):
        return round(sum(1 for r in rows if r["predicted"] == pred) / len(rows), 4) if rows else None

    per_cat = {}
    by_cat: dict = defaultdict(list)
    for r in known:
        by_cat[r.get("category", "?")].append(r)
    for cat, rows in by_cat.items():
        per_cat[cat] = {"n": len(rows), "recall": _rate(rows, "reject")}

    # Which channel surfaced the killing work, for correctly-rejected KNOWN rows.
    channel_attr = Counter(r.get("channel") for r in known if r["predicted"] == "reject" and r.get("channel"))

    costs = [r.get("cost_usd", 0.0) for r in results]
    lats = [r.get("latency_s", 0.0) for r in results]
    return {
        "n_known": len(known),
        "n_plausible": len(plausible),
        "rejection_recall_known": _rate(known, "reject"),
        "false_rejection_rate_plausible": _rate(plausible, "reject"),
        "per_category_recall": per_cat,
        "channel_attribution": dict(channel_attr),
        "cost_usd_total": round(sum(costs), 6),
        "cost_usd_per_idea": round(sum(costs) / len(results), 6) if results else 0.0,
        "latency_s_total": round(sum(lats), 3),
        "latency_s_per_idea": round(sum(lats) / len(results), 3) if results else 0.0,
    }


# --------------------------------------------------------------------------- #
# Run loop with clean budget halt
# --------------------------------------------------------------------------- #
def run_benchmark(
    rows: List[dict],
    engine_fn: Callable[[dict], dict],
    *,
    budget_usd: Optional[float] = None,
) -> dict:
    """Evaluate ``rows`` with ``engine_fn`` (row -> per-row result). Halts cleanly
    at ``budget_usd``, persisting every completed row."""
    results: List[dict] = []
    total_cost = 0.0
    status = "completed"
    for row in rows:
        res = engine_fn(row)
        results.append(res)
        total_cost += float(res.get("cost_usd", 0.0))
        if budget_usd is not None and total_cost >= budget_usd:
            status = "budget_halted"
            break
    return {
        "status": status,
        "rows_completed": len(results),
        "rows_total": len(rows),
        "total_cost_usd": round(total_cost, 6),
        "results": results,
    }


# --------------------------------------------------------------------------- #
# CI-lite engine — offline, canned outputs, exercises the real pipeline code
# --------------------------------------------------------------------------- #
def _diff_row(work_id: str, severity: str) -> dict:
    return {"work_id": work_id, "overlap_summary": "s", "differs_because": "d", "overlap_severity": severity}


def make_ci_lite_engine(k: int = 3) -> Callable[[dict], dict]:
    """Deterministic offline engine: runs the REAL pipeline (dedup, prefilter,
    gate, falsifier) with canned recall/score/falsify so KNOWN rows reject and
    PLAUSIBLE rows approve — asserting plumbing, not quality."""
    from unittest.mock import patch

    import numpy as np

    from ai_research_engineer.core.novelty import prefilter as _prefilter
    from ai_research_engineer.core.novelty.dedup import RejectedIdeaStore
    from ai_research_engineer.core.novelty.pipeline import evaluate_idea

    def _embed(texts, model_name=None):
        if isinstance(texts, str):
            texts = [texts]
        return np.array([[float(i + 1), 0.0, 1.0] for i in range(len(texts))], dtype=np.float32)

    def engine(row: dict) -> dict:
        gt = row["ground_truth"]
        killer = row.get("killing_work", {}) or {}
        killer_id = killer.get("url") or killer.get("title") or "KILLER"
        channel = "openalex"

        def recall_fn(_idea):
            return [
                {
                    "id": killer_id,
                    "title": killer.get("title") or "prior work",
                    "abstract_or_readme": "prior work text",
                    "source_channel": channel,
                    "year": 2020,
                    "url": killer.get("url"),
                }
            ]

        def score_fn(_idea, _cands):
            if gt == "reject":
                table = [_diff_row(f"W{i}", "none") for i in range(k - 1)] + [_diff_row(killer_id, "core")]
            else:
                table = [_diff_row(f"W{i}", "none") for i in range(k)]
            return {"verdict": "approve", "differentiation_table": table}

        def falsify_fn(_idea, _table):
            return {"found": False, "searched": ["q"]}

        idea = {"title": row["idea_title"], "description": row["idea_description"]}
        store = RejectedIdeaStore(state={}, embed_fn=lambda t: _embed(t)[0])
        t0 = time.time()
        with patch.object(_prefilter, "embed_texts", side_effect=_embed):
            decision = evaluate_idea(idea, recall_fn(idea), score_fn=score_fn, falsify_fn=falsify_fn, k=k, store=store)
        predicted = "reject" if not decision.get("approved") else "approve"
        return {
            "id": row["id"],
            "ground_truth": gt,
            "category": row.get("category", "open"),
            "predicted": predicted,
            "correct": predicted == gt,
            "channel": channel if (gt == "reject" and predicted == "reject") else None,
            "cost_usd": 0.0,
            "latency_s": round(time.time() - t0, 4),
        }

    return engine


def _ci_lite_rows() -> List[dict]:
    _, known = load_dataset(_DATASETS / "known_50.jsonl")
    _, plausible = load_dataset(_DATASETS / "plausible_30.jsonl")
    by_id = {r["id"]: r for r in known + plausible}
    return [by_id[i] for i in (CI_LITE_KNOWN + CI_LITE_PLAUSIBLE) if i in by_id]


# --------------------------------------------------------------------------- #
# Result assembly
# --------------------------------------------------------------------------- #
def build_result(run: dict, *, model: str, mode: str, args: dict) -> dict:
    return {
        # header — every number carries its model + mode + status.
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "mode": mode,
        "model": model,
        "status": run["status"],
        "rows_completed": run["rows_completed"],
        "rows_total": run["rows_total"],
        "budget_usd": args.get("budget_usd"),
        "flags": args,
        "metrics": compute_metrics(run["results"]),
        "rows": run["results"],
    }


def _print_summary(result: dict) -> None:
    m = result["metrics"]
    print("\n=== Novelty benchmark ===")
    print(
        f"mode={result['mode']}  model={result['model']}  status={result['status']}  "
        f"rows={result['rows_completed']}/{result['rows_total']}"
    )
    print(f"KNOWN-50 rejection recall: {m['rejection_recall_known']}")
    for cat, s in m["per_category_recall"].items():
        print(f"  - {cat:<10} recall={s['recall']}  (n={s['n']})")
    print(f"PLAUSIBLE false-rejection rate: {m['false_rejection_rate_plausible']}")
    print(f"channel attribution: {m['channel_attribution']}")
    print(f"cost/idea=${m['cost_usd_per_idea']}  latency/idea={m['latency_s_per_idea']}s")


# --------------------------------------------------------------------------- #
# Dry-run — configuration sanity-check, no LLM / search / engine invoked
# --------------------------------------------------------------------------- #
def estimate_cost(rows: List[dict], expected_cost_per_row: float) -> dict:
    """Coarse estimate: row count x a flat $/row. Deliberately NOT a per-row
    price model — the cost harness gives the true number during a real run."""
    n_known = sum(1 for r in rows if r.get("ground_truth") == "reject")
    n_plausible = sum(1 for r in rows if r.get("ground_truth") == "approve")
    return {
        "rows": len(rows),
        "n_known": n_known,
        "n_plausible": n_plausible,
        "expected_cost_per_row": expected_cost_per_row,
        "estimated_total_usd": round(len(rows) * expected_cost_per_row, 2),
    }


def dry_run_report(
    rows: List[dict],
    mode: str,
    model: str,
    expected_cost_per_row: float,
    budget_usd: Optional[float],
) -> int:
    """Print the estimate and return an exit code. Invokes no LLM, search, or
    engine. With ``budget_usd``, prints projected margin and returns nonzero iff
    the estimate exceeds the cap, so scripts can detect a misconfigured budget."""
    est = estimate_cost(rows, expected_cost_per_row)
    x = est["estimated_total_usd"]
    print("\n=== Novelty benchmark — DRY RUN (no LLM or search invoked) ===")
    print(f"mode={mode}  model={model}")
    print(f"rows={est['rows']}  (KNOWN={est['n_known']}  PLAUSIBLE={est['n_plausible']})")
    print(f"expected ${expected_cost_per_row:.2f}/row  ->  estimated total ${x:.2f}")
    if budget_usd is not None:
        y = float(budget_usd)
        margin = round((y - x) / y * 100, 1) if y else 0.0
        print(f"budget: estimated ${x:.2f} vs cap ${y:.2f}, margin {margin}%")
        if x > y:
            print(
                f"!! DRY-RUN OVER BUDGET — estimated ${x:.2f} exceeds cap ${y:.2f}; raise --budget-usd or reduce rows"
            )
            return 1
    return 0


# --------------------------------------------------------------------------- #
# main
# --------------------------------------------------------------------------- #
def main() -> int:
    ap = argparse.ArgumentParser(description="Stage 2 novelty benchmark (S2-7)")
    ap.add_argument("--ci-lite", action="store_true", help="offline plumbing run (5 KNOWN + 3 PLAUSIBLE)")
    ap.add_argument("--budget-usd", type=float, default=None, help="halt cleanly at this cumulative spend")
    ap.add_argument("--subsample", type=int, default=None, help="run N rows")
    ap.add_argument("--stratified", action="store_true", help="keep per-category proportions when subsampling")
    ap.add_argument("--model-override", default=None, help="scorer+falsifier model (recorded in the header)")
    ap.add_argument("-k", type=int, default=3, help="prefiltered works / table rows (ci-lite default 3)")
    ap.add_argument(
        "--dry-run",
        action="store_true",
        help="report estimated cost + row/mode breakdown for the current selection and exit; invokes no LLM or search",
    )
    ap.add_argument(
        "--expected-cost-per-row",
        type=float,
        default=EXPECTED_COST_PER_ROW,
        help=f"$/row used ONLY by --dry-run (default {EXPECTED_COST_PER_ROW})",
    )
    args = ap.parse_args()

    # Resolve the row selection for the current flags. This touches dataset files
    # only — no LLM, no search, no engine construction.
    if args.ci_lite:
        rows = _ci_lite_rows()
        model = args.model_override or "ci-lite-offline"
        mode = "ci-lite"
        p_header = None
    else:
        _, known = load_dataset(_DATASETS / "known_50.jsonl")
        p_header, plausible = load_dataset(_DATASETS / "plausible_30.jsonl")
        rows = known + plausible
        if args.subsample:
            rows = stratified_subsample(rows, args.subsample) if args.stratified else rows[: args.subsample]
        model = args.model_override or "<live model set at CC-2.7>"
        mode = "full"

    # --dry-run: sanity-check configuration and exit BEFORE any engine exists.
    if args.dry_run:
        return dry_run_report(rows, mode, model, args.expected_cost_per_row, args.budget_usd)

    if args.ci_lite:
        engine = make_ci_lite_engine(k=args.k)
    else:
        if not signed_off(p_header):
            print("\n" + "!" * 72)
            print("!! PLAUSIBLE is DRAFT (SIGNED_OFF: false). Its false-rejection")
            print("!! numbers are NOT valid until the maintainer signs off the dataset.")
            print("!" * 72 + "\n")
        # Live engine construction is intentionally deferred (CC-2.7 runs it live).
        raise SystemExit("full (live) mode is not run here — see CC-2.7. Use --ci-lite for the offline plumbing run.")

    run = run_benchmark(rows, engine, budget_usd=args.budget_usd)
    result = build_result(run, model=model, mode=mode, args=vars(args))

    _RESULTS.mkdir(parents=True, exist_ok=True)
    out = _RESULTS / f"novelty_{mode}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    out.write_text(json.dumps(result, indent=2), encoding="utf-8")
    _print_summary(result)
    print(f"\nwrote {out}")

    # CI-lite asserts plumbing: every row's prediction must match ground truth.
    if args.ci_lite:
        wrong = [r["id"] for r in run["results"] if not r["correct"]]
        if wrong:
            print(f"CI-LITE FAILED — mispredicted rows: {wrong}")
            return 1
        print("CI-LITE OK — pipeline plumbing verified end-to-end.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
