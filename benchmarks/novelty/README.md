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

### Sign-off status (maintainer)

**SIGNED OFF (2026-07-05), N = 8.** The set started as 30 candidate rows;
**22 were removed** after a per-row literature review found clear or close prior
art (the LLM-assisted curation of "genuinely open" was weak — see
`PLAUSIBLE_SIGNOFF_NOTES.md` for each decision + killer). FRR is now computed
against **N = 8** (small but clean — the honesty of the denominator matters more
than its size). Until a dataset is signed off (`SIGNED_OFF: true`), the harness
prints a loud DRAFT warning and its false-rejection numbers are not valid.

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
