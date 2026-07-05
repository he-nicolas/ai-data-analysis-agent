import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from ai_data_analysis_agent.api.routes import file_removal, query, file_upload
from ai_data_analysis_agent.core.config import Settings
from ai_data_analysis_agent.core.logging import get_logger

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    problems = []

    db_path = Path(Settings.EXAMPLE_DB)
    if not db_path.exists():
        problems.append(f"SQL database not found at {db_path}")

    example_file = Path(Settings.EXAMPLE_FILE)
    if not example_file.exists():
        problems.append(f"Example Excel file not found at {example_file}")

    upload_dir = Path(Settings.UPLOAD_DIR)
    upload_dir.mkdir(parents=True, exist_ok=True)

    if problems:
        for p in problems:
            logger.error(f"Startup check failed: {p}")
    else:
        logger.info("Startup checks passed")

    logger.info("Application startup complete")
    yield
    logger.info("Application shutdown")


app = FastAPI(
    title="AI Agent System",
    version="0.1.0",
    lifespan=lifespan,
)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    request_id = str(uuid.uuid4())
    start_time = time.time()

    response = await call_next(request)

    latency = time.time() - start_time
    logger.info(
        f"{request.method} {request.url.path} -> {response.status_code} "
        f"({round(latency, 3)}s) [request_id={request_id}]"
    )
    response.headers["X-Request-ID"] = request_id
    return response


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.exception(f"Unhandled exception on {request.method} {request.url.path}")
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


@app.get("/")
def root():
    return {"status": "ok"}


app.include_router(query.router)
app.include_router(file_upload.router)
app.include_router(file_removal.router)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "ai_data_analysis_agent.main:app", host="0.0.0.0", port=8000, reload=True
    )
