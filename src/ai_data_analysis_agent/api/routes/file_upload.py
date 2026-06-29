from fastapi import APIRouter, UploadFile, File, Form
import os
import logging
import time
from ai_data_analysis_agent.core.session_store import set_file_path

router = APIRouter()
logger = logging.getLogger("ai-agent")

UPLOAD_DIR = "data/uploaded_file"
os.makedirs(UPLOAD_DIR, exist_ok=True)


@router.post("/upload")
async def upload(file: UploadFile = File(...), session_id: str = Form(...)):
    start_time = time.time()

    logger.info(
        "Upload request received",
        extra={
            "filename": file.filename,
            "session_id": session_id
        }
    )

    try:
        file_path = os.path.join(UPLOAD_DIR, f"{session_id}_{file.filename}")

        content = await file.read()

        with open(file_path, "wb") as f:
            f.write(content)

        set_file_path(session_id, file_path)

        latency = time.time() - start_time

        logger.info(
            "Upload successful",
            extra={
                "file_path": file_path,
                "size_bytes": len(content),
                "latency": round(latency, 3),
                "session_id": session_id
            }
        )

        return {
            "status": "ok",
            "file_path": file_path,
            "filename": file.filename
        }

    except Exception as e:
        logger.exception(
            "Upload failed",
            extra={
                "filename": file.filename,
                "session_id": session_id
            }
        )

        return {
            "status": "error",
            "message": "File upload failed"
        }