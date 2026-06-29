from fastapi import APIRouter
from pydantic import BaseModel
import time
import logging
from ai_data_analysis_agent.agents.agent import run_agent

router = APIRouter()
logger = logging.getLogger("ai-agent")


class QueryRequest(BaseModel):
    input: str
    session_id: str | None = None


@router.post("/query")
def query(req: QueryRequest):
    start_time = time.time()

    logger.info(
        "Query request received",
        extra={
            "session_id": req.session_id,
            "input_preview": req.input[:100]  # avoid huge logs
        }
    )

    try:
        result = run_agent(
            user_input=req.input,
            session_id=req.session_id,
        )

        latency = time.time() - start_time

        logger.info(
            "Query completed",
            extra={
                "session_id": req.session_id,
                "latency": round(latency, 3),
                "response_length": len(result) if isinstance(result, str) else None
            }
        )

        return {
            "response": result,
            "latency": round(latency, 3)
        }

    except Exception as e:
        logger.exception(
            "Agent failed",
            extra={
                "session_id": req.session_id,
                "input_preview": req.input[:100]
            }
        )

        return {
            "response": "Sorry, something went wrong.",
            "error": str(e)
        }