from fastapi import APIRouter
import logging
from ai_data_analysis_agent.core.session_store import delete_session

router = APIRouter()
logger = logging.getLogger("ai-agent")

from pydantic import BaseModel

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