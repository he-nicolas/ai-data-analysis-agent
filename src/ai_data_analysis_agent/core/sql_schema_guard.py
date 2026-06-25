from ai_data_analysis_agent.tools.sql_tools import sql_db_list_tables, sql_db_schema
from ai_data_analysis_agent.core.llm import call_llm


def get_schema_context() -> str:
    tables = sql_db_list_tables.invoke("")

    schema_parts = []
    for table in tables.split(", "):
        schema_parts.append(sql_db_schema.invoke({"table_name": table}))

    return "\n\n".join(schema_parts)


def is_answerable(user_input: str) -> bool:
    schema = get_schema_context()

    prompt = f"""
You are a strict database validator.

You are given:
- Database schema
- A user question

Schema:
{schema}

Question:
{user_input}

Decide if the question can be answered using ONLY this schema.

Rules:
- You MUST assume no external knowledge exists
- If schema does not clearly contain required data → answer NO
- If unsure → answer NO

Return only:
YES or NO
"""
    print(call_llm(prompt))
    result = call_llm(prompt).strip().upper()
    return result == "YES"