"""
Templates for Claude Code agent configuration.

This module provides functions to generate instructions and context
for the Claude Code agent.
"""

import logging
from string import Template
from typing import Any, Dict


logger = logging.getLogger(__name__)


def get_claude_instructions(state: Dict[str, Any], working_dir: str) -> str:
    """
    Generate system instructions for Claude Code agent.

    Parameters
    ----------
    state : dict
        The state dictionary containing variables for template substitution.
    working_dir : str
        The working directory path where execution will occur.

    Returns
    -------
    str
        The complete system instructions with substituted variables.
    """
    # Load the coding base prompt
    try:
        from ai_research_engineer.prompts import load_prompt

        base_content = load_prompt("coding_base")
    except FileNotFoundError:
        # Fallback to a simple default
        base_content = """You are an ML coding assistant. Implement the given task completely and thoroughly.

Working directory: $working_dir

Task: $implementation_task

Plan: $implementation_plan

Requirements:
1. Complete ALL steps in the plan
2. Save all outputs with descriptive filenames
3. Print progress updates after each step
4. Generate comprehensive documentation
5. Create final execution summary when done"""

    # Create substitutions dictionary
    substitutions = {'working_dir': working_dir}

    # Add all state variables
    for key, value in state.items():
        if value is None:
            value = ""
        elif not isinstance(value, str):
            value = str(value)

        # Truncate very long values
        MAX_CHARS = 40000
        if len(value) > MAX_CHARS:
            substitutions[key] = value[:MAX_CHARS] + "\n\n[... truncated for length ...]"
        else:
            substitutions[key] = value

    # Substitute variables
    template = Template(base_content)
    result = template.safe_substitute(**substitutions)

    # Append critical file handling constraints
    file_handling_constraints = """

CRITICAL FILE HANDLING CONSTRAINTS:
=====================================
Claude Agent SDK has a 1MB buffer limit for tool responses. To prevent buffer overflow errors:

1. DO NOT read files larger than 1MB directly using the Read tool
2. For large CSV/data files:
   - Use command-line tools (ls -lh, wc -l, head, tail) to inspect first
   - Use pandas with nrows parameter to load only portions: pd.read_csv('file.csv', nrows=1000)
   - Process files in chunks using pandas chunksize parameter
3. Check file sizes before reading:
   - Use bash: ls -lh filename.csv
   - Only read files under 1MB directly
4. For files >1MB:
   - Sample the data (head/tail commands)
   - Load incrementally with pandas
   - Use streaming/iterative processing

Violating these constraints will cause "JSON message exceeded maximum buffer size" errors.
"""

    result += file_handling_constraints

    return result


def get_claude_context(
    implementation_plan: str,
    working_dir: str,
    original_request: str = "",
    completed_stages: list = None,
    all_stages: list = None,
) -> str:
    """
    Generate the initial user context/prompt for Claude with comprehensive context.
    """
    # Format optional context sections
    context_sections = []

    # 1. ANALYSIS CONTEXT SECTION
    if original_request:
        context_sections.append("## RESEARCH CONTEXT\n")

        # Truncate if too long
        MAX_REQUEST_LENGTH = 2000
        truncated_request = original_request
        if len(original_request) > MAX_REQUEST_LENGTH:
            truncated_request = original_request[:MAX_REQUEST_LENGTH] + "\n[... truncated ...]"
        context_sections.append(f"### Original Request\n{truncated_request}\n\n")

    # 2. COMPLETED WORK SECTION
    if completed_stages:
        context_sections.append("## COMPLETED STAGES\n")
        context_sections.append("Previous stages that have been implemented:\n\n")
        for completed in completed_stages:
            if isinstance(completed, dict):
                stage_title = completed.get('stage_title', 'Unknown Stage')
                # Keep only brief summary, not full implementation details
                stage_summary = completed.get('implementation_summary', 'No summary available')
                # Truncate to first 300 chars if longer
                if len(stage_summary) > 300:
                    stage_summary = stage_summary[:300] + "..."
                context_sections.append(f"- **{stage_title}**: {stage_summary}\n")
        context_sections.append("\n")

    # 3. FULL ANALYSIS PLAN SECTION
    if all_stages:
        context_sections.append("## FULL EXPERIMENTAL PLAN\n")
        context_sections.append("Here's the complete stage sequence (for context and continuity):\n\n")
        for stage in all_stages:
            if isinstance(stage, dict):
                stage_index = stage.get('index', 0)
                stage_title = stage.get('title', 'Unknown')
                is_completed = stage.get('completed', False)
                is_current = not is_completed and (
                    not completed_stages
                    or all(c.get('stage_index', -1) != stage_index for c in completed_stages if isinstance(c, dict))
                )

                status = ""
                if is_completed:
                    status = " [COMPLETED]"
                elif is_current:
                    status = " [CURRENT - IMPLEMENT THIS]"
                else:
                    status = " [UPCOMING]"

                context_sections.append(f"{stage_index + 1}. **{stage_title}**{status}\n")
                # Include brief description for upcoming stages only
                if not is_completed and not is_current:
                    stage_desc = stage.get('description', '')
                    if len(stage_desc) > 200:
                        stage_desc = stage_desc[:200] + "..."
                    context_sections.append(f"   {stage_desc}\n")
        context_sections.append("\n")

    # Truncate plan if too long
    MAX_PLAN_LENGTH = 100000
    truncated_plan = implementation_plan

    if len(implementation_plan) > MAX_PLAN_LENGTH:
        keep_start = MAX_PLAN_LENGTH * 3 // 4
        keep_end = MAX_PLAN_LENGTH // 4
        truncated_plan = (
            implementation_plan[:keep_start]
            + "\n\n[... middle section truncated to prevent token limit errors ...]\n\n"
            + implementation_plan[-keep_end:]
        )
        logger.warning(
            f"Implementation plan truncated from {len(implementation_plan)} to {len(truncated_plan)} characters"
        )

    # Build the full context with optional sections
    context_prefix = "".join(context_sections) if context_sections else ""

    context = f"""{context_prefix}## YOUR CURRENT TASK

Execute the following stage implementation COMPLETELY and THOROUGHLY.

Working directory: {working_dir}

CURRENT STAGE TO IMPLEMENT:
{truncated_plan}

CRITICAL ML RESEARCH REQUIREMENTS:
1. READ THE BLUEPRINT: You MUST read `knowledge_base/02_methodology_specs.md` before writing any code.
2. Complete ALL aspects of this stage - no partial execution.
3. Save all neural network weights, plots, and metrics with descriptive filenames using {working_dir}/results/ prefix.
4. Ensure your Deep Learning code is device-agnostic (CPU/CUDA/MPS) and sets random seeds for reproducibility.
5. Print training progress updates (e.g., loss every N epochs) so the orchestrator knows you haven't hung.
6. Update README.md incrementally - DO NOT create separate summary files.

FILE HANDLING CONSTRAINTS (CRITICAL):
- DO NOT read files >1MB directly - use head/tail or pandas with nrows parameter
- Check file sizes first: ls -lh filename.csv
- Violating this causes "JSON buffer exceeded" errors

You MUST implement the entire stage. Parse it into concrete steps, execute them thoroughly, and verify all aspects are complete."""

    return context


def get_minimal_pyproject() -> str:
    """
    Get a minimal pyproject.toml content for the session.

    Returns
    -------
    str
        The pyproject.toml content.
    """
    return """[project]
name = "ai-research-engineer-session"
version = "0.1.0"
requires-python = ">=3.12,<3.13"
dependencies = [
    # Core Deep Learning & ML
    "torch>=2.2.0",
    "torchvision>=0.17.0",
    "transformers>=4.38.0",
    "datasets>=2.18.0",
    "accelerate>=0.27.0",
    "einops>=0.7.0",
    
    # Core scientific computing
    "numpy>=1.26.0",
    "pandas>=2.0.0",
    "matplotlib>=3.8.0",
    "scipy>=1.11.0",
    "seaborn>=0.13.0",
    "scikit-learn>=1.3.0",
    
    # Data formats and utilities
    "pyyaml>=6.0.0",
    "pillow>=10.0.0",
    "requests>=2.31.0",
    
    # Additional utilities
    "tqdm>=4.66.0",
    "plotly>=5.17.0",
    "wandb>=0.16.0",
    
    # Environment management
    "python-dotenv>=1.0.0",
]
"""