# Contributing to Archimedes

Thanks for your interest in contributing! Archimedes is an open-source autonomous research framework and we welcome contributions of all kinds — bug fixes, features, tests, and docs.

---

## Before you start

- Read the [ROADMAP](ROADMAP.md) to understand where the project is headed.
- Check the [issue tracker](https://github.com/archimedes-run/ai-research-engineer/issues) to see what's already planned or in progress.
- For anything large, open a **design issue** first (half a page describing the approach) so we can align before you build.

---

## Development setup

**Requirements:** Python 3.12+, [uv](https://docs.astral.sh/uv/), Node 20+, npm.

```bash
# Clone
git clone https://github.com/archimedes-run/ai-research-engineer.git
cd ai-research-engineer

# Backend
uv sync --extra dev
cp .env.example .env   # add your API keys

# Frontend
cd frontend && npm install
```

**API keys** you'll need (in `.env`):
```
ANTHROPIC_API_KEY=...
OPENROUTER_API_KEY=...
SEMANTIC_SCHOLAR_API_KEY=...   # optional, raises rate limits
```

---

## Running tests & linting

```bash
# Backend tests
uv run pytest tests/ -q

# Linting & formatting
uv run ruff check .
uv run ruff format .

# Frontend build check
cd frontend && npm run build
```

All checks run automatically in CI on every PR.

---

## Workflow

1. **Fork** the repo and create a branch from `main`:
   ```bash
   git checkout -b feat/my-change
   ```
2. Make your changes. Keep commits focused and use [Conventional Commits](https://www.conventionalcommits.org/):
   - `feat:` new feature
   - `fix:` bug fix
   - `docs:` documentation only
   - `chore:` maintenance, deps, config
   - `test:` tests only
3. Push your branch and **open a draft PR** early — we're happy to give feedback before you're done.
4. Fill in the PR template and mark it **Ready for Review** when done.
5. A maintainer will review and merge once CI is green.

---

## Code style

- **Python:** type hints everywhere, NumPy-style docstrings, formatted with `ruff format`.
- **TypeScript/React:** functional components, no default exports that aren't page/layout, Tailwind for styling.
- **Comments:** only when the *why* is non-obvious. Don't describe what the code does — good names do that.
- **No overclaims in copy:** the phrases `world's first`, `publication-ready`, `finished paper`, `fully autonomous` must not appear in the codebase or site.

---

## Commit message examples

```
feat(backend): add session persistence for resumable runs
fix(frontend): correct mobile TOC sticky offset below navbar
docs: update quickstart for uv-based install
chore: bump next to 15.5.19 (CVE-2025-66478)
test(backend): add smoke test for evolve mode
```

---

## Questions?

- Open an issue and tag it `help wanted`.
- For bigger ideas, open a `design` issue — we love talking through approaches before building.
