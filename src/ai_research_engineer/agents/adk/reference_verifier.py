"""
Reference verifier agent — custom BaseAgent (no LLM calls).

Appended after paper_writing_loop in the SequentialAgent workflow. Runs before
_compile_latex() to produce a non-blocking citation integrity report.

What it does:
  1. Reads manuscript/*.tex and *.md to collect all in-text cite keys.
  2. Parses manuscript/references.bib to get the known bib keys.
  3. Finds hallucinated keys (in text, not in .bib) — zero network cost.
  4. Calls verify_online() on all .bib entries (Crossref→OpenAlex→URL-HEAD, cached).
  5. Writes manuscript/verification_report.md.
  6. Stores counts in ctx.session.state["_verification_counts"] so that
     _stream_responses can emit a VerificationEvent after the runner exits.
  7. Adds an audit_note to the argument tree (fail-soft).

Iron rule: never raises, never modifies manuscript/.bib, never blocks compilation.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, AsyncGenerator

from google.adk.agents import BaseAgent, InvocationContext
from google.adk.events import Event
from google.genai import types
from pydantic import PrivateAttr


logger = logging.getLogger(__name__)


class ReferenceVerifierAgent(BaseAgent):
    """Non-LLM citation verifier; yields a single summary Event."""

    _working_dir: Any = PrivateAttr()

    def __init__(
        self,
        working_dir: str,
        name: str = "reference_verifier_agent",
        description: str = "Verifies bibliography citations and reports hallucinated or unconfirmed references.",
    ) -> None:
        super().__init__(name=name, description=description)
        self._working_dir = Path(working_dir)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _tree_safe(fn, *args, **kwargs):
        """Call fn(*args, **kwargs), swallow any exception — tree is observability only."""
        try:
            return fn(*args, **kwargs)
        except Exception as exc:
            logger.warning("[RefVerifier] tree write ignored: %s", exc)
            return None

    def _event(self, text: str) -> Event:
        return Event(
            author=self.name,
            content=types.Content(role="model", parts=[types.Part(text=text)]),
            turn_complete=True,
        )

    # ------------------------------------------------------------------
    # Core logic
    # ------------------------------------------------------------------

    async def _run_async_impl(self, ctx: InvocationContext) -> AsyncGenerator[Event, None]:
        from ai_research_engineer.core.references import (
            find_unknown_cite_keys,
            parse_bib,
            verify_online,
        )

        manuscript_dir = self._working_dir / "manuscript"
        bib_path = manuscript_dir / "references.bib"
        report_path = manuscript_dir / "verification_report.md"
        cache_path = self._working_dir / ".data" / "ref_cache.db"

        _empty_counts = {
            "total": 0, "verified": 0, "not_found": 0,
            "unverified": 0, "hallucinated": 0, "report_path": "",
        }

        if not manuscript_dir.exists():
            logger.warning("[RefVerifier] manuscript/ not found — skipping verification")
            ctx.session.state["_verification_counts"] = _empty_counts
            yield self._event("[RefVerifier] manuscript/ directory not found — citation verification skipped.")
            return

        # 1. Collect manuscript text (all .tex and .md except the report itself)
        manuscript_text = ""
        for pattern in ("*.tex", "*.md"):
            for p in sorted(manuscript_dir.glob(pattern)):
                if p.name == "verification_report.md":
                    continue
                try:
                    manuscript_text += p.read_text(encoding="utf-8", errors="ignore") + "\n"
                except OSError:
                    pass

        # 2. Parse .bib
        bib_entries = parse_bib(bib_path) if bib_path.exists() else {}
        bib_keys = set(bib_entries.keys())

        # 3. Hallucinated keys — pure text, zero cost
        hallucinated: set[str] = find_unknown_cite_keys(manuscript_text, bib_keys) if manuscript_text else set()

        # 4. Online verification with cache
        verification_results = []
        if bib_entries:
            try:
                verification_results = verify_online(bib_entries, cache_db_path=cache_path)
            except Exception as exc:
                logger.warning("[RefVerifier] verify_online fail-soft: %s", exc)

        # 5. Tally
        verified = sum(1 for r in verification_results if r["status"] == "verified")
        not_found = sum(1 for r in verification_results if r["status"] == "not_found")
        unverified_count = sum(1 for r in verification_results if r["status"] == "unverified")
        total = len(bib_entries)

        # 6. Write verification_report.md
        lines = [
            "# Citation Verification Report",
            "",
            f"**Total references in .bib:** {total}  ",
            f"**Verified online:** {verified}  ",
            f"**Not found:** {not_found}  ",
            f"**Unverified (network/parse error):** {unverified_count}  ",
            f"**Hallucinated cite keys** (in text, not in .bib): {len(hallucinated)}",
            "",
        ]

        if hallucinated:
            lines += ["## Hallucinated Citation Keys", ""]
            for k in sorted(hallucinated):
                lines.append(f"- `{k}` — cited in manuscript but absent from references.bib")
            lines.append("")

        problem = [r for r in verification_results if r["status"] in ("not_found", "unverified")]
        if problem:
            lines += ["## References Requiring Attention", ""]
            for r in problem:
                label = "NOT FOUND" if r["status"] == "not_found" else "UNVERIFIED"
                lines.append(f"- `{r['key']}` [{label}] via `{r['method']}`: {r.get('detail', '')}")
            lines.append("")

        ok = [r for r in verification_results if r["status"] == "verified"]
        if ok:
            lines += ["## Verified References", ""]
            for r in ok:
                cached = " (cached)" if r.get("cached") else ""
                lines.append(f"- `{r['key']}` ✓ via `{r['method']}`{cached}")
            lines.append("")

        try:
            manuscript_dir.mkdir(parents=True, exist_ok=True)
            report_path.write_text("\n".join(lines), encoding="utf-8")
            logger.info("[RefVerifier] wrote %s", report_path)
        except OSError as exc:
            logger.warning("[RefVerifier] could not write report: %s", exc)

        # 7. Store counts in session state for VerificationEvent emission
        rel_report = ""
        try:
            rel_report = str(report_path.relative_to(self._working_dir))
        except ValueError:
            rel_report = str(report_path)

        counts = {
            "total": total,
            "verified": verified,
            "not_found": not_found,
            "unverified": unverified_count,
            "hallucinated": len(hallucinated),
            "report_path": rel_report,
        }
        ctx.session.state["_verification_counts"] = counts

        # 8. Argument tree audit note (fail-soft)
        def _write_tree_note() -> None:
            from ai_research_engineer.core.argument_tree import TreeBuilder

            tree = TreeBuilder(ctx.session.id)
            try:
                root = tree.get_root()
                parent_id = root["node_id"] if root else None
                summary = (
                    f"Citations verified: {verified}/{total}. "
                    f"Not found: {not_found}. Unverified: {unverified_count}. "
                    f"Hallucinated keys: {len(hallucinated)}."
                )
                tree.add_audit_note(
                    label="Reference Verification",
                    content=summary,
                    parent_id=parent_id,
                    metadata={**counts, "hallucinated_keys": sorted(hallucinated)},
                )
            finally:
                tree.close()

        self._tree_safe(_write_tree_note)

        # 9. Summary event
        hallucinated_note = ""
        if hallucinated:
            sample = ", ".join(sorted(hallucinated)[:5])
            more = f" …+{len(hallucinated) - 5} more" if len(hallucinated) > 5 else ""
            hallucinated_note = f"\n- ⚠️ **{len(hallucinated)} hallucinated** key(s): `{sample}`{more}"

        summary = (
            f"\n\n### Reference Verification Complete\n\n"
            f"- **{total}** references in .bib\n"
            f"- **{verified}** verified | **{not_found}** not found | **{unverified_count}** unverified"
            f"{hallucinated_note}\n"
            f"\nFull report → `{report_path.name}`\n\n"
        )
        yield self._event(summary)

    async def _run_live_impl(self, ctx: InvocationContext) -> AsyncGenerator[Event, None]:
        raise NotImplementedError("Live mode is not supported for ReferenceVerifierAgent.")
