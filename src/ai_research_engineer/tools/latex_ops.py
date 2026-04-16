"""
LaTeX operations for the AI Research Engineer.
Allows agents to compile .tex files to PDF and catch syntax errors.
"""

import logging
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)


def compile_latex_to_pdf(tex_file_name: str, working_dir: str) -> str:
    """
    Compiles a .tex file into a PDF using pdflatex.
    The file must be located in the 'manuscript/' directory of the workspace.

    Args:
        tex_file_name: The name of the .tex file (e.g., 'main.tex')
        working_dir: The root workspace directory
    """
    logger.info(f"[Tool:compile_latex] Compiling {tex_file_name}")
    try:
        manuscript_dir = Path(working_dir) / "manuscript"
        tex_path = manuscript_dir / tex_file_name

        if not tex_path.exists():
            return f"Error: Could not find {tex_file_name} in {manuscript_dir}"

        # Run pdflatex twice to resolve TOC and references
        for pass_num in range(1, 3):
            logger.info(f"Running pdflatex pass {pass_num}...")
            result = subprocess.run(
                ["pdflatex", "-interaction=nonstopmode", "-halt-on-error", tex_file_name],
                cwd=str(manuscript_dir),
                capture_output=True,
                text=True,
                check=False,
            )

            if result.returncode != 0:
                # Extract the actual error from the massive LaTeX log
                log_lines = result.stdout.splitlines()
                error_context = "\n".join(log_lines[-20:])  # Grab the bottom where the error is
                return (
                    f"LaTeX Compilation FAILED on pass {pass_num}.\n\n"
                    f"Error Log:\n{error_context}\n\n"
                    f"Please fix the syntax errors in {tex_file_name} and recompile."
                )

        pdf_name = tex_file_name.replace(".tex", ".pdf")
        pdf_path = manuscript_dir / pdf_name

        if pdf_path.exists():
            # Move it to results for the final output
            final_dest = Path(working_dir) / "results" / "final_research_paper.pdf"
            final_dest.write_bytes(pdf_path.read_bytes())
            return "SUCCESS: LaTeX compiled perfectly! PDF saved to results/final_research_paper.pdf"
        else:
            return "Error: pdflatex ran without crashing, but no PDF was generated."

    except Exception as e:
        return f"Exception during compilation: {str(e)}"
