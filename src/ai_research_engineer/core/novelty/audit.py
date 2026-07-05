"""Novelty audit persistence (S2-8).

Every idea's full audit — differentiation table (joined to its prefiltered
candidates for display), prefilter top-k, recall report (per-channel counts +
channel_status), falsifier verdict, final verdict, and MVPT-as-lens — is
appended to ``knowledge_base/novelty_audit.json`` (a JSON array). This is the
artifact Stage 5's ideation memory and the S2-9 cockpit view consume.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from ai_research_engineer.core.novelty.recall import _idea_id


logger = logging.getLogger(__name__)


def audit_path(working_dir: str) -> Path:
    return Path(working_dir) / "knowledge_base" / "novelty_audit.json"


def build_audit_entry(
    idea: dict,
    *,
    verdict: dict,
    table: List[dict],
    prefiltered: List[dict],
    recall: Optional[dict] = None,
    mvpt: Optional[dict] = None,
) -> dict:
    """Assemble one idea's audit entry. Differentiation rows are joined to their
    prefiltered candidate so each card carries a title / url / source badge."""
    by_id: dict = {}
    for c in prefiltered or []:
        for key in (c.get("id"), c.get("url")):
            if key:
                by_id[str(key)] = c

    cards = []
    for row in table or []:
        wid = str(row.get("work_id") or "")
        cand = by_id.get(wid, {})
        cards.append({
            "work_id": wid,
            "overlap_summary": row.get("overlap_summary"),
            "differs_because": row.get("differs_because"),
            "overlap_severity": row.get("overlap_severity"),
            "title": cand.get("title") or wid,
            "url": cand.get("url"),
            "source": cand.get("source") or cand.get("source_channel"),
        })

    return {
        "idea_id": _idea_id(idea),
        "idea_title": idea.get("title") or "",
        "idea_description": idea.get("description") or "",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "approved": bool(verdict.get("approved")),
        "verdict": verdict.get("verdict"),
        "reason": verdict.get("reason"),
        "differentiation_table": cards,
        "prefiltered": prefiltered or [],
        "recall": recall or {},
        "falsifier": {
            "rounds": verdict.get("falsifier_rounds"),
            "verdict": "reject" if not verdict.get("approved") else "approve",
            "killing_works": verdict.get("killing_works", []),
        },
        "mvpt": mvpt,
    }


def append_audit(working_dir: str, entry: dict) -> Path:
    """Append one audit entry to novelty_audit.json (creating it as an array)."""
    path = audit_path(working_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    audits = load_audits(working_dir)
    audits.append(entry)
    path.write_text(json.dumps(audits, indent=2), encoding="utf-8")
    return path


def load_audits(working_dir: str) -> List[dict]:
    """Return the audit array (empty list when missing or unreadable)."""
    path = audit_path(working_dir)
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        logger.debug("[audit] unreadable novelty_audit.json: %s", exc)
        return []
    return data if isinstance(data, list) else []
