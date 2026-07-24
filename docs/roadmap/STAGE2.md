# Stage 2 Spec — Novelty Engine v2: evidence-grounded, adversarial, measured
Goal: replace "one seed's descendants + self-scored MVPT rubric" with a
retrieval-grounded audit whose accuracy is measured on a labeled benchmark.
MVPT survives only as a secondary reporting lens; the gate is evidence.

S2-0 Freeze the Stage 1 retrieval benchmark: add a checksum guard test that
hashes the 10 query→target pairs in benchmarks/knowledge/retrieval_recall.py
and fails if they change without updating a FROZEN_PAIRS_SHA constant plus a
CHANGELOG entry in benchmarks/knowledge/README.md explaining why. Tuning
queries after seeing misses must leave a paper trail.

S2-1 Stage A — multi-channel recall. New module core/novelty/recall.py:
recall_prior_work(idea: dict, working_dir, max_candidates=80) -> list[Candidate].
(a) Query generation: 4-6 deliberately varied paraphrase queries from the idea's
    title+description (an LLM call through the existing agent model config, with
    a deterministic keyword-based fallback when no model is available so tests
    and offline runs work).
(b) Channels, each behind the tool registry with graceful degradation:
    semantic_scholar bulk search, arxiv search, openalex_search, github_search
    (repositories mode, FIRST-CLASS — a hit is a Candidate like any paper),
    paperswithcode_search (OPTIONAL-IF-ALIVE: probe with a cheap request at
    recall start; if non-JSON/dead, mark channel_status="dead" in the recall
    report and skip — never let it silently contribute zero while appearing
    healthy).
(c) Union with citation-graph neighbors: build_citation_graph(seed_ids=top 3
    relevant papers from the session lit index or channel results, hops=2,
    query_text=idea description); absorb graph nodes as Candidates.
(d) Dedupe by (paperId | arxiv id | normalized-title | repo URL); every
    Candidate carries {id, title, abstract_or_readme, source_channel, year,
    url}. GitHub candidates use the repo description+README head as their text.
(e) Upsert all candidates into the session LitIndex (record_papers).
Output also persists knowledge_base/novelty/recall_<idea_id>.json with
per-channel counts and channel_status — the recall report the UI and the
benchmark read.

S2-2 Stage B — embedding prefilter. core/novelty/prefilter.py:
top_similar(idea, candidates, k=12) -> ranked list with cosine scores, via
core embeddings (embed_texts batch; idea text = title+description). Ties are
broken by recency. The prefilter output (top-k with scores) persists into the
recall report.

S2-3 Stage C — forced pairwise differentiation. Rewrite novelty_scorer.md and
the scorer's output schema:
- Input: the idea + the top-k prefiltered works (title/abstract/url/source).
- REQUIRED output per work: {work_id, overlap_summary, differs_because,
  overlap_severity: none|partial|core}. The differentiation table comes FIRST.
- Verdict rule (enforced in the gate code, not just the prompt): any `core`
  → REJECT with that work attached verbatim to the generator feedback;
  otherwise the scorer may APPROVE. An APPROVE with an empty/incomplete table
  (fewer rows than k) is INVALID and treated as REJECT with reason
  "incomplete differentiation" (schema-validated in code).
- MVPT: retained as an optional holistic assessment AFTER the table, recorded
  in the report, never used in the gate decision. DELETE the TIER_1/TIER_2
  numeric thresholds from the prompt. DELETE expected_mvpt from
  idea_generator.md's output schema entirely (grep-tested).
- The ideation confirmation gate now branches on the structured verdict
  (approve/reject + severity table), not on tier arithmetic.

S2-4 Stage D — adversarial falsifier. New agent (same scorer model, temp 0)
prompts/base/novelty_falsifier.md: receives ONLY the idea and its
differentiation table; has the search tools; one job — find a prior work that
kills the idea (a `core` overlap the table missed). Output: {found: bool,
work: {...}, why_core: str} or {found: false, searched: [queries]}.
Wiring: falsifier runs after a scorer APPROVE. found=true → the work is
injected into the candidate set and the scorer re-runs (max 2 falsifier
rounds, then the loop returns its outcome per Stage 0 semantics — no silent
pass). Two clean falsifier passes = final APPROVE.

S2-5 Idea dedup. Before scoring, embed the idea; cosine > 0.92 against any
previously REJECTED idea this session (store rejected-idea embeddings in
state / a small per-session store) → auto-reject with the prior rejection's
reason, zero scorer tokens spent. Threshold in config
(novelty.dedup_threshold).

S2-6 Ideation tournament. idea_generator.md now produces 4-6 ideas per round
(raise from 2-3). Recall (S2-1) runs ONCE on the union of ideas' queries
(shared corpus); each idea is prefiltered+scored against it. The top APPROVED
idea proceeds; the runner-up (if any) is stored in
state["ideation_runner_up"] with its audit, and stage_reflector.md gains one
line: if Stage 1 of the winner's plan fails terminally, pivoting to the
runner-up is an allowed remediation.

S2-7 The novelty benchmark. benchmarks/novelty/ with:
- datasets/known_50.jsonl — 50 "ideas" that are lightly paraphrased abstracts
  of PUBLISHED work → ground truth REJECT. Composition: ~25 canonical papers
  (pre-2024, famous), ~15 recent (2024-2026, non-famous), ~10 CODE-ONLY (well
  -known GitHub repos/techniques with no flagship paper). Each row: {id,
  idea_title, idea_description, ground_truth: "reject", killing_work:
  {title, url}, category}.
- datasets/plausible_30.jsonl — signed off at 19 genuinely open/very-recent
  directions (subfield-rebuilt; the original 30-row spec kept only 8 on review)
  → ground truth "approve" (meaning: must not be rejected for prior art).
  Mark each with a confidence field; these are curated by the maintainer —
  generate a candidate list with rationales for human review, and mark the
  dataset DRAFT until the maintainer signs off (a SIGNED_OFF flag in the
  file header the harness warns about).
  See sign-off history in df4f782 and benchmarks/novelty/PLAUSIBLE_SIGNOFF_NOTES.md.
- run_novelty_bench.py: runs the FULL engine (recall→prefilter→differentiate
  →falsify) against both sets; reports rejection recall on KNOWN-50 (overall
  + per category, esp. code-only), false-rejection rate on PLAUSIBLE-30,
  per-channel attribution (which channel surfaced the killing work), cost and
  latency per idea (reuse the pricing/cost harness). Writes
  benchmarks/novelty/results/<timestamp>.json + a summary table.
- A CI-lite mode: 5 KNOWN + 3 PLAUSIBLE fixture-recorded rows, offline,
  asserting the pipeline plumbing end-to-end (not the quality numbers).

S2-8 Audit persistence. Every idea's full audit (recall report, prefilter
top-k, differentiation table, falsifier rounds, final verdict, MVPT-as-lens)
persists to knowledge_base/novelty_audit.json (append per idea). This is the
artifact Stage 5's ideation memory and the S2-9 UI consume.

S2-9 Frontend novelty evidence view. Cockpit view rendering novelty_audit.json:
per idea, the differentiation table as cards (title, severity chip,
differs-because text, source-channel badge, link), the falsifier verdict, and
the recall report's per-channel counts (with a visibly "dead" badge for dead
channels — surfacing S2-1's channel_status). Read-only, resilient to
missing/partial audits, no new frontend deps unless package.json already has
what's needed.

S2-10 Verification: v1-vs-v2 baseline comparison + report (see CC-2.7).

Rubric targets (from the roadmap): KNOWN-50 rejection recall ≥ 90%; code-only
subset ≥ 7/10; PLAUSIBLE-30 false-rejection ≤ 20%; zero approvals without a
complete differentiation table (schema-enforced); expected_mvpt and TIER
thresholds gone (grep); cost ≤ $1.50 and ≤ 6 min per idea at k=12; ablation
recorded (prefilter on/off, falsifier on/off).
