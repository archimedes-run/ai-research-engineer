"""S0-8: unified Semantic Scholar client + thread-safe 1-rps limiter."""

import threading
import time

from ai_research_engineer.tools import semantic_scholar as s2


class TestUnifiedClient:
    def test_both_modules_share_one_client(self):
        from ai_research_engineer.tools import research_ops, semantic_scholar_ops

        assert research_ops.sch is s2.client
        assert semantic_scholar_ops.sch is s2.client

    def test_both_modules_share_one_limiter(self):
        from ai_research_engineer.tools import research_ops, semantic_scholar_ops

        assert research_ops.enforce_rate_limit is s2.enforce_rate_limit
        # semantic_scholar_ops keeps the historical alias name.
        assert semantic_scholar_ops._enforce_1_rps_limit is s2.enforce_rate_limit


class TestRateLimiterConcurrency:
    def test_two_threads_never_violate_1rps(self, monkeypatch):
        """Two threads calling the shared limiter must be spaced >= the interval
        apart — the 1 rps limit is never violated by a race."""
        monkeypatch.setattr(s2, "_last_call", 0.0)

        release_times = []
        record_lock = threading.Lock()

        def worker():
            s2.enforce_rate_limit()
            with record_lock:
                release_times.append(time.monotonic())

        threads = [threading.Thread(target=worker) for _ in range(2)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(release_times) == 2
        release_times.sort()
        gap = release_times[1] - release_times[0]
        assert gap >= s2.MIN_INTERVAL_S - 0.1, f"two S2 calls only {gap:.3f}s apart — 1 rps limiter violated"
