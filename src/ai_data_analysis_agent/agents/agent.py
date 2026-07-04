from ai_data_analysis_agent.core.llm import get_llm
from ai_data_analysis_agent.core.prompt import SYSTEM_PROMPT
from ai_data_analysis_agent.core.sql_schema_guard import is_answerable
from ai_data_analysis_agent.tools.sql_tools import sql_tools
from langchain.agents import create_agent
from langgraph.checkpoint.memory import InMemorySaver
from langchain.agents.middleware import AgentState

class CustomState(AgentState):
    session_id: str

llm = get_llm()

sql_agent = create_agent(
    model=llm,
    tools=sql_tools,
    system_prompt=SYSTEM_PROMPT,
    checkpointer=InMemorySaver(),
    state_schema=CustomState,
)

excel_agent = create_agent(
    model=llm,
    tools=sql_tools,
    system_prompt=SYSTEM_PROMPT,
    checkpointer=InMemorySaver(),
    state_schema=CustomState,
)


def run_agent(user_input: str, session_id: str, data_source: str):
    if data_source == "[Example] Sales Excel":
        pass
    elif data_source == "[Example] Music Database":
        pass
    elif data_source == "Upload Excel":
        pass
    else:
        return "Invalid data source."



    if not is_answerable(user_input):
        return "I can only help with questions related to the connected data sources."


    result = agent.invoke(
        {
            "messages": [("user", user_input)],
            "session_id": session_id or "default-session",
        },
        config={
            "configurable": {
                "recursion_limit": 3
            }
        },
    )

    return result["messages"][-1].content