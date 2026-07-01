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
