from pathlib import Path
from typing import Optional

from ai_data_analysis_agent.core.config import Settings
from ai_data_analysis_agent.core.logging import get_logger

logger = get_logger(__name__)

UPLOAD_DIR = Path(Settings.UPLOAD_DIR)


def _path_for(session_id: str) -> Path:
    return UPLOAD_DIR / f"{session_id}.xlsx"


def set_file_path(session_id: str, path: str) -> None:
    expected = _path_for(session_id)
    if Path(path) != expected:
        logger.warning(
            f"set_file_path called with unexpected path for session {session_id}: "
            f"got {path}, expected {expected}"
        )


def get_file_path(session_id: str) -> Optional[str]:
    path = _path_for(session_id)
    return str(path) if path.exists() else None


def delete_file(session_id: str) -> None:
    path = _path_for(session_id)

    if not path.exists():
        logger.info(f"No file to delete for session {session_id}")
        return

    try:
        path.unlink()
        logger.info(f"Deleted uploaded file for session {session_id}")
    except OSError:
        logger.exception(f"Failed to delete file for session {session_id}")
