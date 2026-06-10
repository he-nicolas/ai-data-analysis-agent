from app.core.llm import call_llm

def run_agent(user_input: str, session_id: str | None = None):

    prompt = f"""
    You are an AI agent.

    User input:
    {user_input}

    Provide a helpful response.
    """

    response = call_llm(prompt)

    return response