"""
Argument tree: evidence-linked DAG stored in .data/pipeline.db.

All reads/writes use the same WAL-mode SQLite database as RunStore.
TreeBuilder is self-initialising (creates tables on construction) so
CLI runs that don't start the server still work.

Design: every node has a type, a label, optional content, a status,
and a JSON metadata blob.  Edges are directed parent → child.
"""

import json
import logging
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Valid node types
# ---------------------------------------------------------------------------

VALID_NODE_TYPES = {
    # SEEKER originals
    "root",
    "claim",
    "evidence",
    "question",
    "objection",
    "response",
    "premise",
    "inference",
    # Archimedes extensions
    "experiment",
    "result",
    "artifact",
    "hypothesis",
}

VALID_STATUSES = {
    "supported",
    "unsupported",
    "weak",
    "pending",
    "completed",
    "failed",
    "active",
}

# ---------------------------------------------------------------------------
# Schema (IF NOT EXISTS — safe to run alongside RunStore schema)
# ---------------------------------------------------------------------------

_SCHEMA = """
CREATE TABLE IF NOT EXISTS argument_tree (
  node_id    TEXT PRIMARY KEY,
  run_id     TEXT NOT NULL,
  parent_id  TEXT,
  type       TEXT NOT NULL,
  label      TEXT NOT NULL,
  content    TEXT,
  status     TEXT DEFAULT 'pending',
  metadata   TEXT DEFAULT '{}',
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_tree_run_id    ON argument_tree(run_id);
CREATE INDEX IF NOT EXISTS idx_tree_parent    ON argument_tree(run_id, parent_id);
CREATE INDEX IF NOT EXISTS idx_tree_status    ON argument_tree(run_id, status);
CREATE INDEX IF NOT EXISTS idx_tree_type      ON argument_tree(run_id, type);

CREATE TABLE IF NOT EXISTS sources (
  source_id  TEXT PRIMARY KEY,
  node_id    TEXT NOT NULL,
  run_id     TEXT NOT NULL,
  url        TEXT,
  title      TEXT,
  authors    TEXT,
  year       INTEGER,
  citation   TEXT,
  metadata   TEXT DEFAULT '{}',
  created_at TEXT NOT NULL,
  FOREIGN KEY(node_id) REFERENCES argument_tree(node_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_sources_node ON sources(node_id);
CREATE INDEX IF NOT EXISTS idx_sources_run  ON sources(run_id);
"""

_DEFAULT_DB = Path(".data") / "pipeline.db"


class TreeBuilder:
    """Build and query an argument tree for a single run (session)."""

    def __init__(self, run_id: str, db_path: Optional[Path] = None) -> None:
        self.run_id = run_id
        self._db_path = db_path or _DEFAULT_DB
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._con = sqlite3.connect(str(self._db_path), check_same_thread=False)
        self._con.row_factory = sqlite3.Row
        self._con.execute("PRAGMA journal_mode=WAL")
        self._con.execute("PRAGMA busy_timeout=5000")
        self._con.execute("PRAGMA foreign_keys=ON")
        self._con.executescript(_SCHEMA)
        self._con.commit()

    def close(self) -> None:
        try:
            self._con.close()
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def _insert(
        self,
        node_type: str,
        label: str,
        content: Optional[str] = None,
        parent_id: Optional[str] = None,
        status: str = "pending",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        if node_type not in VALID_NODE_TYPES:
            raise ValueError(f"Unknown node type '{node_type}'. Valid: {sorted(VALID_NODE_TYPES)}")
        if status not in VALID_STATUSES:
            raise ValueError(f"Unknown status '{status}'. Valid: {sorted(VALID_STATUSES)}")
        node_id = str(uuid.uuid4())
        now = self._now()
        self._con.execute(
            """
            INSERT INTO argument_tree
              (node_id, run_id, parent_id, type, label, content, status, metadata, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                node_id,
                self.run_id,
                parent_id,
                node_type,
                label,
                content,
                status,
                json.dumps(metadata or {}),
                now,
                now,
            ),
        )
        self._con.commit()
        return node_id

    def _update(self, node_id: str, **kwargs: Any) -> None:
        if not kwargs:
            return
        now = self._now()
        kwargs["updated_at"] = now
        if "metadata" in kwargs and isinstance(kwargs["metadata"], dict):
            kwargs["metadata"] = json.dumps(kwargs["metadata"])
        set_clause = ", ".join(f"{k} = ?" for k in kwargs)
        vals = list(kwargs.values()) + [node_id, self.run_id]
        self._con.execute(
            f"UPDATE argument_tree SET {set_clause} WHERE node_id = ? AND run_id = ?",
            vals,
        )
        self._con.commit()

    # ------------------------------------------------------------------
    # Node creation — named helpers
    # ------------------------------------------------------------------

    def add_root(self, label: str, content: Optional[str] = None, metadata: Optional[Dict] = None) -> str:
        return self._insert("root", label, content=content, status="active", metadata=metadata)

    def add_claim(
        self,
        label: str,
        content: Optional[str] = None,
        parent_id: Optional[str] = None,
        status: str = "unsupported",
        metadata: Optional[Dict] = None,
    ) -> str:
        return self._insert("claim", label, content=content, parent_id=parent_id, status=status, metadata=metadata)

    def add_evidence(
        self,
        label: str,
        content: Optional[str] = None,
        parent_id: Optional[str] = None,
        metadata: Optional[Dict] = None,
    ) -> str:
        return self._insert(
            "evidence", label, content=content, parent_id=parent_id, status="supported", metadata=metadata
        )

    def add_question(
        self,
        label: str,
        content: Optional[str] = None,
        parent_id: Optional[str] = None,
        metadata: Optional[Dict] = None,
    ) -> str:
        return self._insert(
            "question", label, content=content, parent_id=parent_id, status="pending", metadata=metadata
        )

    def add_objection(
        self,
        label: str,
        content: Optional[str] = None,
        parent_id: Optional[str] = None,
        metadata: Optional[Dict] = None,
    ) -> str:
        return self._insert(
            "objection", label, content=content, parent_id=parent_id, status="unsupported", metadata=metadata
        )

    def add_response(
        self,
        label: str,
        content: Optional[str] = None,
        parent_id: Optional[str] = None,
        metadata: Optional[Dict] = None,
    ) -> str:
        return self._insert(
            "response", label, content=content, parent_id=parent_id, status="pending", metadata=metadata
        )

    def add_premise(
        self,
        label: str,
        content: Optional[str] = None,
        parent_id: Optional[str] = None,
        status: str = "pending",
        metadata: Optional[Dict] = None,
    ) -> str:
        return self._insert("premise", label, content=content, parent_id=parent_id, status=status, metadata=metadata)

    def add_inference(
        self,
        label: str,
        content: Optional[str] = None,
        parent_id: Optional[str] = None,
        status: str = "pending",
        metadata: Optional[Dict] = None,
    ) -> str:
        return self._insert("inference", label, content=content, parent_id=parent_id, status=status, metadata=metadata)

    def add_experiment(
        self,
        label: str,
        content: Optional[str] = None,
        parent_id: Optional[str] = None,
        status: str = "pending",
        metadata: Optional[Dict] = None,
    ) -> str:
        """Add an experiment node (maps to a research stage).

        Typical metadata: {stage_index: int, title: str}
        """
        return self._insert("experiment", label, content=content, parent_id=parent_id, status=status, metadata=metadata)

    def add_result(
        self,
        label: str,
        content: Optional[str] = None,
        parent_id: Optional[str] = None,
        status: str = "pending",
        metadata: Optional[Dict] = None,
    ) -> str:
        """Add a result node under an experiment.

        Typical metadata: {metric_name: str, value: Any, stage_index: int}
        """
        return self._insert("result", label, content=content, parent_id=parent_id, status=status, metadata=metadata)

    def add_artifact(
        self,
        label: str,
        content: Optional[str] = None,
        parent_id: Optional[str] = None,
        metadata: Optional[Dict] = None,
    ) -> str:
        """Add an artifact node (file path, URL, or other output).

        Typical metadata: {path: str, artifact_type: str}
        """
        return self._insert(
            "artifact", label, content=content, parent_id=parent_id, status="completed", metadata=metadata
        )

    def add_hypothesis(
        self,
        label: str,
        content: Optional[str] = None,
        parent_id: Optional[str] = None,
        status: str = "unsupported",
        metadata: Optional[Dict] = None,
    ) -> str:
        return self._insert("hypothesis", label, content=content, parent_id=parent_id, status=status, metadata=metadata)

    # ------------------------------------------------------------------
    # Node mutation
    # ------------------------------------------------------------------

    def update_node_status(self, node_id: str, status: str, metadata_patch: Optional[Dict] = None) -> None:
        if status not in VALID_STATUSES:
            raise ValueError(f"Unknown status '{status}'")
        updates: Dict[str, Any] = {"status": status}
        if metadata_patch:
            # Merge into existing metadata
            row = self._con.execute(
                "SELECT metadata FROM argument_tree WHERE node_id = ? AND run_id = ?",
                (node_id, self.run_id),
            ).fetchone()
            existing = json.loads(row["metadata"]) if row else {}
            existing.update(metadata_patch)
            updates["metadata"] = existing
        self._update(node_id, **updates)

    def add_source(
        self,
        node_id: str,
        url: Optional[str] = None,
        title: Optional[str] = None,
        authors: Optional[str] = None,
        year: Optional[int] = None,
        citation: Optional[str] = None,
        metadata: Optional[Dict] = None,
    ) -> str:
        source_id = str(uuid.uuid4())
        now = self._now()
        self._con.execute(
            """
            INSERT INTO sources
              (source_id, node_id, run_id, url, title, authors, year, citation, metadata, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (source_id, node_id, self.run_id, url, title, authors, year, citation, json.dumps(metadata or {}), now),
        )
        self._con.commit()
        return source_id

    # ------------------------------------------------------------------
    # Reads
    # ------------------------------------------------------------------

    def _row_to_dict(self, row: sqlite3.Row) -> Dict:
        d = dict(row)
        try:
            d["metadata"] = json.loads(d.get("metadata") or "{}")
        except (json.JSONDecodeError, TypeError):
            d["metadata"] = {}
        return d

    def get_tree(self) -> List[Dict]:
        rows = self._con.execute(
            "SELECT * FROM argument_tree WHERE run_id = ? ORDER BY created_at",
            (self.run_id,),
        ).fetchall()
        return [self._row_to_dict(r) for r in rows]

    def get_node(self, node_id: str) -> Optional[Dict]:
        row = self._con.execute(
            "SELECT * FROM argument_tree WHERE node_id = ? AND run_id = ?",
            (node_id, self.run_id),
        ).fetchone()
        return self._row_to_dict(row) if row else None

    def get_children(self, parent_id: str) -> List[Dict]:
        rows = self._con.execute(
            "SELECT * FROM argument_tree WHERE run_id = ? AND parent_id = ? ORDER BY created_at",
            (self.run_id, parent_id),
        ).fetchall()
        return [self._row_to_dict(r) for r in rows]

    def get_nodes_by_type(self, node_type: str) -> List[Dict]:
        rows = self._con.execute(
            "SELECT * FROM argument_tree WHERE run_id = ? AND type = ? ORDER BY created_at",
            (self.run_id, node_type),
        ).fetchall()
        return [self._row_to_dict(r) for r in rows]

    def get_root(self) -> Optional[Dict]:
        row = self._con.execute(
            "SELECT * FROM argument_tree WHERE run_id = ? AND type = 'root' ORDER BY created_at LIMIT 1",
            (self.run_id,),
        ).fetchone()
        return self._row_to_dict(row) if row else None

    def get_stats(self) -> Dict[str, Any]:
        rows = self._con.execute(
            "SELECT type, status, COUNT(*) as cnt FROM argument_tree WHERE run_id = ? GROUP BY type, status",
            (self.run_id,),
        ).fetchall()
        by_type: Dict[str, int] = {}
        by_status: Dict[str, int] = {}
        for r in rows:
            by_type[r["type"]] = by_type.get(r["type"], 0) + r["cnt"]
            by_status[r["status"]] = by_status.get(r["status"], 0) + r["cnt"]
        total = sum(by_type.values())
        return {
            "total_nodes": total,
            "by_type": by_type,
            "by_status": by_status,
        }

    def find_gaps(self) -> List[Dict]:
        """Return a list of gap descriptors: unanswered questions, unsupported claims, etc."""
        gaps = []
        # Unanswered questions (no children and still pending)
        q_rows = self._con.execute(
            """
            SELECT a.* FROM argument_tree a
            WHERE a.run_id = ? AND a.type = 'question' AND a.status = 'pending'
              AND NOT EXISTS (
                SELECT 1 FROM argument_tree c WHERE c.run_id = a.run_id AND c.parent_id = a.node_id
              )
            ORDER BY a.created_at
            """,
            (self.run_id,),
        ).fetchall()
        for r in q_rows:
            gaps.append({"kind": "unanswered_question", "node_id": r["node_id"], "label": r["label"]})

        # Unsupported claims
        c_rows = self._con.execute(
            """
            SELECT a.* FROM argument_tree a
            WHERE a.run_id = ? AND a.type = 'claim' AND a.status = 'unsupported'
            ORDER BY a.created_at
            """,
            (self.run_id,),
        ).fetchall()
        for r in c_rows:
            gaps.append({"kind": "unsupported_claim", "node_id": r["node_id"], "label": r["label"]})

        # Weak claims
        w_rows = self._con.execute(
            """
            SELECT a.* FROM argument_tree a
            WHERE a.run_id = ? AND a.type = 'claim' AND a.status = 'weak'
            ORDER BY a.created_at
            """,
            (self.run_id,),
        ).fetchall()
        for r in w_rows:
            gaps.append({"kind": "weak_claim", "node_id": r["node_id"], "label": r["label"]})

        # Experiments with no result children
        e_rows = self._con.execute(
            """
            SELECT a.* FROM argument_tree a
            WHERE a.run_id = ? AND a.type = 'experiment'
              AND NOT EXISTS (
                SELECT 1 FROM argument_tree c
                WHERE c.run_id = a.run_id AND c.parent_id = a.node_id AND c.type = 'result'
              )
            ORDER BY a.created_at
            """,
            (self.run_id,),
        ).fetchall()
        for r in e_rows:
            gaps.append({"kind": "experiment_without_result", "node_id": r["node_id"], "label": r["label"]})

        return gaps

    def to_context(self, max_nodes: int = 40) -> str:
        """Return a compact text representation suitable for LLM context."""
        nodes = self._con.execute(
            "SELECT * FROM argument_tree WHERE run_id = ? ORDER BY created_at LIMIT ?",
            (self.run_id, max_nodes),
        ).fetchall()
        if not nodes:
            return "(argument tree is empty)"
        lines = ["=== Argument Tree ==="]
        for n in nodes:
            indent = "  " if n["parent_id"] else ""
            lines.append(f"{indent}[{n['type'].upper()}:{n['status']}] {n['label']}")
            if n["content"]:
                snippet = n["content"][:120].replace("\n", " ")
                lines.append(f"{indent}  {snippet}")
        stats = self.get_stats()
        lines.append(f"\nTotal: {stats['total_nodes']} nodes — {stats['by_type']}")
        return "\n".join(lines)

    def to_reference_list(self) -> List[Dict]:
        """Return sources as a flat list for bibliography / citation building."""
        rows = self._con.execute(
            "SELECT * FROM sources WHERE run_id = ? ORDER BY created_at",
            (self.run_id,),
        ).fetchall()
        result = []
        for r in rows:
            d = dict(r)
            try:
                d["metadata"] = json.loads(d.get("metadata") or "{}")
            except (json.JSONDecodeError, TypeError):
                d["metadata"] = {}
            result.append(d)
        return result
