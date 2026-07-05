import re

_SESSION_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,128}$")


def validate_session_id(session_id: str) -> str:
    """
    Ensure session_id is safe to use as a file-path component and as a
    LangGraph checkpoint thread_id. Raises ValueError if invalid.
    """
    if not session_id or not _SESSION_ID_RE.match(session_id):
        raise ValueError(
            "session_id must be 1-128 characters: letters, digits, '-' or '_' only."
        )
    return session_id