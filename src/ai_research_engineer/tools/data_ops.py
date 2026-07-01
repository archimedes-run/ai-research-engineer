"""
Database Operations using DuckDB.
Allows agents to query Parquet files using SQL without loading data into memory.
"""

import logging
import re
from pathlib import Path

import duckdb


logger = logging.getLogger(__name__)

# Statements whose leading keyword is safe to execute read-only.
_ALLOWED_LEADING_KEYWORDS = {"select", "with", "describe", "show", "pragma"}

# Patterns that indicate a write or exfiltration vector regardless of leading keyword.
_FORBIDDEN_PATTERNS = [
    re.compile(r"\bcopy\b", re.IGNORECASE),
    re.compile(r"\battach\b", re.IGNORECASE),
    re.compile(r"\binstall\b", re.IGNORECASE),
    re.compile(r"\bload\b", re.IGNORECASE),
    re.compile(r"\bexport\b", re.IGNORECASE),
    re.compile(r"\bset\b", re.IGNORECASE),  # blocks SET enable_external_access etc
    re.compile(r"\bcreate\b", re.IGNORECASE),
    re.compile(r"\bdrop\b", re.IGNORECASE),
    re.compile(r"\bdelete\b", re.IGNORECASE),
    re.compile(r"\binsert\b", re.IGNORECASE),
    re.compile(r"\bupdate\b", re.IGNORECASE),
    re.compile(r"\balter\b", re.IGNORECASE),
]


def _validate_query(query: str) -> str | None:
    """
    Return an error message if the query is not safe; None if it is.

    Strategy: check the first non-comment keyword against an allowlist, then
    scan for forbidden statement keywords (write/exfiltration vectors).
    Returns an error string on rejection, None on acceptance.
    """
    stripped = query.strip()

    # Reject absolute paths that could be used to read arbitrary files.
    if re.search(r"'[/\\]|\"[/\\]", stripped):
        return "Absolute file paths are not permitted in queries."

    # Reject path traversal attempts.
    if re.search(r"\.\.", stripped):
        return "Path traversal ('..') is not permitted in queries."

    # Extract the first meaningful token (skip leading comments).
    without_comments = re.sub(r"--[^\n]*", "", stripped)
    without_comments = re.sub(r"/\*.*?\*/", "", without_comments, flags=re.DOTALL)
    first_token = re.match(r"\s*(\w+)", without_comments)

    if not first_token or first_token.group(1).lower() not in _ALLOWED_LEADING_KEYWORDS:
        keyword = first_token.group(1) if first_token else "(empty)"
        return f"Only SELECT / WITH / DESCRIBE / SHOW statements are permitted. Got: '{keyword}'"

    # Secondary scan: reject forbidden statement keywords anywhere in the query.
    for pattern in _FORBIDDEN_PATTERNS:
        if pattern.search(without_comments):
            return f"Forbidden keyword detected: '{pattern.pattern[2:-2]}'."

    return None


def query_duckdb(query: str, working_dir: str) -> str:
    """
    Execute a read-only SQL query against local Parquet/CSV files.

    Parameters
    ----------
    query : str
        SQL query to execute. Only SELECT/WITH/DESCRIBE/SHOW are permitted.
    working_dir : str
        Sandbox directory; relative file references are resolved here.

    Returns
    -------
    str
        Query results formatted as Markdown, or an error message.
    """
    try:
        error = _validate_query(query)
        if error:
            return f"Error: {error} Only SELECT statements are allowed."

        # Resolve working_dir to an absolute path.
        wd = Path(working_dir).resolve()

        con = duckdb.connect(database=":memory:")
        try:
            # Point DuckDB's file search path at the sandbox; avoids os.chdir.
            con.execute(f"SET file_search_path='{wd}';")
            # Disable external network and filesystem access.
            con.execute("SET enable_external_access=false;")

            if "LIMIT" not in query.upper():
                query += " LIMIT 1000"

            df = con.execute(query).fetchdf()

            row_count = len(df)
            if row_count >= 1000:
                sample_md = df.head(5).to_markdown(index=False)
                return (
                    "⚠️ WARNING: Result truncated at 1000 rows. "
                    "Use aggregations (GROUP BY) for analysis.\n"
                    f"Total rows returned: {row_count}\n\n"
                    f"Data Sample (First 5 rows):\n{sample_md}"
                )

            return df.to_markdown(index=False)

        finally:
            con.close()

    except Exception as e:
        logger.error(f"DuckDB Query Failed: {e}")
        return f"Error executing query: {str(e)}"


def get_schema(filepath: str, working_dir: str) -> str:
    """
    Get the schema (columns and types) of a Parquet or CSV file.
    """
    return query_duckdb(f"DESCRIBE SELECT * FROM '{filepath}'", working_dir)
