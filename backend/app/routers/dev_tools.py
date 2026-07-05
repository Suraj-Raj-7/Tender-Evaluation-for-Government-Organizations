"""
backend/app/routers/dev_tools.py
------------------------------------
Purpose: Temporary developer-only endpoint to test the OCR pipeline
directly, without needing Celery (which doesn't exist until Phase 3).

Why this file exists: We need a way to actually verify extract_text()
works correctly on real documents right now. Once Phase 3's Celery
workers exist and call extract_text() themselves, this file's purpose
is done -- it's gated behind DEBUG mode so it's never reachable in a
real deployment.
"""

import tempfile
import os
from fastapi import APIRouter, UploadFile, File, HTTPException
from app.config import settings
from app.services.ocr import extract_text

router = APIRouter(prefix="/dev", tags=["dev-tools"])

IMAGE_EXTENSIONS = {"jpg", "jpeg", "png"}


@router.post("/ocr-test")
async def test_ocr(file: UploadFile = File(...)):
    """
    Purpose: Accepts one uploaded file, saves it to a temporary local
    file, runs extract_text() on it synchronously, and returns the
    result immediately -- lets us verify OCR works before Celery exists.

    Where it gets its data: file is whatever the developer uploads
    through Swagger UI's "Try it out" for manual testing.

    Note: Only available when settings.DEBUG is True (see main.py,
    where this router is only registered in debug mode).
    """
    if not settings.DEBUG:
        raise HTTPException(status_code=404, detail="Not found")

    extension = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    is_image = extension in IMAGE_EXTENSIONS

    contents = await file.read()

    # extract_text() needs a real file path on disk, so we write the
    # uploaded bytes to a temporary file first, then clean it up after.
    with tempfile.NamedTemporaryFile(delete=False, suffix=f".{extension}") as tmp:
        tmp.write(contents)
        tmp_path = tmp.name

    try:
        text, confidence, page_count, is_scanned = extract_text(tmp_path, is_image=is_image)
    finally:
        os.remove(tmp_path)

    return {
        "text": text,
        "confidence": confidence,
        "page_count": page_count,
        "is_scanned": is_scanned,
    }