# Novelty benchmark (Stage 2, S2-7)

Measures the novelty engine (recall → prefilter → differentiate → falsify) on a
labeled benchmark.

## Datasets (`datasets/`)

- **`known_50.jsonl`** — 50 ideas that are lightly **paraphrased** cores of
  PUBLISHED work → ground truth **reject**. Composition: 25 canonical (pre-2024,
  famous), 15 recent (2023-2026, non-famous), 10 code-only (GitHub techniques
  with no flagship paper). Each row: `{id, idea_title, idea_description,
  ground_truth: "reject", killing_work: {title, url}, category}`. Descriptions
  are paraphrases, never the verbatim abstract.
- **`plausible_30.jsonl`** — genuinely open / very-recent directions → ground
  truth **approve** (must not be rejected for prior art). Each row carries a
  `confidence` and a `rationale`. The first line is a header
  `{"__meta__": true, "SIGNED_OFF": ..., ...}`.

### Sign-off status (maintainer) — SIGNED OFF, N=5, small-N caveat

**Signed off at N = 5** (per maintainer authorization). Composition: 4
high-confidence-open rows from the review + 1 survivor of an autonomous rebuild.

Provenance: the set started as 30 LLM-proposed candidates; a per-row literature
review found **22 had prior art** and **4 were close-calls**, leaving 4 confident
rows. An authorized autonomous rebuild proposed **18 new candidates and
search-verified each** — only **1 survived (~5%)**, a repeated confirmation that
LLM-generation cannot produce this set. Full record in
`PLAUSIBLE_SIGNOFF_NOTES.md`; process for a proper expansion in
`PLAUSIBLE_REBUILD_PLAN.md`.

**⚠ N=5 makes FRR coarse — each row is 20%.** The dataset header carries
`frr_interpretability: LOW`; report the false-rejection number only with that
caveat. A robust N still needs maintainer-proposed, individually-verified rows.

To add a row (propose from your own knowledge, then **search-verify before
adding** — discard anything with a core-doing prior work):

```json
{"id": "p_<slug>", "idea_title": "...", "idea_description": "one specific,
 mechanism-level open direction", "ground_truth": "approve",
 "confidence": "high|medium|low",
 "rationale": "the closest work you found and the concrete reason the idea is
 not it", "category": "<subfield>"}
```

Aim for ~20–24 rows; keep each individually verified. The 27%→0/6 curation
failure above is *the* argument for this discipline (and a citable Stage 2 result).

## Harness (`run_novelty_bench.py`)

```
uv run python -m benchmarks.novelty.run_novelty_bench --ci-lite          # offline plumbing
uv run python -m benchmarks.novelty.run_novelty_bench                    # full live (CC-2.7)
```

- **`--ci-lite`** — 5 KNOWN + 3 PLAUSIBLE fixture rows, offline, canned LLM
  outputs. Exercises the real pipeline code end-to-end and asserts every
  prediction matches ground truth (plumbing, **not** quality numbers). Wired into
  CI (`novelty-ci-lite` job).
- **`--budget-usd CAP`** — track cumulative spend and **halt cleanly** at the cap;
  completed rows are persisted and the result is marked `status="budget_halted"`.
  Partial results are valid results.
- **`--subsample N [--stratified]`** — run a subset; stratified keeps per-category
  proportions across canonical/recent/code-only and known/plausible (ablations).
- **`--model-override M`** — scorer+falsifier model for the run; **recorded in the
  result header** so no metric is ever reported without its model attached.

Results are written to `results/<mode>_<timestamp>.json` with a header carrying
`{mode, model, status, rows_completed, budget_usd, flags}` and a `metrics` block
(rejection recall overall + per category, false-rejection rate, per-channel
attribution, cost/latency per idea).

## Rubric targets (asserted in CC-2.7, not here)

KNOWN-50 rejection recall ≥ 90%; code-only ≥ 7/10; PLAUSIBLE-30 false-rejection
≤ 20%; cost ≤ $1.50 and ≤ 6 min per idea at k=12.
