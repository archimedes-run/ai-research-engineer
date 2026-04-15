"""Prompt templates and loading utilities."""

from pathlib import Path
import logging

logger = logging.getLogger(__name__)

def load_prompt(name: str, domain: str = "aiml") -> str:
    """
    Load prompt template by name and inject the domain-specific methodology.
    """
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

        # Load the base Universal Scientific rules
        preamble_text = preamble_path.read_text(encoding="utf-8") if preamble_path.exists() else ""
        
        # Load your newly written Domain-Specific Methodology
        domain_text = ""
        if domain_path.exists():
            domain_text = domain_path.read_text(encoding="utf-8")
        else:
            logger.warning(f"Domain context file not found for '{domain}'. Using base preamble only.")

        # Stitch them together
        full_preamble = f"{preamble_text}\n\n{domain_text}"
        
        # Inject into the base prompt
        content = content.replace("$global_preamble", full_preamble)

    return content

__all__ = ["load_prompt"]