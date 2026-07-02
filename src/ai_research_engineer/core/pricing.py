"""Token cost calculator backed by config/pricing.yaml."""

import logging
from functools import lru_cache
from pathlib import Path
from typing import Dict, Optional

import yaml


logger = logging.getLogger(__name__)

_PRICING_YAML = Path(__file__).parents[3] / "config" / "pricing.yaml"


@lru_cache(maxsize=1)
def load_pricing() -> Dict[str, Dict[str, float]]:
    """Return the pricing table, cached after first load."""
    try:
        data = yaml.safe_load(_PRICING_YAML.read_text(encoding="utf-8"))
        return data.get("models", {})
    except Exception as exc:
        logger.warning("Could not load pricing.yaml: %s — all costs will be 0.0", exc)
        return {}


def _resolve_model(model: Optional[str], table: Dict[str, Dict[str, float]]) -> Optional[Dict[str, float]]:
    """Find the best matching entry in the pricing table for *model*."""
    if not model:
        return None
    if model in table:
        return table[model]
    # OpenRouter: fall back to the generic openrouter/default entry
    if model.startswith("openrouter/") and "openrouter/default" in table:
        return table["openrouter/default"]
    return None


def cost_usd(
    model: Optional[str],
    input_tokens: int,
    output_tokens: int,
    cached_tokens: int = 0,
) -> float:
    """
    Return the estimated cost in USD for a single LLM call.

    Cached tokens are billed at *cache_read_per_mtok* instead of *input_per_mtok*.
    Non-cached input tokens = input_tokens - cached_tokens.

    Unknown models return 0.0 and emit a WARNING log so gaps can be filled in.
    """
    table = load_pricing()
    entry = _resolve_model(model, table)
    if entry is None:
        if model:
            logger.warning("pricing.py: no pricing entry for model %r — cost reported as 0.0", model)
        return 0.0

    cached_tokens = min(cached_tokens, input_tokens)
    non_cached = input_tokens - cached_tokens
    usd = (
        non_cached / 1_000_000 * entry.get("input_per_mtok", 0.0)
        + cached_tokens / 1_000_000 * entry.get("cache_read_per_mtok", 0.0)
        + output_tokens / 1_000_000 * entry.get("output_per_mtok", 0.0)
    )
    return round(usd, 10)
