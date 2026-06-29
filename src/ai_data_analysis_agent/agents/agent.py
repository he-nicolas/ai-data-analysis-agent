from ai_data_analysis_agent.core.llm import get_llm
from ai_data_analysis_agent.core.prompt import SYSTEM_PROMPT
from ai_data_analysis_agent.core.sql_schema_guard import is_answerable
from ai_data_analysis_agent.tools.sql_tools import sql_tools
from langchain.agents import create_agent
from langgraph.checkpoint.memory import InMemorySaver
from langchain.agents.middleware import AgentState
import uuid

class CustomState(AgentState):
    session_id: str


llm = get_llm()
agent = create_agent(
    model=llm,
    tools=sql_tools,
    system_prompt=SYSTEM_PROMPT,
    checkpointer=InMemorySaver(),
    state_schema=CustomState,
)


def run_agent(user_input: str, session_id: str | None = None, thread_id: str | None = None):

    if not is_answerable(user_input):
        return "I can only help with questions related to the connected data sources."

    thread_id = thread_id or "default-thread"

    result = agent.invoke(
        {
            "messages": [("user", user_input)],
            "session_id": session_id or "default-session",
        },
        config={
            "configurable": {
                "thread_id": thread_id,
                "recursion_limit": 3
            }
        },
    )

    return result["messages"][-1].content