"""Unit tests for prompt loading and domain validation."""

import pytest

from ai_research_engineer.prompts import load_prompt


class TestLoadPrompt:
    def test_valid_domain_injects_text(self):
        """load_prompt with domain='aiml' should inject domain methodology text."""
        result = load_prompt("idea_generator", "aiml")
        assert isinstance(result, str)
        assert len(result) > 0
        # The base prompt contains $global_preamble; it should have been replaced.
        assert "$global_preamble" not in result

    def test_unknown_domain_raises_value_error(self):
        """Passing an unknown domain must raise ValueError naming valid domains."""
        with pytest.raises(ValueError, match="Unknown domain 'ai_ml'"):
            load_prompt("idea_generator", "ai_ml")

    def test_unknown_domain_error_lists_valid_domains(self):
        """The ValueError message must include the valid domain names."""
        with pytest.raises(ValueError) as exc_info:
            load_prompt("idea_generator", "notreal")
        msg = str(exc_info.value)
        for domain in ("aiml", "finance", "bioinformatics", "algorithms", "physics"):
            assert domain in msg

    def test_missing_base_prompt_raises_file_not_found(self):
        """Requesting a nonexistent prompt name raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            load_prompt("does_not_exist", "aiml")

    def test_each_valid_domain_loads(self):
        """All valid domain names must work without error for idea_generator."""
        for domain in ("aiml", "finance", "bioinformatics", "algorithms", "physics"):
            result = load_prompt("idea_generator", domain)
            assert isinstance(result, str), f"Failed for domain: {domain}"


class TestConditionalToolSections:
    """S0-7: <!-- BEGIN:graphify -->..<!-- END:graphify --> blocks are dropped
    when graphify is unavailable and kept (markers removed) when available."""

    def test_graphify_stripped_from_both_coding_prompts(self):
        for name in ("coding_base", "coding_review"):
            stripped = load_prompt(name, tool_availability={"graphify": False})
            assert "graphify" not in stripped.lower(), f"{name} still mentions graphify when unavailable"
            # Markers must never leak into the assembled prompt.
            assert "BEGIN:graphify" not in stripped
            assert "END:graphify" not in stripped

    def test_graphify_retained_when_available(self):
        for name in ("coding_base", "coding_review"):
            available = load_prompt(name, tool_availability={"graphify": True})
            assert "graphify" in available.lower(), f"{name} lost graphify guidance when available"
            assert "BEGIN:graphify" not in available
            assert "END:graphify" not in available

    def test_default_keeps_graphify_and_strips_markers(self):
        # No tool_availability -> tools default to available; markers still removed.
        for name in ("coding_base", "coding_review"):
            default = load_prompt(name)
            assert "graphify" in default.lower()
            assert "BEGIN:graphify" not in default


class TestImplementationReviewConfirmationPrompt:
    """S0-6: the confirmation prompt FILE must gate on the coding review only —
    no ideation / novelty / tier language leaking in from the old cross-wired
    gate. (Assert on the raw file, not the assembled prompt: the injected
    $global_preamble legitimately discusses research novelty.)"""

    def _raw_file(self) -> str:
        from pathlib import Path

        import ai_research_engineer.prompts as prompts_pkg

        path = Path(prompts_pkg.__file__).parent / "base" / "implementation_review_confirmation.md"
        return path.read_text(encoding="utf-8")

    def test_no_ideation_or_novelty_language(self):
        content = self._raw_file().lower()
        for forbidden in ("ideation", "novelty", "mvpt", "publication_tier", "tier_"):
            assert forbidden not in content, f"forbidden token '{forbidden}' present in confirmation prompt file"

    def test_gates_on_reviewer_output(self):
        content = self._raw_file()
        # It must reference the reviewer feedback and the blocking-issues gate.
        assert "{review_feedback?}" in content
        assert "blocking" in content.lower()
        assert "review_degraded" in content
