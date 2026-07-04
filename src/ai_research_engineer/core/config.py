"""Lightweight configuration accessors (S1-3; formalized in S1-6).

For now configuration is read from environment variables. S1-6 will introduce
``config/archimedes.yaml`` as the single source of truth and layer env overrides
on top of it; these accessors are the seam the rest of the code depends on.
"""

import os


WEB_PROVIDERS = ("tavily", "brave", "searxng", "none")

# The env var holding the provider's credential, per provider. searxng points at
# a self-hosted instance URL rather than an API key.
_PROVIDER_CREDENTIAL_ENV = {
    "tavily": "TAVILY_API_KEY",
    "brave": "BRAVE_API_KEY",
    "searxng": "SEARXNG_URL",
}


def get_web_provider() -> str:
    """Return the configured web-search provider (one of WEB_PROVIDERS)."""
    provider = os.getenv("SEARCH_WEB_PROVIDER", "none").strip().lower()
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
    """Embedding model id (S1-1 default; overridable via env)."""
    return os.getenv("EMBEDDINGS_MODEL", "sentence-transformers/all-MiniLM-L6-v2").strip()


def get_pdf_engine() -> str:
    """PDF ingestion engine (S1-2 default)."""
    return os.getenv("INGESTION_PDF_ENGINE", "pymupdf4llm").strip()
