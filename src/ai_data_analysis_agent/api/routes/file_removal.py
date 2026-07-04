from fastapi import APIRouter
from pydantic import BaseModel
from uvicorn import logging
from ai_data_analysis_agent.core.logging import get_logger
from ai_data_analysis_agent.core.session_store import delete_session

router = APIRouter()
logger = get_logger(__name__)


class SessionEndRequest(BaseModel):
    session_id: str


@router.post("/session/end")
def end_session(req: SessionEndRequest):
    logger.info(
        "Session cleanup requested",
        extra={"session_id": req.session_id}
    )

    try:
        delete_session(req.session_id)

        logger.info(
            "Session cleaned",
            extra={"session_id": req.session_id}
        )

        return {"status": "cleaned"}

    except Exception:
        logger.exception(
            "Session cleanup failed",
            extra={"session_id": req.session_id}
        )

        return {
            "status": "error",
            "message": "Failed to clean session"
        }