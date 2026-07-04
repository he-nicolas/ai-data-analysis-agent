from fastapi import APIRouter, UploadFile, File, Form
import os
from ai_data_analysis_agent.core.logging import get_logger
import time
from ai_data_analysis_agent.core.session_store import set_file_path

router = APIRouter()
logger = get_logger(__name__)

UPLOAD_DIR = "data/uploaded_file"
os.makedirs(UPLOAD_DIR, exist_ok=True)


@router.post("/file/upload")
async def upload(file: UploadFile = File(...), session_id: str = Form(...)):
    start_time = time.time()

    logger.info(
        "Upload request received",
        extra={
            "file_name": file.filename,
            "session_id": session_id
        }
    )

    try:
        if not file.filename.endswith(".xlsx"):
            return {"status": "error", "message": "Only .xlsx allowed"}
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