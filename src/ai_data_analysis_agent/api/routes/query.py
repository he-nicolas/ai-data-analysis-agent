import time

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from langsmith import traceable

from ai_data_analysis_agent.agents.agent import run_agent
from ai_data_analysis_agent.core.logging import get_logger
from ai_data_analysis_agent.api.schemas import validate_session_id

router = APIRouter()
logger = get_logger(__name__)


class QueryRequest(BaseModel):
    input: str
    session_id: str
    data_source: str


@router.post("/query")
@traceable(name="query_endpoint")
def query(req: QueryRequest):
    start_time = time.time()

    try:
        session_id = validate_session_id(req.session_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    if not req.input.strip():
        raise HTTPException(status_code=400, detail="input must not be empty")

    input_preview = req.input[:100]  # avoid huge logs

    logger.info(
        "Query request received",
        extra={"session_id": session_id, "input_preview": input_preview},
    )

    try:
        result = run_agent(
            user_input=req.input,
            session_id=session_id,
            data_source=req.data_source,
        )

        latency = time.time() - start_time

        logger.info(
            "Query completed",
            extra={
                "session_id": session_id,
                "latency": round(latency, 3),
                "response_length": len(result) if isinstance(result, str) else None,
            },
        )

        return {"response": result, "latency": round(latency, 3)}

    except Exception:
        logger.exception(
            "Agent failed",
            extra={"session_id": session_id, "input_preview": input_preview},
        )
        raise HTTPException(status_code=500, detail="Sorry, something went wrong.")
