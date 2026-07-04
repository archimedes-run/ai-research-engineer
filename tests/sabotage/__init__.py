"""Sabotage test suite (Stage 0 — S0-10).

Each scenario feeds an adversarial / broken input into the workflow using
mocked agents and fake ``eval.sh`` scripts (no real LLM or network), and
asserts that the runtime *fails loudly and honestly* instead of silently
trusting a self-graded score or a cross-wired gate.

Every test is currently marked ``xfail(strict=True)`` because the Stage 0
trust-foundation features they pin (see docs/roadmap/STAGE0.md) are not yet
implemented. When a feature lands, its scenario should start passing, the
strict marker will turn the unexpected pass into a failure, and the marker
must be removed in the same change that ships the feature.
"""
