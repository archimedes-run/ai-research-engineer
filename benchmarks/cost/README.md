# Cost Benchmark Harness

Measures **real-world cost per request** across task modes, engines, and Graphify
configurations. A dry-run (offline, no API) is always available for CI and local
iteration. Real sweeps consume API credits and are opt-in.

---

## Quick start

### Dry-run (offline, no API keys needed)

```bash
uv run python benchmarks/cost/run_benchmark.py --dry-run --yes
```

This uses the built-in mock engine — no LLM calls, no credits spent.
Output lands in `benchmarks/cost/out/`:

```
benchmarks/cost/out/
  raw_<timestamp>.csv       ← one row per cell
  report_<timestamp>.md     ← aggregated Markdown with means, std, cost/request
  runs_<timestamp>/         ← per-run working directories (scratch)
```

### Real sweep (consumes API credits)

```bash
uv run python benchmarks/cost/run_benchmark.py --yes
```

A cost estimate is printed before execution. `--yes` confirms. Without `--yes` the
harness prompts interactively.

Budget and run-count guards:

```bash
# Stop after 5 cells regardless of cost:
uv run python benchmarks/cost/run_benchmark.py --max-runs 5 --yes

# Stop once accumulated cost reaches $1.00:
uv run python benchmarks/cost/run_benchmark.py --budget-usd 1.00 --yes

# Both guards active (whichever fires first):
uv run python benchmarks/cost/run_benchmark.py --max-runs 10 --budget-usd 2.00 --yes
```

---

## Matrix dimensions

| Dimension | Values today | Notes |
|-----------|-------------|-------|
| task modes | `novel`, `replication`, `evolve` | defined in `suite.yaml` |
| graphify | `off` | `on` reserved — Phase H-Graphify |
| engine | `default` | alternate engines reserved — Phase I |
| repetitions | 1 (default) | increase for variance analysis; cost × reps |

Cells for unavailable dimensions (`graphify=on`, unknown engines) are **skipped
automatically** with a WARNING log. The harness never fails on reserved values.

---

## Adding tasks

Edit `benchmarks/cost/suite.yaml`:

```yaml
tasks:
  - id: my_new_task
    topic: "Your research prompt here."
    mode: novel       # novel | replication | evolve
    domain: aiml

defaults:
  repetitions: 1     # bump for variance; each rep costs ≈ the same as one run
```

Keep default topics short — the suite is swept on every CI dry-run.

---

## Output

### `raw_<timestamp>.csv`

One row per completed cell. Columns:

| Column | Description |
|--------|-------------|
| `task_id` | Task identifier from suite.yaml |
| `mode` | `novel` / `replication` / `evolve` |
| `engine` | `default` / `mock` / future engines |
| `model` | Model string from the first usage event |
| `graphify` | `True` / `False` |
| `rep` | Repetition index (1-based) |
| `input_tokens` | Total non-cached prompt tokens |
| `cached_tokens` | Prompt tokens served from cache |
| `output_tokens` | Completion tokens |
| `cost_usd` | Computed via `core.pricing.cost_usd()` |
| `llm_calls` | Number of `UsageEvent`s in the stream |
| `wall_seconds` | Wall-clock time for the cell |
| `success` | Best-effort success signal (`True` / `False` / `None`) |
| `notes` | Error message if the run failed |

### `report_<timestamp>.md`

Aggregated view grouped by `(mode × engine × model × graphify)`:

- Mean ± std for cost, tokens, wall-time, LLM calls.
- **Cost per request** and **cost per successful run**.
- When both `graphify=on` and `graphify=off` data exist for the same cell key,
  the measured **Graphify cost delta** is shown (our measurement, not the vendor's).

---

## Running tests (no API required)

```bash
uv run pytest tests/unit/test_benchmark.py -v
```

All tests use `_FakeEngine` — deterministic, offline, exact cost assertions.

```bash
uv run ruff check benchmarks/ tests/unit/test_benchmark.py
```

---

## Notes

- **Real sweeps consume API credits.** The `--budget-usd` guard stops the harness
  *after* a run that pushes accumulated cost past the limit (the guard fires before
  the *next* run). Set it conservatively.
- **Graphify rows** (`graphify=on`) will activate automatically once Phase H-Graphify
  lands and wires the dimension. No harness changes needed.
- **Alternate engine rows** will activate once Phase I lands. Same principle.
- The harness drives `AIEngineer.run_async(stream=True)` directly — no server
  required, no dependency on `/usage` endpoint.
