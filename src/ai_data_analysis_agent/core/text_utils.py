def strip_code_fences(text: str) -> str:
    """
    Remove a surrounding ```/```lang markdown code fence from LLM output, if
    present. Pure string logic, no project dependencies - shared by both the
    SQL and Excel tool pipelines so there's a single implementation to test
    and maintain rather than two copies that can drift apart.
    """
    text = text.strip()
    if text.startswith("```"):
        lines = text.splitlines()[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines)
    return text.strip()
