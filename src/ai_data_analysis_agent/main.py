from fastapi import FastAPI, UploadFile, File, Form
from pydantic import BaseModel
from ai_data_analysis_agent.agents.agent import run_agent
import time
import logging
import os
from ai_data_analysis_agent.core.session_store import set_file_path

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

app.state.sessions = {}

UPLOAD_DIR = "data/files"
os.makedirs(UPLOAD_DIR, exist_ok=True)

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


@app.post("/upload")
async def upload(file: UploadFile = File(...), session_id: str = Form(...)):

    file_path = os.path.join(UPLOAD_DIR, f"{session_id}_{file.filename}")

    with open(file_path, "wb") as f:
        content = await file.read()
        f.write(content)

    set_file_path(session_id, file_path)

    return {
        "status": "ok",
        "file_path": file_path,
        "filename": file.filename
    }


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
            session_id=req.session_id,
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
    
@app.post("/session/end")
def end_session(session_id: str):
    from ai_data_analysis_agent.core.session_store import delete_session

    delete_session(session_id)

    return {"status": "cleaned"}