"""
LaTeX operations for the AI Research Engineer.
Allows agents to compile .tex files to PDF and catch syntax errors.
"""

import logging
import shutil
import subprocess
from pathlib import Path


logger = logging.getLogger(__name__)


def compile_latex_to_pdf(tex_file_name: str, working_dir: str) -> str:
    """
    Compiles a .tex file into a PDF using pdflatex (preferred) or tectonic (fallback).
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

        # Choose compiler: prefer pdflatex, fall back to tectonic
        if shutil.which("pdflatex"):
            return _compile_pdflatex(tex_file_name, manuscript_dir, working_dir)
        elif shutil.which("tectonic"):
            return _compile_tectonic(tex_file_name, manuscript_dir, working_dir)
        else:
            return (
                "Error: No LaTeX compiler found. "
                "Install pdflatex (TeX Live / MacTeX) or tectonic (https://tectonic-typesetting.github.io)."
            )

    except Exception as e:
        return f"Exception during compilation: {str(e)}"


def _compile_pdflatex(tex_file_name: str, manuscript_dir: Path, working_dir: str) -> str:
    """Run pdflatex twice to resolve cross-references."""
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
            log_lines = result.stdout.splitlines()
            error_context = "\n".join(log_lines[-20:])
            return (
                f"LaTeX Compilation FAILED on pass {pass_num}.\n\n"
                f"Error Log:\n{error_context}\n\n"
                f"Please fix the syntax errors in {tex_file_name} and recompile."
            )

    pdf_name = tex_file_name.replace(".tex", ".pdf")
    return _finalize_pdf(manuscript_dir / pdf_name, working_dir, tex_file_name)


def _compile_tectonic(tex_file_name: str, manuscript_dir: Path, working_dir: str) -> str:
    """Run tectonic (handles multiple passes and package downloads automatically)."""
    logger.info("Running tectonic...")
    result = subprocess.run(
        ["tectonic", tex_file_name],
        cwd=str(manuscript_dir),
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        error_output = (result.stderr or result.stdout or "")[-2000:]
        return (
            f"LaTeX Compilation FAILED (tectonic).\n\n"
            f"Error:\n{error_output}\n\n"
            f"Please fix the syntax errors in {tex_file_name} and recompile."
        )

    pdf_name = tex_file_name.replace(".tex", ".pdf")
    return _finalize_pdf(manuscript_dir / pdf_name, working_dir, tex_file_name)


def _finalize_pdf(pdf_path: Path, working_dir: str, tex_file_name: str) -> str:
    """Copy the compiled PDF to results/ and return a success message."""
    if not pdf_path.exists():
        return f"Error: compiler ran without error but no PDF was produced for {tex_file_name}."

    final_dest = Path(working_dir) / "results" / "final_research_paper.pdf"
    final_dest.parent.mkdir(parents=True, exist_ok=True)
    final_dest.write_bytes(pdf_path.read_bytes())
    return "SUCCESS: LaTeX compiled perfectly! PDF saved to results/final_research_paper.pdf"
