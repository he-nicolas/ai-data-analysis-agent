from typing import Literal, Optional

from langchain_core.runnables import RunnableConfig

from ai_data_analysis_agent.core.prompts import get_answerability_prompt
from ai_data_analysis_agent.tools.sql_tools import sql_db_list_tables, sql_db_schema
from ai_data_analysis_agent.tools.excel_tools import excel_list_sheets, excel_schema
from ai_data_analysis_agent.core.llm import call_llm
from ai_data_analysis_agent.core.logging import get_logger
from ai_data_analysis_agent.core.config import Settings

logger = get_logger(__name__)

SourceType = Literal["sql", "excel"]


def _get_sql_schema_context() -> str:
    tables_str = sql_db_list_tables.invoke("")

    if not tables_str or tables_str.startswith("Error") or tables_str == "No user tables found.":
        logger.warning(f"No SQL tables available for schema guard: {tables_str!r}")
        return ""

    schema_parts = []
    for table in tables_str.split(", "):
        table = table.strip()
        if not table:
            continue
        schema = sql_db_schema.invoke({"table_name": table})
        if schema.startswith("Error"):
            logger.warning(f"Could not fetch schema for table '{table}': {schema}")
            continue
        schema_parts.append(schema)

    return "\n\n".join(schema_parts)


def _get_excel_schema_context(config: RunnableConfig) -> str:
    sheets_str = excel_list_sheets.invoke({}, config=config)

    if not sheets_str or sheets_str.startswith("Error") or "no sheets" in sheets_str.lower():
        logger.warning(f"No Excel sheets available for schema guard: {sheets_str!r}")
        return ""

    sheet_names = [s.strip() for s in sheets_str.removeprefix("Sheets: ").split(",") if s.strip()]

    schema_parts = []
    for sheet_name in sheet_names:
        schema = excel_schema.invoke({"sheet_name": sheet_name}, config=config)
        if schema.startswith("Error"):
            logger.warning(f"Could not fetch schema for sheet '{sheet_name}': {schema}")
            continue
        schema_parts.append(schema)

    return "\n\n".join(schema_parts)


def get_schema_context(source_type: SourceType, config: Optional[RunnableConfig] = None) -> str:
    """
    Build the schema context for the currently connected data source.

    Args:
        source_type: Which connected source to inspect - "sql" or "excel".
        config: Required when source_type is "excel" (used to resolve the
            session's uploaded/example file). Ignored for "sql".
    """
    if source_type == "sql":
        return _get_sql_schema_context()

    if source_type == "excel":
        if config is None:
            raise ValueError("config is required to resolve the Excel schema context.")
        return _get_excel_schema_context(config)

    raise ValueError(f"Unknown source_type: {source_type!r}")


def is_answerable(
    user_input: str,
    source_type: SourceType,
    config: Optional[RunnableConfig] = None,
) -> bool:
    """
    Check whether `user_input` can plausibly be answered using the connected
    data source's schema, before letting the agent attempt a full run.
    """
    schema = get_schema_context(source_type, config)

    if not schema:
        logger.warning(
            f"No schema available for source_type={source_type}; treating question as unanswerable"
        )
        return False

    prompt = get_answerability_prompt(schema, user_input)

    response = call_llm(prompt, model=Settings.GUARD_LLM_MODEL).strip().upper()

    logger.info(f"Answerability check result: {response} (source_type={source_type})")

    return response.startswith("YES")
