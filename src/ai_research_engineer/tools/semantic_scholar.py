"""Unified Semantic Scholar access (S0-8).

A single module-level client and a single thread-safe 1-request-per-second rate
limiter, shared by BOTH ``research_ops`` and ``semantic_scholar_ops`` so the S2
rate limit is respected across every caller — including across threads.
"""

import logging
import os
import threading
import time

from semanticscholar import SemanticScholar


logger = logging.getLogger(__name__)

# One shared client for the whole process.
_api_key = os.getenv("SEMANTIC_SCHOLAR_API_KEY")
client = SemanticScholar(api_key=_api_key)

# One shared, thread-safe limiter (Semantic Scholar's unauthenticated limit is
# ~1 request/second).
MIN_INTERVAL_S = 1.0
_lock = threading.Lock()
_last_call = 0.0


def enforce_rate_limit() -> None:
    """Block until at least ``MIN_INTERVAL_S`` has elapsed since the previous call.

    Thread-safe: the lock is held across the sleep, so concurrent callers are
    serialised and spaced by at least ``MIN_INTERVAL_S`` — the limiter can never
    be violated by two threads racing.
    """
    global _last_call
    with _lock:
        wait = MIN_INTERVAL_S - (time.monotonic() - _last_call)
        if wait > 0:
            time.sleep(wait)
        _last_call = time.monotonic()


__all__ = ["client", "enforce_rate_limit", "MIN_INTERVAL_S"]
