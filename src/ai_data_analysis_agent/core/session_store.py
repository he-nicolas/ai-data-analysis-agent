import os

_FILE_STORE = {}

def set_file_path(session_id: str, path: str):
    _FILE_STORE[session_id] = path


def get_file_path(session_id: str):
    return _FILE_STORE.get(session_id)


def delete_session(session_id: str):
    file_path = _FILE_STORE.pop(session_id, None)

    if file_path and os.path.exists(file_path):
        try:
            os.remove(file_path)
        except Exception:
            pass