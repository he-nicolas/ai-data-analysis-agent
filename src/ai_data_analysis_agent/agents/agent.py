from ai_data_analysis_agent.core.llm import get_llm
from ai_data_analysis_agent.core.prompts import SQL_SYSTEM_PROMPT, EXCEL_SYSTEM_PROMPT
from ai_data_analysis_agent.core.answerability_checker import is_answerable
from ai_data_analysis_agent.tools.sql_tools import sql_tools
from ai_data_analysis_agent.tools.excel_tools import excel_tools
from langchain.agents import create_agent
from langgraph.checkpoint.memory import InMemorySaver

llm = get_llm()

sql_agent = create_agent(
    model=llm,
    tools=sql_tools,
    system_prompt=SQL_SYSTEM_PROMPT,
    checkpointer=InMemorySaver(),
)

excel_agent = create_agent(
    model=llm,
    tools=excel_tools,
    system_prompt=EXCEL_SYSTEM_PROMPT,
    checkpointer=InMemorySaver(),
)


def run_agent(user_input: str, session_id: str, data_source: str):
    if data_source == "[Example] Sales Excel":
        agent = excel_agent
        source_type = "excel"
    elif data_source == "[Example] Music Database":
        agent = sql_agent
        source_type = "sql"
    elif data_source == "Upload Excel":
        agent = excel_agent
        source_type = "excel"
    else:
        return "Invalid data source."

    session_id = session_id or "default-session"

    config = {
        "configurable": {
            "thread_id": session_id,
            "session_id": session_id,
            "data_source": data_source,
        },
        "recursion_limit": 15,
    }

    if not is_answerable(user_input, source_type, config):
        return "I can only help with questions related to the connected data sources."

    result = agent.invoke(
        {
            "messages": [("user", user_input)],
        },
        config=config,
    )

    return result["messages"][-1].content
