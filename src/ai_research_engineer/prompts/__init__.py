"""Prompt templates and loading utilities."""

from pathlib import Path
import logging

logger = logging.getLogger(__name__)


def _valid_domains() -> set:
    domain_dir = Path(__file__).parent / "domain"
    return {p.name for p in domain_dir.iterdir() if p.is_dir() and p.name != "__pycache__"}


def load_prompt(name: str, domain: str = "aiml") -> str:
    """
    Load prompt template by name and inject the domain-specific methodology.

    Parameters
    ----------
    name : str
        Base prompt name (without extension), e.g. ``"idea_generator"``.
    domain : str
        Domain subdirectory under ``prompts/domain/``.  Valid values are the
        directory names that actually exist there (``aiml``, ``finance``,
        ``bioinformatics``, ``algorithms``, ``physics``).

    Raises
    ------
    FileNotFoundError
        If the base prompt template does not exist.
    ValueError
        If *domain* is not one of the valid domain directories.
    """
    valid = _valid_domains()
    if domain not in valid:
        raise ValueError(
            f"Unknown domain '{domain}'. Valid domains: {sorted(valid)}"
        )

    prompts_dir = Path(__file__).parent

    # 1. Always load the base prompt (e.g., base/idea_generator.md)
    base_path = prompts_dir / "base" / f"{name}.md"

    if not base_path.exists():
        raise FileNotFoundError(f"Base prompt not found: {base_path}")

    content = base_path.read_text(encoding="utf-8")

    # 2. If the prompt uses the $global_preamble tag, perform Template Injection
    if "$global_preamble" in content:
        preamble_path = prompts_dir / "base" / "global_preamble.md"
        domain_path = prompts_dir / "domain" / domain / "science_methodology.md"

        preamble_text = preamble_path.read_text(encoding="utf-8") if preamble_path.exists() else ""

        domain_text = domain_path.read_text(encoding="utf-8") if domain_path.exists() else ""

        full_preamble = f"{preamble_text}\n\n{domain_text}"
        content = content.replace("$global_preamble", full_preamble)

    return content


__all__ = ["load_prompt"]