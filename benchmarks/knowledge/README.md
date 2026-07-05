# Knowledge-layer benchmarks (Stage 1)

Two rubric harnesses that measure the Stage 1 knowledge layer. Both run live when
network is available and write JSON to `results/`.

- **`ingestion_qa.py`** — runs the S1-2 ingestion pipeline over a 15-paper set
  (HTML-native / PDF-fallback / math-heavy / table-heavy); reports sections
  extracted, hyperparameter-query answerability, and truncation events.
- **`retrieval_recall.py`** — 10 paraphrased-query → target-paper pairs run
  through the multi-source search union; reports top-10 recall and per-source
  attribution.

## Frozen retrieval pairs (S2-0)

The 10 `(query, target)` pairs in `retrieval_recall.py` are a **frozen
benchmark**. Tuning a query after seeing a miss is exactly the kind of silent
overfitting this guard prevents, so changing any pair must be a deliberate,
documented act:

1. Edit `PAIRS`.
2. Recompute the digest and set it as `FROZEN_PAIRS_SHA`:
   ```
   uv run python -c "from benchmarks.knowledge.retrieval_recall import frozen_pairs_sha; print(frozen_pairs_sha())"
   ```
3. Add a dated CHANGELOG entry below **including the new digest**.

`tests/unit/test_retrieval_freeze.py` enforces both halves: it fails if
`frozen_pairs_sha()` ≠ `FROZEN_PAIRS_SHA` (you changed pairs but not the SHA) and
if the current `FROZEN_PAIRS_SHA` is not recorded in this file (you changed the
SHA but left no paper trail).

### CHANGELOG

- **2026-07-04** — Initial freeze of the 10 pairs (2 queries were realistic-paraphrase
  fixes over the first live run; see `STAGE1_REPORT.md` §3).
  `FROZEN_PAIRS_SHA = a5f288316a4a73abe8699752f422e9c9041aa75301074aba9c43213e3b4f1966`
