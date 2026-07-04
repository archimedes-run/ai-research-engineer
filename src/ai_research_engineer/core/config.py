"""Configuration accessors (S1-6).

Resolution order for every setting is **env var > ``config/archimedes.yaml`` >
built-in default**, so ops can pin defaults in the YAML file and still override
per-run via the environment. ``load_config()`` returns the defaults verbatim when
the file is absent, so the system always has a complete, valid configuration.
"""

import logging
import os
from pathlib import Path

import yaml


logger = logging.getLogger(__name__)

WEB_PROVIDERS = ("tavily", "brave", "searxng", "none")

# The env var holding the provider's credential, per provider. searxng points at
# a self-hosted instance URL rather than an API key.
_PROVIDER_CREDENTIAL_ENV = {
    "tavily": "TAVILY_API_KEY",
    "brave": "BRAVE_API_KEY",
    "searxng": "SEARXNG_URL",
}

# Built-in defaults — the shape of the whole config tree.
DEFAULT_EMBEDDINGS_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
DEFAULT_PDF_ENGINE = "pymupdf4llm"
_DEFAULTS = {
    "search": {"web_provider": "none"},
    "embeddings": {"model": DEFAULT_EMBEDDINGS_MODEL},
    "ingestion": {"pdf_engine": DEFAULT_PDF_ENGINE},
}


def _deep_merge(base: dict, override: dict) -> dict:
    """Recursively merge ``override`` onto a copy of ``base``."""
    out = {k: (dict(v) if isinstance(v, dict) else v) for k, v in base.items()}
    for key, value in (override or {}).items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _deep_merge(out[key], value)
        else:
            out[key] = value
    return out


def _config_path(path: str | None = None) -> Path:
    """Resolve the config file path (arg > ARCHIMEDES_CONFIG env > repo default)."""
    if path:
        return Path(path)
    env_path = os.getenv("ARCHIMEDES_CONFIG")
    if env_path:
        return Path(env_path)
    # src/ai_research_engineer/core/config.py -> repo_root/config/archimedes.yaml
    return Path(__file__).resolve().parents[3] / "config" / "archimedes.yaml"


def load_config(path: str | None = None) -> dict:
    """Return the merged config: file values layered over the built-in defaults.

    When the file is absent (or unparseable) the defaults are returned unchanged,
    so callers always get the full tree with valid values.
    """
    cfg_path = _config_path(path)
    if not cfg_path.exists():
        return _deep_merge(_DEFAULTS, {})
    try:
        loaded = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
    except Exception as exc:
        logger.warning("[config] failed to parse %s (%s); using defaults", cfg_path, exc)
        loaded = {}
    if not isinstance(loaded, dict):
        loaded = {}
    return _deep_merge(_DEFAULTS, loaded)


def _resolve(env_var: str, *config_keys: str, default: str) -> str:
    """env var > config file (nested by config_keys) > default."""
    val = os.getenv(env_var)
    if val is None:
        node = load_config()
        for key in config_keys:
            node = node.get(key, {}) if isinstance(node, dict) else {}
        val = node if isinstance(node, str) else None
    return (val or default).strip()


def get_web_provider() -> str:
    """Return the configured web-search provider (one of WEB_PROVIDERS)."""
    provider = _resolve("SEARCH_WEB_PROVIDER", "search", "web_provider", default="none").lower()
    return provider if provider in WEB_PROVIDERS else "none"


def web_provider_ready() -> bool:
    """True iff a real web-search provider is selected AND its credential is set."""
    provider = get_web_provider()
    if provider == "none":
        return False
    env_name = _PROVIDER_CREDENTIAL_ENV.get(provider)
    if not env_name:
        return True
    return bool(os.getenv(env_name, "").strip())


def get_embeddings_model() -> str:
    """Embedding model id (env > config > default)."""
    return _resolve("EMBEDDINGS_MODEL", "embeddings", "model", default=DEFAULT_EMBEDDINGS_MODEL)


def get_pdf_engine() -> str:
    """PDF ingestion engine (env > config > default)."""
    return _resolve("INGESTION_PDF_ENGINE", "ingestion", "pdf_engine", default=DEFAULT_PDF_ENGINE)
