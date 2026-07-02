"""Unit tests for core/pricing.py."""

from ai_research_engineer.core.pricing import cost_usd, load_pricing


class TestLoadPricing:
    def test_returns_dict(self):
        table = load_pricing()
        assert isinstance(table, dict)

    def test_known_model_present(self):
        table = load_pricing()
        assert "claude-sonnet-4-6" in table

    def test_entry_has_required_fields(self):
        table = load_pricing()
        entry = table["claude-sonnet-4-6"]
        for field in ("input_per_mtok", "output_per_mtok", "cache_read_per_mtok"):
            assert field in entry
            assert isinstance(entry[field], (int, float))


class TestCostUsd:
    def test_known_model_nonzero(self):
        # claude-sonnet-4-6: $3/MTok input, $15/MTok output
        usd = cost_usd("claude-sonnet-4-6", input_tokens=1_000_000, output_tokens=1_000_000)
        assert abs(usd - 18.0) < 0.01

    def test_zero_tokens_returns_zero(self):
        assert cost_usd("claude-sonnet-4-6", 0, 0) == 0.0

    def test_unknown_model_returns_zero(self):
        assert cost_usd("totally-unknown-model-xyz", 1_000_000, 500_000) == 0.0

    def test_none_model_returns_zero(self):
        assert cost_usd(None, 1_000_000, 500_000) == 0.0

    def test_cached_tokens_cheaper_than_input(self):
        # Cached tokens use cache_read rate, which is lower than input rate.
        usd_no_cache = cost_usd("claude-sonnet-4-6", input_tokens=100_000, output_tokens=0)
        usd_cached = cost_usd("claude-sonnet-4-6", input_tokens=100_000, output_tokens=0, cached_tokens=100_000)
        assert usd_cached < usd_no_cache

    def test_cached_tokens_exact_arithmetic(self):
        # 1M cached tokens at $0.30/MTok cache_read, 0 non-cached, 0 output
        usd = cost_usd("claude-sonnet-4-6", input_tokens=1_000_000, output_tokens=0, cached_tokens=1_000_000)
        assert abs(usd - 0.30) < 0.001

    def test_partial_cache_arithmetic(self):
        # 500k non-cached input at $3/MTok + 500k cached at $0.30/MTok
        usd = cost_usd("claude-sonnet-4-6", input_tokens=1_000_000, output_tokens=0, cached_tokens=500_000)
        expected = 0.5 * 3.0 + 0.5 * 0.30
        assert abs(usd - expected) < 0.001

    def test_cached_tokens_exceeding_input_clamped(self):
        # cached_tokens > input_tokens → non_cached = max(0, ...) = 0
        usd = cost_usd("claude-sonnet-4-6", input_tokens=100, output_tokens=0, cached_tokens=200)
        # Only cached portion: 100 tokens at cache_read rate
        expected = 100 / 1_000_000 * 0.30
        assert abs(usd - expected) < 1e-9

    def test_openrouter_fallback(self):
        usd = cost_usd("openrouter/some-model", input_tokens=1_000_000, output_tokens=0)
        # openrouter/default: $1/MTok input
        assert abs(usd - 1.0) < 0.01

    def test_output_only(self):
        # 1M output at $15/MTok
        usd = cost_usd("claude-sonnet-4-6", input_tokens=0, output_tokens=1_000_000)
        assert abs(usd - 15.0) < 0.01

    def test_gemini_model(self):
        usd = cost_usd("gemini-2.5-pro", input_tokens=1_000_000, output_tokens=0)
        assert usd > 0.0

    def test_returns_float(self):
        result = cost_usd("claude-sonnet-4-6", 100, 50)
        assert isinstance(result, float)
