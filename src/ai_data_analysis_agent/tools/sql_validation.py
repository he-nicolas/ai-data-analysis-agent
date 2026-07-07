"""
Pure SQL validation logic for the read-only query pipeline.

Deliberately has ZERO project-internal imports and no side effects at import
time (no DB connection, no config, no LLM). This is what makes it safe to
unit test directly - importing this module can never touch a real database
or fail because some unrelated setting is missing.

Requires: `pip install sqlparse`
"""

from __future__ import annotations

import re

import sqlparse

MAX_ROWS_DEFAULT = 100

# Keywords that should never appear in a read-only query, anywhere in the
# statement (including inside a CTE, subquery, or after a semicolon).
FORBIDDEN_KEYWORDS = {
    "insert", "update", "delete", "drop", "alter", "create", "replace",
    "attach", "detach", "pragma", "vacuum", "reindex", "grant", "revoke",
    "truncate", "begin", "commit", "rollback",
}

_TOKEN_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")


def validate_readonly_sql(query: str) -> str:
    """
    Raise ValueError unless `query` is exactly one read-only statement.
    Returns the query with any trailing semicolon stripped.
    """
    statements = [s for s in sqlparse.split(query) if s.strip()]
    if len(statements) == 0:
        raise ValueError("No SQL statement found.")
    if len(statements) > 1:
        raise ValueError("Only a single SQL statement is allowed per call.")

    stmt = statements[0].strip().rstrip(";").strip()

    tokens = {t.lower() for t in _TOKEN_RE.findall(stmt)}
    forbidden_hits = tokens & FORBIDDEN_KEYWORDS
    if forbidden_hits:
        raise ValueError(f"Disallowed keyword(s) in query: {', '.join(sorted(forbidden_hits))}")

    first_word = stmt.split(None, 1)[0].lower() if stmt else ""
    if first_word not in {"select", "with"}:
        raise ValueError("Only SELECT statements (optionally starting with WITH) are allowed.")

    return stmt


def ensure_limit(query: str, limit: int = MAX_ROWS_DEFAULT) -> str:
    """Append a LIMIT clause via the parser, not a substring check, unless one already exists."""
    parsed = sqlparse.parse(query)[0]
    has_limit = any(
        tok.ttype is sqlparse.tokens.Keyword and tok.value.upper() == "LIMIT"
        for tok in parsed.tokens
    )
    if has_limit:
        return query
    return f"{query} LIMIT {limit}"