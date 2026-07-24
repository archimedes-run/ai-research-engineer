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

### Sign-off status (maintainer) — SIGNED OFF, N=19 (subfield rebuild)

**Signed off at N = 19.** Composition: **15 new** maintainer-proposed rows across
four subfields (4 learning-augmented algorithms, 4 physics-informed neural
operators, 3 protein-ML, 4 MoE routing) + **4 retained** confident rows from the
original review. The dataset header carries the full `composition` and
`frr_denominator: 19`.

Provenance: the set started as 30 LLM-proposed candidates; a per-row literature
review found **22 had prior art** and **4 were close-calls**, and an autonomous
LLM rebuild of 18 candidates netted only **1 survivor (~5%)** — repeated evidence
that LLM-generation cannot produce this set. It was instead rebuilt
**subfield-first / memory-first / then-verified** (`PLAUSIBLE_REBUILD_PLAN.md`):
the maintainer proposed from fields they know deeply, and each candidate got an
independent Semantic Scholar/arXiv verification pass — **2 of 17 were killed** by
a core-doing prior work found in verification. Full record in
`PLAUSIBLE_SIGNOFF_NOTES.md`.

N = 19 is still modest, so continue to report the false-rejection number as a
fraction of 19. A larger N only ever comes from maintainer-proposed,
individually-verified rows — never from relaxing a rationale to hit a count.

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
- **`--dry-run`** — report the estimated cost and KNOWN/PLAUSIBLE row breakdown
  for the current selection, then exit **without any LLM or search call**.
  Estimate is `rows × --expected-cost-per-row` (default $0.55) — a configuration
  sanity-check, not a price model. With `--budget-usd` it prints the projected
  margin and **exits non-zero if the estimate exceeds the cap**, so a
  misconfigured budget is caught before anything is spent.
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

KNOWN-50 rejection recall ≥ 90%; code-only ≥ 7/10; PLAUSIBLE false-rejection
≤ 20%; cost ≤ $1.50 and ≤ 6 min per idea at k=12.
