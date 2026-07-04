# Stage 0 — Verification Report

Trust Foundation (S0-1 … S0-10). Branch `stage-0-trust-foundation`, verified
against branch point `3cc575a`.

## 1. Full test suite — `uv run pytest tests/ -q`

```
443 passed, 4 skipped, 21 warnings
```

- **0 failed, 0 errors, 0 xfailed, 0 xpassed.**
- 4 skipped = 2 pdflatex-gated LaTeX tests (no `pdflatex` on PATH) + 2 opt-in
  `real` end-to-end tests (require live API keys; run with `-m real`).

## 2. Sabotage suite — `uv run pytest tests/sabotage -q`

```
6 passed, 3 warnings
```

- **6 passed, 0 xfailed** ✓ (all six adversarial scenarios (a)–(f) now drive the
  real Stage 0 seams; no scenario remains a placeholder xfail).

## 3. Static audits

| # | Command | Expectation | Result |
|---|---------|-------------|--------|
| 1 | `grep -ri "penalized" src/ai_research_engineer/prompts` | empty | **0 matches** ✓ |
| 2 | `grep -rn "archimedes-run\|ris3abh" src` | empty (outside comments/docs) | **0 matches** ✓ |
| 3 | `grep -rn "git push origin main" src/ai_research_engineer/prompts` | empty | **0 matches** ✓ |
| 4 | `grep -rn "SemanticScholar(" src` | exactly one construction site | **1 match** ✓ — `tools/semantic_scholar.py:20` |

Audit 4 detail — the single unified client:

```
src/ai_research_engineer/tools/semantic_scholar.py:20:client = SemanticScholar(api_key=_api_key)
```

Both `research_ops` and `semantic_scholar_ops` import this one client (`sch`) and
the one shared thread-safe limiter (`enforce_rate_limit`).

## 4. Files changed in Stage 0 — `git diff --stat 3cc575a HEAD`

```
 .github/workflows/ci.yml                                    |  24 ++
 CLAUDE.md                                                   |   6 +
 docs/roadmap/STAGE0.md                                      |  29 ++
 docs/roadmap/STAGE0_BASELINE.md                             |  68 +++++
 src/ai_research_engineer/agents/adk/agent.py                |  59 +++-
 src/ai_research_engineer/agents/adk/evolution_loop.py       | 207 ++++++++++---
 src/ai_research_engineer/agents/adk/hitl_sequential.py      |  78 ++++-
 src/ai_research_engineer/agents/adk/implementation_loop.py  |   6 +-
 src/ai_research_engineer/agents/adk/stage_orchestrator.py   | 239 ++++++++++++++-
 src/ai_research_engineer/agents/adk/utils.py                |  24 ++
 src/ai_research_engineer/agents/claude_code/agent.py        | 257 ++++++++--------
 src/ai_research_engineer/agents/claude_code/templates.py    |  12 +-
 src/ai_research_engineer/core/api.py                        |  70 +++++
 src/ai_research_engineer/core/events.py                     |  84 ++++++
 src/ai_research_engineer/core/intake.py                     |  87 ++++++
 src/ai_research_engineer/evolve/database/database.py        |  20 +-
 src/ai_research_engineer/evolve/utils/structures.py         |  10 +-
 src/ai_research_engineer/prompts/__init__.py                |  35 ++-
 src/ai_research_engineer/prompts/base/coding_base.md        |  27 +-
 src/ai_research_engineer/prompts/base/coding_review.md      |  26 +-
 .../prompts/base/implementation_review_confirmation.md      | 135 ++-------
 src/ai_research_engineer/prompts/base/stage_reflector.md    |   4 +-
 src/ai_research_engineer/server/app.py                      |  61 ++++
 src/ai_research_engineer/tools/research_ops.py              |  14 +-
 src/ai_research_engineer/tools/semantic_scholar.py          |  44 +++
 src/ai_research_engineer/tools/semantic_scholar_ops.py      |  26 +-
 src/ai_research_engineer/tools/web_ops.py                   |  94 +++++-
 tests/conftest.py                                           |  13 +
 tests/integration/test_run_e2e_mock.py                     |  12 +-
 tests/sabotage/__init__.py                                  |  13 +
 tests/sabotage/test_sabotage.py                            | 322 +++++++++++++++++++++
 tests/unit/test_agents.py                                  | 228 +++++++++++++++
 tests/unit/test_claude_code_security.py                    | 111 +++++++
 tests/unit/test_events.py                                  | 166 +++++++++++
 tests/unit/test_evolve.py                                  | 179 ++++++++++++
 tests/unit/test_evolve_tree.py                             |   5 +
 tests/unit/test_hitl.py                                    | 123 ++++++++
 tests/unit/test_intake.py                                  | 128 ++++++++
 tests/unit/test_prompts.py                                 |  54 ++++
 tests/unit/test_semantic_scholar.py                        |  47 +++
 tests/unit/test_tools.py                                   | 141 ++++++---
 41 files changed, 2910 insertions(+), 378 deletions(-)
```

## 5. Rubric — S0-1 … S0-10 → tests → status

| Task | What it delivers | Primary test(s) / audit | Status |
|------|------------------|-------------------------|--------|
| **S0-1** Loop outcomes | `NonEscalatingLoopAgent` records `<loop>_outcome`; `HITLSequentialAgent` halts/pauses/draft-unverified; `gate_decision` event | `test_hitl.py::TestLoopOutcomeBranching`; `test_agents.py` (`classify_loop_outcome`); `test_events.py::TestGateDecisionEvent`; sabotage (a),(b) | **PASS** |
| **S0-2** Honest stages | stage `status` = completed vs completed_unverified (derived `completed` bool); reflector flags unverified | `test_agents.py::TestStageStatusHonesty`; `test_events.py::TestStageStatusEvent`; sabotage (a) | **PASS** |
| **S0-3** No-progress guard | sha256 over criteria/status/plan/files; 2× → forced reflection, 3× → terminate/HITL-pause; `progress_hash` events | `test_agents.py::TestNoProgressGuard` (4 cases); `test_events.py::TestProgressHashEvent` | **PASS** |
| **S0-4** Sealed evolve evaluator | orchestrator runs `eval.sh` (mtime-fenced, pre-deleted, timeout); `score=None`/status on failure; DB accepts/skips None | `test_evolve.py::TestSealedEvaluation`, `::TestSealedBootstrap`, `::TestNoneScoreDatabase`; `test_events.py::TestEvalResultEvent`; sabotage (c),(d) | **PASS** |
| **S0-5** Intake router | classify {replicate,novel,optimize,ambiguous}; reconcile mode (switch/pause/warn); HITL pause halts fail-safe | `test_intake.py` (classify, reconcile, `TestHITLIntakePauseHalts`); `test_events.py::TestIntakeDecisionEvent`; sabotage (f) | **PASS** |
| **S0-6** Fix cross-wired gate | rewrote `implementation_review_confirmation.md` to gate on reviewer output; `review_degraded`; no novelty/MVPT/tier/ideation | `test_prompts.py::TestImplementationReviewConfirmationPrompt`; sabotage (a) exercises the gate | **PASS** |
| **S0-7** Conditional prompting | `probe_tool_availability`; `load_prompt` strips `BEGIN:graphify` blocks; graphify preferred-but-optional in both files | `test_prompts.py::TestConditionalToolSections`; sabotage (e); Audit 1 (penalized) | **PASS** |
| **S0-8** Security sweep | no hardcoded org/PAT/auto-push; config-gated push w/ ephemeral auth; pinned skills cache; `fetch_url` DNS pinning; unified S2 client+limiter | `test_claude_code_security.py` (git no-push, no PAT, skills cache); `test_semantic_scholar.py` (unified + 1-rps concurrency); Audits 2,3,4 | **PASS** |
| **S0-9** Typed events | `gate_decision`, `stage_status`, `eval_result`, `progress_hash`, `intake_decision` payload types that serialize into the stream/store | `test_events.py::TestS0_9EventSessionStoreRoundTrip` + per-type tests | **PASS** |
| **S0-10** Sabotage suite + CI | `tests/sabotage/` with 6 mocked scenarios; wired into CI as a required job | `tests/sabotage/test_sabotage.py` (6 passed, 0 xfailed); `.github/workflows/ci.yml` `sabotage` job | **PASS** |

**Result: 10 / 10 Stage 0 tasks PASS.**

### Known follow-ups (tracked in STAGE0_BASELINE.md)

- **S0-5 (HITL):** a real pre-workflow HITL pause+resume handshake is deferred to
  Stage 7; the interim behavior halts fail-safe (never fail-open).
- **S0-8 (skills):** `SKILLS_REPO_SHA` is a placeholder constant — set it to a real
  pinned commit of `claude-scientific-skills` before enabling real clones.
