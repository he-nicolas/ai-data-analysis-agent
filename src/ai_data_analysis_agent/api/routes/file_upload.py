import time
from pathlib import Path

from fastapi import APIRouter, UploadFile, File, Form, HTTPException

from ai_data_analysis_agent.core.config import Settings
from ai_data_analysis_agent.core.logging import get_logger
from ai_data_analysis_agent.core.file_store import set_file_path
from ai_data_analysis_agent.api.schemas import validate_session_id

router = APIRouter()
logger = get_logger(__name__)

UPLOAD_DIR = Path(Settings.UPLOAD_DIR)
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

MAX_UPLOAD_BYTES = 20 * 1024 * 1024  # 20 MB
_XLSX_MAGIC = b"PK\x03\x04"  # .xlsx is a zip archive


@router.post("/file/upload")
async def upload(file: UploadFile = File(...), session_id: str = Form(...)):
    start_time = time.time()

    try:
        session_id = validate_session_id(session_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    logger.info(
        "Upload request received",
        extra={"file_name": file.filename, "session_id": session_id},
    )

    if not file.filename or not file.filename.lower().endswith(".xlsx"):
        raise HTTPException(status_code=400, detail="Only .xlsx files are allowed")

    content = await file.read()

    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=400,
            detail=f"File too large (max {MAX_UPLOAD_BYTES // (1024 * 1024)} MB)",
        )

    if not content.startswith(_XLSX_MAGIC):
        raise HTTPException(
            status_code=400, detail="File does not look like a valid .xlsx file"
        )


    file_path = UPLOAD_DIR / f"{session_id}.xlsx"

    try:
        file_path.write_bytes(content)
        set_file_path(session_id, str(file_path))

        latency = time.time() - start_time
        logger.info(
            "Upload successful",
            extra={
                "file_path": str(file_path),
                "size_bytes": len(content),
                "latency": round(latency, 3),
                "session_id": session_id,
            },
        )

        return {"status": "ok", "file_path": str(file_path), "filename": file.filename}

    except HTTPException:
        raise
    except Exception:
        logger.exception(
            "Upload failed", extra={"file_name": file.filename, "session_id": session_id}
        )
        raise HTTPException(status_code=500, detail="File upload failed")