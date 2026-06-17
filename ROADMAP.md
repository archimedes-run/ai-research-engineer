# Archimedes — Roadmap

> Archimedes is an open-source autonomous research framework. You give it a prompt and a mode, and it runs a research loop end to end, producing a **reproducible trace you can verify**. Our goal is to make autonomous research *transparent, steerable, and trustworthy* — a collaborator you can watch and guide, not a black box.

This file is the high-level direction. Detailed work lives in **Issues**, is tracked on the **Project board**, and ships in **Milestones**. This is a living document — we revise it as we learn.

---

## The three modes (today's core)

- **Novelty** — generate and pursue a novel research idea, with citation-graph novelty gating before committing.
- **Replication** — reproduce a target paper or result under controlled conditions.
- **Evolve** — AlphaEvolve/FunSearch-style evolutionary search over candidate programs.

You give it a prompt + a mode, and it runs. Everything below is about making each run more stable, more steerable, and more visible.

---

## How we work

- **ROADMAP.md** = direction (this file). **Issues** = detail. **Project board** = status. **Milestones** = releases.
- Labels: `area:backend`, `area:frontend`, `type:feature`, `type:bug`, `type:docs`, `good first issue`, `help wanted`, `design`.
- Anything large (e.g. the HITL engine, live streaming) gets a short **design issue** (`design` label) before implementation — half a page, discussed, then built.
- `main` is protected: every change is a PR, reviewed, with CI passing.
- We ship **small and often**, tag versions, and keep a `CHANGELOG.md`.

**Lanes:** work is split into a **Backend** lane and a **Frontend** lane so collaborators can own an area. Cross-lane features (HITL, live cockpit) get a design issue that spans both.

---

## Milestones

### Phase 0 — Foundation · `v0.1.0` · NOW
Make the project safe to collaborate on and easy to join.
- [x] Branch protection on `main` (require PR + review + CI).
- [x] CI workflow (lint + tests) via GitHub Actions.
- [x] Issue templates, PR template, label set.
- [x] Project board + milestones created.
- [x] README with architecture + the three modes + quickstart.
- [x] `CONTRIBUTING.md` polished, `CODE_OF_CONDUCT.md` added.
- [x] Tag `v0.1.0` to mark the current state.
- [x] Seed 5-8 `good first issue`s for new collaborators.

### Phase 1 — Stabilize the core · `v0.2.0` · NOW → NEXT
Make the three modes dependable and observable.
- **Backend**
  - [ ] Define a clear contract/interface each mode implements (inputs, stages, outputs).
  - [ ] Unit + smoke tests for each mode (novelty, replication, evolve).
  - [ ] **Run/session persistence** — store run state so runs are resumable and replayable.
  - [ ] **Structured event stream** — backend emits typed events (stage started/finished, file written, log line, metric). This is the foundation for both the live UI *and* human-in-the-loop.
- **Frontend**
  - [ ] Run launcher: submit a prompt, choose a mode, start a run.
  - [ ] Run list + basic run detail view (reads the event stream).

### Phase 2 — Human-in-the-loop · `v0.3.0` · NEXT  (flagship)
Let a human step in between stages to guide the research.
- **Design first:** `design` issue for the stage-gate model (how runs pause, checkpoint, and resume).
- **Backend**
  - [ ] Stage-gate engine: pause after each stage, checkpoint state, await human input, resume.
  - [ ] HITL mode flag (autonomous vs. supervised) on a run.
  - [ ] API to surface a pending stage's output and accept human approval / edits / redirection.
- **Frontend**
  - [ ] HITL toggle in the launcher ("allow human in the loop" on/off).
  - [ ] Stage-review panel: see each stage's output, then **approve / edit / send back** before the run continues.

### Phase 3 — Live research cockpit · `v0.4.0` · NEXT  (the "wow")
Watch the agent work in real time.
- **Frontend**
  - [ ] Live stage progress (what's happening right now).
  - [ ] **Live codebase view** — stream files as the agent writes/edits them: a file tree + live diffs, built up in front of the user.
  - [ ] Live logs / terminal stream and live metrics.
  - [ ] Replayable session viewer (scrub through a finished run).
- **Backend**
  - [ ] Ensure the event stream carries file-level and log-level granularity for the above.

### Phase 4 — Outputs & rigor · `v0.5.0` · LATER
Turn raw runs into trustworthy artifacts.
- [ ] Produced artifacts per run: literature map, experiment plan, metrics **and failures**, draft write-up, full replayable log.
- [ ] Verification helpers: data-leakage checks, seed/reproducibility harness, citation existence check.

### Phase 5 — Polish & adoption · `v1.0.0` · LATER
- [ ] Auth, run sharing, hosted demo.
- [ ] Docs site, examples per mode, tutorials.
- [ ] Domain plugin expansion (AI/ML, algorithms, bioinformatics, finance, physics).
- [ ] Performance, cost controls, and observability hardening.

---

## What we're intentionally *not* doing (for now)
- Claiming runs produce finished, publishable papers. Archimedes produces **traces a human verifies** — that's the design, and the verification tooling in Phase 4 is part of the point.
- Chasing breadth of domains before the core loop and the cockpit are solid.

---

## Want to contribute?
Start with a `good first issue`, read `CONTRIBUTING.md`, and open a draft PR early so we can help. Bigger ideas → open a `design` issue and let's talk.
