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

## Not environment-gated — deliberately NOT guarded (pre-existing test defects)

These fail **regardless of the environment** (the "dependency" is already
present, or there is no external dependency at all), so a `skipif` would be
both ineffective and dishonest. They need test fixes, tracked as follow-ups —
not environment guards.

| Test | Observed failure | Real root cause (not environment) |
|------|------------------|-----------------------------------|
| `test_tools.py::TestResearchOps::test_omni_search_papers` | ERROR at setup: `fixture 'mock_search_paper' not found` | Test references a fixture that no longer exists. A collection-time error, unrelated to network. |
| `test_tools.py::TestResearchOps::test_build_citation_graph` | `Object of type MagicMock is not JSON serializable` | `build_citation_graph` also calls `sch.get_papers(...)` (plural) for neighbour citations; the test only stubs `sch.get_paper` (singular), so the un-stubbed call returns a MagicMock that is then JSON-dumped. Semantic Scholar is mocked, so network presence is irrelevant. |
| `test_tools.py::TestCodeGraphOps::test_build_knowledge_graph_success` | `Could not build the code graph …` | Stale mock: the test patches `code_graph_ops.subprocess.run`, but `build_knowledge_graph` was refactored to build via `core.graphify.ensure_graph` (graphify Python API), so the mock is never hit. graphify **is** installed (`graphifyy` is a hard dependency), so `graphify_available()` is True — a graphify guard would not skip it. |
| `test_tools.py::TestCodeGraphOps::test_build_knowledge_graph_failure` | `assert "Error building graph" in result` fails | Same stale-mock cause as above. |
| `test_tools.py::TestCodeGraphOps::test_query_code_structure_path` | Returns `No code graph yet — run build_knowledge_graph first` | `query_code_structure` early-returns when `graphify-out/graph.json` is absent; the test never builds one, so the patched subprocess is never reached. A setup gap, not a missing dependency. |
| `tests/integration/test_run_e2e_mock.py` (9 tests) | `TimeoutError: Session … never left 'running' within 10.0s` | Async background-task scheduling under Starlette `TestClient`. `AIEngineer(...)` construction is instant and `run_async` is monkeypatched to a canned stream, and outbound network is reachable — yet the background `_run_agent` task does not progress within the poll window. This is test-infra/timing flakiness (one test in the module passes), not a missing external dependency; a network guard would not skip it (network is up). |

### Verification snapshot (this environment)

- `pytest tests/unit/test_tools.py` → `4 failed, 33 passed, 2 skipped, 1 error`
  (was `6 failed, 33 passed, 1 error`; the 2 pdflatex tests now skip).
- The remaining failures above are identical on baseline `HEAD` and are not
  introduced by any Stage 0 change.
