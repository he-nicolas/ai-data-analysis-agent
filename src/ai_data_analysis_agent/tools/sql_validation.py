"""
Pure SQL validation logic for the read-only query pipeline.

Deliberately has ZERO project-internal imports and no side effects at import
time (no DB connection, no config, no LLM). This is what makes it safe to
unit test directly - importing this module can never touch a real database
or fail because some unrelated setting is missing.

Requires: `pip install sqlparse`
"""

from __future__ import annotations

import sqlparse
from sqlparse.tokens import Keyword, DML, Literal, Comment

MAX_ROWS_DEFAULT = 100

# Keywords that should never appear in a read-only query, anywhere in the
# statement (including inside a CTE, subquery, or after a semicolon).
FORBIDDEN_KEYWORDS = {
    "insert",
    "update",
    "delete",
    "drop",
    "alter",
    "create",
    "replace",
    "attach",
    "detach",
    "pragma",
    "vacuum",
    "reindex",
    "grant",
    "revoke",
    "truncate",
    "begin",
    "commit",
    "rollback",
}


def _contains_forbidden_keyword(statement) -> set[str]:
    """
    Return a set of forbidden keywords found in the SQL statement,
    ignoring string literals and comments.
    """
    hits = set()

    for token in statement.flatten():
        # Skip string literals
        if token.ttype in Literal.String:
            continue

        # Skip comments
        if token.ttype in Comment:
            continue

        val = token.value.lower()

        if val in FORBIDDEN_KEYWORDS:
            hits.add(val)

    return hits


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

    parsed = sqlparse.parse(stmt)[0]

    first_token = next((t for t in parsed.tokens if not t.is_whitespace), None)

    if first_token and first_token.value.upper() == "EXPLAIN":
        raise ValueError("Only SELECT statements are allowed.")

    forbidden_hits = _contains_forbidden_keyword(parsed)
    if forbidden_hits:
        raise ValueError(
            f"Disallowed keyword(s) in query: {', '.join(sorted(forbidden_hits))}"
        )

    if not first_token or first_token.value.lower() not in {"select", "with"}:
        raise ValueError(
            "Only SELECT statements (optionally starting with WITH) are allowed."
        )

    return stmt


def ensure_limit(query: str, limit: int = MAX_ROWS_DEFAULT) -> str:
    """Append a LIMIT clause via the parser, not a substring check, unless one already exists."""
    parsed = sqlparse.parse(query)[0]
    has_limit = any(
        tok.ttype in Keyword and tok.value.upper() == "LIMIT"
        for tok in parsed.flatten()
    )

    if has_limit:
        return query

    return f"{query} LIMIT {limit}"
