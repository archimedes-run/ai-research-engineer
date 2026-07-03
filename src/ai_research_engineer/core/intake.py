"""Intake router (S0-5).

Before the workflow root runs, classify the user's prompt into
{replicate, novel, optimize, ambiguous} with a cheap regex heuristic (and an
optional single-LLM-call fallback behind a flag), then reconcile the detected
intent with the configured research mode.
"""

import logging
import re
from typing import Optional, Tuple


logger = logging.getLogger(__name__)

# Heuristic patterns (checked before any optional LLM fallback).
_REPLICATE_RE = re.compile(r"\b(replicat\w*|reproduc\w*|re-?implement\w*|faithfully implement\w*)\b", re.IGNORECASE)
_OPTIMIZE_RE = re.compile(r"\b(maximi[sz]e|optimi[sz]e|improve the score|evolve)\b", re.IGNORECASE)
_NOVEL_RE = re.compile(r"\b(novel|new (?:method|idea|approach|algorithm)|invent|propose a new)\b", re.IGNORECASE)

# Research modes the workflow understands.
MODE_REPLICATION = "replication"
MODE_NOVELTY = "novelty"
MODE_EVOLVE = "evolve"

# The research mode each detected intent is consistent with.
_INTENT_TO_MODE = {
    "replicate": MODE_REPLICATION,
    "optimize": MODE_EVOLVE,
    "novel": MODE_NOVELTY,
}


def classify_intent(prompt: str, use_llm_fallback: bool = False) -> str:
    """Classify a user prompt into {replicate, novel, optimize, ambiguous} (S0-5).

    A cheap regex heuristic runs first (replicate and optimize are the most
    safety-relevant, so they take precedence). When nothing matches and
    ``use_llm_fallback`` is set, a single LLM call may be consulted; otherwise
    the result is "ambiguous".
    """
    text = prompt or ""
    if _REPLICATE_RE.search(text):
        return "replicate"
    if _OPTIMIZE_RE.search(text):
        return "optimize"
    if _NOVEL_RE.search(text):
        return "novel"
    if use_llm_fallback:
        result = _llm_classify(text)
        if result:
            return result
    return "ambiguous"


def _llm_classify(prompt: str) -> Optional[str]:
    """Optional single-LLM-call fallback (behind the ``use_llm_fallback`` flag).

    Not wired to a live model in the default build; returns ``None`` so callers
    fall back to "ambiguous". Kept as the documented S0-5 extension point.
    """
    return None


def reconcile_mode(intent: str, research_mode: str, hitl_enabled: bool = False) -> Tuple[str, str]:
    """Reconcile a detected intent with the configured research_mode (S0-5).

    Returns ``(selected_mode, action)`` where action is one of:
      "switch"  — autonomous: auto-switch to the intent's mode,
      "pause"   — supervised (hitl): pause for human confirmation,
      "warn"    — intent is ambiguous: proceed with a warning,
      "proceed" — no conflict, keep research_mode.
    """
    if intent == "ambiguous":
        return research_mode, "warn"

    expected = _INTENT_TO_MODE.get(intent)
    if expected is None or expected == research_mode:
        return research_mode, "proceed"

    # Detected intent conflicts with the configured mode.
    if hitl_enabled:
        return research_mode, "pause"
    return expected, "switch"


__all__ = ["classify_intent", "reconcile_mode", "MODE_REPLICATION", "MODE_NOVELTY", "MODE_EVOLVE"]
