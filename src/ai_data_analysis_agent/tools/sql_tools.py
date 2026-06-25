from langchain_core.tools import tool
from contextlib import contextmanager
from sqlalchemy import create_engine, inspect, text
from ai_data_analysis_agent.core.config import Settings
from ai_data_analysis_agent.core.logging import get_logger
from ai_data_analysis_agent.core.llm import call_llm


logger = get_logger(__name__)

engine = create_engine(f"sqlite:///{Settings.DB_PATH}")

@contextmanager
def get_connection():
    """
    Provides a database connection and ensures it is always closed.

    Yields:
        Connection: SQLAlchemy connection object
    """
    conn = engine.connect()
    try:
        yield conn
    finally:
        conn.close()


@tool
def sql_db_list_tables() -> str:
    """
    List all user tables in the SQLite database.

    This tool retrieves all table names from the connected database, excluding internal SQLite tables.

    Args:
        None

    Returns:
        str: A comma-separated list of table names in the database.

    Notes:
        Input is an empty string, output is a comma-separated list of tables in the database.
    """

    try:
        logger.info("Fetching list of database tables")

        inspector = inspect(engine)

        tables = inspector.get_table_names()
        logger.debug(f"Raw tables from inspector: {tables}")

        tables = [t for t in tables if not t.startswith("sqlite_")]

        logger.info(f"Filtered user tables: {tables}")

        result = ", ".join(tables)

        logger.info(f"Table listing completed ({len(tables)} tables found)")

        return result

    except Exception as e:
        logger.exception("Failed to list database tables")
        return f"Error: {str(e)}"


@tool
def sql_db_schema(table_name: str) -> str:
    """
    Get schema information for a single database table.

    This tool returns column-level metadata for a table to help understand its structure
    before writing SQL queries.

    Args:
        table_name (str):
            Name of the table to inspect.
            Example: "users"

    Returns:
        str:
            A human-readable schema description including:
            - column names
            - data types
            - whether NULL is allowed
            - primary key info

    Notes:
        Input must be a single valid table name.
        Use `sql_db_list_tables` to discover available tables first.
    """

    try:
        logger.info(f"Schema inspection started for table: {table_name}")

        inspector = inspect(engine)

        # validate table exists
        valid_tables = inspector.get_table_names()
        logger.debug(f"Available tables: {valid_tables}")

        if table_name not in valid_tables:
            logger.warning(f"Table not found: {table_name}")
            return f"Error: table '{table_name}' not found."

        columns = inspector.get_columns(table_name)

        if not columns:
            logger.warning(f"No columns found for table: {table_name}")
            return f"No columns found for table '{table_name}'."

        lines = [f"Schema for table: {table_name}\n"]

        for col in columns:
            col_name = col.get("name")
            col_type = col.get("type")
            nullable = col.get("nullable")
            primary_key = col.get("primary_key", False)

            lines.append(
                f"- {col_name} | {col_type} | "
                f"nullable={nullable} | pk={primary_key}"
            )

        result = "\n".join(lines)

        logger.info(
            f"Schema inspection completed for {table_name} "
            f"({len(columns)} columns)"
        )

        return result

    except Exception as e:
        logger.exception(f"Schema inspection failed for table: {table_name}")
        return f"Error: {str(e)}"


def sql_db_query(query: str) -> str:
    """
    Execute a SQL query against the database and return results.

    This tool is used to run READ-ONLY SQL queries and retrieve data from the database.

    Args:
        query (str):
            A valid SQL query string.
            Must be a SELECT query.

    Returns:
        str:
            Query results as a string or an error message if execution fails.

    Notes:
        - Only read-only queries are allowed (SELECT).
        - If the query fails, the error is returned.
        - Use `sql_db_schema` if column errors occur.
    """

    try:
        # Limit huge outputs
        if "limit" not in query.lower():
            query = query.rstrip(";") + " LIMIT 100"
        logger.info(f"Executing SQL query: {query}")

        # Safety guard: enforce read-only queries
        if not query.strip().lower().startswith("select"):
            logger.warning("Blocked non-SELECT query attempt")
            return "Error: Only SELECT queries are allowed."

        with engine.connect() as conn:
            result = conn.execute(text(query))
            rows = result.fetchall()

        logger.info(f"Query executed successfully. Rows returned: {len(rows)}")

        return str(rows)

    except Exception as e:
        logger.exception("SQL query execution failed")
        return f"Error: {str(e)}"


def sql_db_query_checker(query: str) -> str:
    """
    Validate and correct a SQL query before execution.

    This tool uses an LLM to detect common SQL mistakes and rewrite the query if needed.

    Args:
        query (str):
            SQL query to validate.

    Returns:
        str:
            Corrected SQL query (or original if no issues are found).

    Notes:
        - Always run this before executing `sql_db_query`.
        - Returns ONLY the final SQL query string.
    """

    try:
        logger.info("SQL query validation started")

        trigger_prompt = f"""
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

            Return ONLY the final SQL query.

            SQL QUERY:
            {query}
        """.strip()

        logger.debug(f"Query sent to LLM for checking: {query}")

        response = call_llm(trigger_prompt)
        fixed_query = response.strip()

        logger.info("SQL query validation completed")
        logger.debug(f"Corrected query: {fixed_query}")

        return fixed_query

    except Exception as e:
        logger.exception("SQL query checker failed")
        return f"Error: {str(e)}"
    

@tool
def run_sql_pipeline(query: str) -> str:
    """
    Safely execute a SQL query using a controlled validation and execution pipeline.

    This is the ONLY tool that should be used for executing SQL queries.

    Pipeline steps:
        1. The query is first validated and corrected by an LLM-based SQL checker.
        2. The corrected query is then executed against the SQLite database.
        3. The final results are returned.

    Args:
        query (str):
            A natural-language-derived SQL query or raw SQL query.

    Returns:
        str:
            The result of the executed SQL query or an error message.

    Notes:
        - This tool enforces query safety through automatic validation.
        - Direct execution of SQL is not allowed outside this pipeline.
        - Always use this tool for any database-related question.
    """

    logger.info("SQL pipeline started")
    logger.info(f"Original query: {query}")

    # 1. validate
    checked_query = sql_db_query_checker(query)
    logger.info(f"Checked query: {checked_query}")

    # 2. execute
    result = sql_db_query(checked_query)

    logger.info("SQL pipeline completed")

    return result


sql_tools = [sql_db_list_tables, sql_db_schema, run_sql_pipeline]