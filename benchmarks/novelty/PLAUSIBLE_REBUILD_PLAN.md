# PLAUSIBLE rebuild protocol (subfield-first, memory-first, then verified)

Why this shape: the original LLM-generated PLAUSIBLE-30 kept only 8/30 (and an
LLM regeneration attempt hit 0/6 — see `PLAUSIBLE_SIGNOFF_NOTES.md`). Proposing
"open directions" across all of ML at once means proposing where knowledge is
shallow, and shallow knowledge produces false-open claims. The fix inverts it:
**propose from fields you know deeply, from memory, then verify.** In your
subfield, "I can't name a killer after 60s" is real evidence of a gap; outside
it, it just means you don't know the field.

**Division of labor:** the maintainer owns Steps 1–2 (subfield pick + memory-first
proposal — the human's comparative advantage). Claude owns Phase 3 (search-verify
each candidate), Phase 4 (assembly/format), and the sign-off commit — hand over
one-line candidates and it runs the rest.

## Step 1 — Pick subfields (do this first; commit the fill-in below)

Pick 3–4 subfields where you could name the most-cited 2024–2026 paper. Fill in:

| # | subfield | why I know it well (a class / project / papers read) | target rows |
| - | --- | --- | ---: |
| 1 |  |  | 5–7 |
| 2 |  |  | 5–7 |
| 3 |  |  | 5–7 |
| 4 |  |  | 5–7 |

## Step 2 — Per row (~15 min)

1. **Propose from memory (5 min)** — one sentence; do NOT search. "What specific
   method/study would I be surprised to learn already exists?"
2. **Adversarial memory check (2 min)** — try to kill it from memory (a paper you
   read; an obvious next-step from a known paper; a broader line you're forgetting).
   Killed → discard.
3. **Verified search (5 min)** — Semantic Scholar + arXiv, ~3 query variants.
   *Core* kills; *adjacent* is fine (that's what the differentiation table is for).
   Search-killed → discard, record the killer. Adjacent-only → keep + note it.
4. **Write the row (3 min):**
   ```json
   {"id": "p_<subfield>_<n>", "idea_title": "<~10-15 words>",
    "idea_description": "<2-3 sentences: what it does, what it targets, what makes
    it distinct from the closest adjacent work>",
    "ground_truth": "approve", "confidence": "high|medium",
    "rationale": "<what you searched; closest work: <paper>, but that <specific
    difference>>", "category": "<subfield>"}
   ```
   The `rationale` is the sign-off audit trail AND the Stage 8 reviewer-facing
   evidence — write it well.

## Step 3 — Sessions

Two ~2-hour sittings, **break overnight between them** (thin differentiations
sneak through in hour 3+). If a subfield starts producing strained rationales,
stop it at whatever count and move on — 8 solid rows beat 10 with two forced ones.
Land at ~18–22 new rows + the 4 retained confident rows → **PLAUSIBLE ~22–26**.

## Step 4 — Meta-check before flipping SIGNED_OFF

Pick 3 random new rows, close the file, redo Phase-1-from-memory. All 3 hold →
commit. 1 fails → drop it (and similar), commit at N-1/-2. 2+ fail → you were
tired; break and redo those fresh.

## Step 5 — Sign off (Claude can run this once rows exist)

Set the dataset header `SIGNED_OFF: true` with the true composition, and use the
commit shape:

```
docs(s2-7): rebuild PLAUSIBLE via subfield-expert generation, sign off

Original LLM-generated PLAUSIBLE-30 kept only 8/30 defensible rows.
Rebuilt subfield-first/memory-first/then-verified across <N> subfields the
reviewer knows well: <list>.

Final: PLAUSIBLE-<N>.
  - <X> rows from <subfield 1>
  - ...
  - 4 rows retained from the original pass (see PLAUSIBLE_SIGNOFF_NOTES.md)
Dropped: 22 (killer found) + 4 weak KEEPs (compositional_eval_gen,
  units_aware_reasoning, uncertainty_from_kv, hardware_aware_quant_search).

FRR computed against N=<N>. SIGNED_OFF: true.
```

## Sign-off hygiene (run before committing a header change)

The dataset header shape (`composition`, counts, `frr_denominator`, `SIGNED_OFF`)
is asserted by `tests/unit/test_novelty_bench.py`. A loader-only sanity check
(`load_dataset` + eyeballing) will **not** catch a stale assertion left behind by
a header change — that surfaced once already (a sign-off updated the header but
left the test asserting the prior N, and the suite went red one commit later).

So when you change the signed-off header, run the bench unit tests before
committing:

```
uv run pytest tests/unit/test_novelty_bench.py -q
```

Green suite is part of "signed off" — not a separate step.
