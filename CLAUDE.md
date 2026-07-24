## guardrails

- Commit locally after completing each task prompt. NEVER push to any remote.
- When a strict-xfail sabotage test starts xpassing after your change, remove
  its marker in the same commit as the feature.
- Backend-lint (`ruff check .`) is reported but not currently a required check,
  due to a pre-existing backlog. Do not introduce new lint errors, but do not
  fix pre-existing ones opportunistically inside feature commits — clear them in
  a dedicated lint-backlog PR.

## graphify

This project has a graphify knowledge graph at graphify-out/.

Rules:
- Before answering architecture or codebase questions, read graphify-out/GRAPH_REPORT.md for god nodes and community structure
- If graphify-out/wiki/index.md exists, navigate it instead of reading raw files
- After modifying code files in this session, run `python3 -c "from graphify.watch import _rebuild_code; from pathlib import Path; _rebuild_code(Path('.'))"` to keep the graph current
