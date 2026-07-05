import re
import threading
from typing import Any, Optional

import sqlparse
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Engine

from ai_data_analysis_agent.core.config import Settings
from ai_data_analysis_agent.core.logging import get_logger
from ai_data_analysis_agent.core.llm import call_llm
from langchain_core.tools import tool

logger = get_logger(__name__)

QUERY_TIMEOUT_SECONDS = 10
MAX_ROWS = 100
MAX_RESULT_CHARS = 4000
MAX_CELL_CHARS = 300

# Keywords that should never appear in a read-only query, anywhere in the
# statement (including inside a CTE, subquery, or after a semicolon).
_FORBIDDEN_KEYWORDS = {
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

_TOKEN_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")


def _build_readonly_engine() -> Engine:
    """
    Open the SQLite file in true read-only mode via its URI filename feature.
    """
    uri = f"sqlite:///file:{Settings.EXAMPLE_DB}?mode=ro&uri=true"
    return create_engine(uri, connect_args={"check_same_thread": False})


engine = _build_readonly_engine()


def _strip_code_fences(text_: str) -> str:
    text_ = text_.strip()
    if text_.startswith("```"):
        lines = text_.splitlines()[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        text_ = "\n".join(lines)
    return text_.strip()


def _validate_readonly_sql(query: str) -> str:
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
    forbidden_hits = tokens & _FORBIDDEN_KEYWORDS
    if forbidden_hits:
        raise ValueError(
            f"Disallowed keyword(s) in query: {', '.join(sorted(forbidden_hits))}"
        )

    first_word = stmt.split(None, 1)[0].lower() if stmt else ""
    if first_word not in {"select", "with"}:
        raise ValueError(
            "Only SELECT statements (optionally starting with WITH) are allowed."
        )

    return stmt


def _ensure_limit(query: str, limit: int = MAX_ROWS) -> str:
    """Append a LIMIT clause via the parser, not a substring check, unless one already exists."""
    parsed = sqlparse.parse(query)[0]
    has_limit = any(
        tok.ttype is sqlparse.tokens.Keyword and tok.value.upper() == "LIMIT"
        for tok in parsed.tokens
    )
    if has_limit:
        return query
    return f"{query} LIMIT {limit}"


def _execute_with_timeout(
    query: str, timeout: int = QUERY_TIMEOUT_SECONDS
) -> list[dict[str, Any]]:
    with engine.connect() as conn:
        raw_conn = conn.connection  # underlying DBAPI (sqlite3) connection
        timer = threading.Timer(timeout, raw_conn.interrupt)
        timer.start()
        try:
            result = conn.execute(text(query))
            rows = [dict(row) for row in result.mappings().all()]
        finally:
            timer.cancel()
    return rows


def _format_rows(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "Query returned no rows."

    truncated_row_count = len(rows) > MAX_ROWS
    rows = rows[:MAX_ROWS]

    def fmt_cell(v: Any) -> str:
        s = str(v)
        return s if len(s) <= MAX_CELL_CHARS else s[:MAX_CELL_CHARS] + "...(truncated)"

    columns = list(rows[0].keys())
    lines = [" | ".join(columns)]
    for row in rows:
        lines.append(" | ".join(fmt_cell(row[c]) for c in columns))

    text_out = "\n".join(lines)
    if truncated_row_count:
        text_out += f"\n... (showing first {MAX_ROWS} rows)"
    if len(text_out) > MAX_RESULT_CHARS:
        text_out = text_out[:MAX_RESULT_CHARS] + "... (truncated)"
    return text_out


@tool
def sql_db_list_tables() -> str:
    """
    List all user tables in the SQLite database.

    Returns:
        str: A comma-separated list of table names in the database.
    """
    try:
        logger.info("Fetching list of database tables")
        inspector = inspect(engine)
        tables = [t for t in inspector.get_table_names() if not t.startswith("sqlite_")]
        logger.info(f"Filtered user tables: {tables}")
        return ", ".join(tables) if tables else "No user tables found."
    except Exception as e:
        logger.exception("Failed to list database tables")
        return f"Error: {e}"


@tool
def sql_db_schema(table_name: str) -> str:
    """
    Get schema information for a single database table.

    Args:
        table_name: Name of the table to inspect. Use `sql_db_list_tables` first.

    Returns:
        str: Column names, types, nullability, and primary-key info.
    """
    try:
        logger.info(f"Schema inspection started for table: {table_name}")
        inspector = inspect(engine)

        valid_tables = inspector.get_table_names()
        if table_name not in valid_tables:
            logger.warning(f"Table not found: {table_name}")
            return f"Error: table '{table_name}' not found."

        columns = inspector.get_columns(table_name)
        if not columns:
            return f"No columns found for table '{table_name}'."

        lines = [f"Schema for table: {table_name}\n"]
        for col in columns:
            lines.append(
                f"- {col.get('name')} | {col.get('type')} | "
                f"nullable={col.get('nullable')} | pk={col.get('primary_key', False)}"
            )
        return "\n".join(lines)
    except Exception as e:
        logger.exception(f"Schema inspection failed for table: {table_name}")
        return f"Error: {e}"


def sql_db_query(query: str) -> str:
    """
    Validate and execute a single read-only SQL query. Not exposed directly
    to the LLM as a tool - always called through `run_sql_pipeline`, which
    guarantees validation runs on whatever the final query ends up being.
    """
    try:
        clean_query = _validate_readonly_sql(query)
        bounded_query = _ensure_limit(clean_query)

        logger.info(f"Executing SQL query: {bounded_query}")
        rows = _execute_with_timeout(bounded_query)
        logger.info(f"Query executed successfully. Rows returned: {len(rows)}")

        return _format_rows(rows)
    except TimeoutError:
        logger.warning("Query interrupted after timeout")
        return f"Error: query exceeded {QUERY_TIMEOUT_SECONDS}s and was interrupted."
    except ValueError as e:
        logger.warning(f"Query rejected by validator: {e}")
        return f"Error: {e}"
    except Exception as e:
        logger.exception("SQL query execution failed")
        return f"Error: {e}"


def sql_db_query_checker(query: str) -> Optional[str]:
    """
    Ask an LLM to review/fix common SQL mistakes. Returns the corrected query,
    or None if the LLM call failed or its output doesn't pass validation
    (callers should fall back to the original query in that case - this
    function is an assist, not a source of truth for safety).
    """
    prompt = f"""
        You are a SQL expert specializing in SQLite.

        Review the following SQL query and fix any mistakes.

        Common issues to check:
        - Using NOT IN with NULL values
        - Using UNION instead of UNION ALL incorrectly
        - Incorrect use of BETWEEN (inclusive vs exclusive ranges)
        - Data type mismatches in WHERE clauses
        - Missing or incorrect quoting of identifiers
        - Incorrect number of function arguments
        - Missing type casts
        - Incorrect join conditions or columns

        If the query is correct, return it unchanged.
        Return ONLY the final SQL query, no explanation, no markdown fences.

        SQL QUERY:
        {query}
    """.strip()

    try:
        raw = call_llm(prompt)
    except Exception as e:
        logger.warning(f"SQL checker LLM call failed: {e}")
        return None

    candidate = _strip_code_fences(raw)

    try:
        _validate_readonly_sql(candidate)
    except ValueError as e:
        logger.warning(f"Checker output failed validation, ignoring it: {e}")
        return None

    return candidate


@tool
def run_sql_pipeline(query: str) -> str:
    """
    Execute a SQL query through a validated, read-only pipeline. This is the
    ONLY tool that should be used for running SQL - use `sql_db_list_tables`
    and `sql_db_schema` first to understand the database.

    Args:
        query: A SQL query (SELECT, optionally with a WITH clause).

    Returns:
        str: Query results as a table, or an error message.
    """
    logger.info(f"SQL pipeline started. Original query: {query}")

    corrected = sql_db_query_checker(query)
    final_query = corrected if corrected is not None else query

    result = sql_db_query(final_query)

    logger.info("SQL pipeline completed")
    return result


sql_tools = [sql_db_list_tables, sql_db_schema, run_sql_pipeline]
