from fastapi import FastAPI
from pydantic import BaseModel
from app.agents.agent import run_agent
import time
import logging

# ------------------------
# Logging setup
# ------------------------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ai-agent")

# ------------------------
# FastAPI app
# ------------------------
app = FastAPI(
    title="AI Agent System",
    description="Production-style agentic AI backend",
    version="0.1.0"
)

# ------------------------
# Request schema
# ------------------------
class QueryRequest(BaseModel):
    input: str
    session_id: str | None = None

# ------------------------
# Health check
# ------------------------
@app.get("/")
def root():
    return {"status": "ok"}

# ------------------------
# Main agent endpoint
# ------------------------
@app.post("/query")
def query(req: QueryRequest):
    start_time = time.time()

    logger.info(
        "Incoming request",
        extra={"input": req.input, "session_id": req.session_id}
    )

    try:
        result = run_agent(
            user_input=req.input,
            session_id=req.session_id
        )

        latency = time.time() - start_time

        logger.info(
            "Request completed",
            extra={"latency": latency}
        )

        return {
            "response": result,
            "latency": round(latency, 3)
        }

    except Exception as e:
        logger.exception("Agent failed")

        return {
            "response": "Sorry, something went wrong while processing your request.",
            "error": str(e)
        }