# Stage 0 — Test Baseline & Environment Guards

Hygiene pass to stop **environment-dependent** tests from *failing* when the
external dependency they exercise is absent — they should **skip** instead.

Guiding rule (do not violate): only gate a test on the environment actually
providing the dependency. Never add a skip to paper over a broken assertion or
a stale mock — that hides real defects. A test that fails *even when the
dependency is present* is a test bug, not an environment gap, and is left
failing (and documented below) rather than falsely guarded.

## Guarded tests (environment-dependent → now skip when the dep is missing)

| Test | Guard | Why it's environment-dependent |
|------|-------|--------------------------------|
| `tests/unit/test_tools.py::TestLatexOps::test_compile_success` | `skipif(shutil.which("pdflatex") is None)` | Asserts the pdflatex two-pass behaviour (`mock_run.call_count == 2`). `compile_latex_to_pdf` prefers `pdflatex` and falls back to `tectonic`; with no pdflatex on PATH the tectonic branch runs (one pass) and the pdflatex-specific assertion cannot hold. |
| `tests/unit/test_tools.py::TestLatexOps::test_compile_failure_on_first_pass` | `skipif(shutil.which("pdflatex") is None)` | Asserts the pdflatex-specific `"pass 1"` message. Only the pdflatex branch emits it; tectonic produces a different message. |

Assertions are unchanged; only execution is gated. `test_compile_missing_file`
is not guarded — it needs no compiler.

## Not environment-gated — repaired test defects (NOT guarded)

These failed **regardless of the environment** (the "dependency" was already
present, or there was no external dependency at all), so a `skipif` would have
been both ineffective and dishonest. Instead of guarding them, the underlying
test defects were fixed (Tier 1: stale mocks; Tier 2: async test-client
lifecycle). The table records the original root cause and the fix.

| Test | Original failure | Root cause (not environment) → Fix |
|------|------------------|------------------------------------|
| `test_tools.py::TestResearchOps::test_omni_search_papers` | ERROR at setup: `fixture 'mock_search_paper' not found` | Referenced a fixture that no longer exists. **Fixed:** rewrote to mock the real findpapers call sites (`findpapers.search` + `findpapers.utils.persistence_util.load`). |
| `test_tools.py::TestResearchOps::test_build_citation_graph` | `Object of type MagicMock is not JSON serializable` | `build_citation_graph` fetches neighbour citations via `sch.get_papers(...)` (plural), and unset MagicMock `paperId`/`year` attrs were JSON-dumped. **Fixed:** set real `paperId`/`year` on the mocks and stubbed `sch.get_papers`; assertions updated to the current JSON output (incl. the cross-connection edge). |
| `test_tools.py::TestCodeGraphOps::test_build_knowledge_graph_success` / `_failure` | `Could not build the code graph …` | Stale mock: patched `code_graph_ops.subprocess.run`, but `build_knowledge_graph` was refactored to build via `core.graphify.ensure_graph`. **Fixed:** repointed mocks at `core.graphify.{graphify_available,ensure_graph}`; added a graphify-absent test asserting the fail-soft message. |
| `test_tools.py::TestCodeGraphOps::test_query_code_structure_path` | Returns `No code graph yet …` | `query_code_structure` early-returns unless `graphify-out/graph.json` exists. **Fixed:** create the graph file so the `python -m graphify` subprocess (correctly mocked) is actually invoked. |
| `tests/integration/test_run_e2e_mock.py` (9 tests) | `TimeoutError: Session … never left 'running' within 10.0s` | **Root cause (diagnosed Tier 2):** the fixtures used `TestClient` **without** a context manager, so its anyio portal / event loop was torn down after each request and the background `asyncio.create_task(_run_agent(...))` was **cancelled** mid-flight (the task showed `cancelled`, no `update_session` ever ran → status stuck "running"). Not network, not a missing dependency. **Fixed:** enter `TestClient` as a context manager (`with TestClient(app) as client: yield client`) so the loop stays alive and the background task completes. Small, safe test-only change — no server machinery restructured. |

### Verification snapshot (this environment)

- `pytest tests/unit/test_tools.py` → `39 passed, 2 skipped` (the 2 pdflatex
  tests skip; the 4 repaired tests + 1 new graphify-absent test pass).
- `pytest tests/integration/test_run_e2e_mock.py` → `10 passed` (was 9 failed /
  1 passed), and fast (~7s) instead of timing out.
