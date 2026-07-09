from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ai_data_analysis_agent.core.logging import get_logger
from ai_data_analysis_agent.core.file_store import delete_file
from ai_data_analysis_agent.api.schemas import validate_session_id

router = APIRouter()
logger = get_logger(__name__)


class SessionFileRequest(BaseModel):
    session_id: str


@router.post("/file/remove")
def remove_file(req: SessionFileRequest):
    try:
        session_id = validate_session_id(req.session_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    logger.info("File removal requested", extra={"session_id": session_id})

    try:
        delete_file(session_id)
        logger.info("File removed", extra={"session_id": session_id})
        return {"status": "file_removed"}
    except Exception:
        logger.exception("File removal failed", extra={"session_id": session_id})
        raise HTTPException(status_code=500, detail="Failed to remove file")
