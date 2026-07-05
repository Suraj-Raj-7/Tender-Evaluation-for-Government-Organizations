"""
backend/app/services/storage.py
-----------------------------------
Purpose: The only file in the project that talks directly to MinIO
(file storage). Handles uploading files, downloading them back, deleting
them, and generating temporary secure links to view them.

Why this file exists: If every router uploaded files to MinIO on its
own, the connection setup and bucket logic would be duplicated
everywhere. Centralizing it here means routers just call
upload_file(...) and don't need to know MinIO exists underneath.
"""

import uuid
from io import BytesIO
from minio import Minio
from minio.error import S3Error
from app.config import settings


# The "bucket" is like a top-level folder inside MinIO where all of
# TenderIQ's documents live, separate from any other project's files.
BUCKET_NAME = "tenderiq-documents"

# One shared MinIO client, built from settings loaded in config.py.
# secure=False because we're running MinIO locally over plain HTTP,
# not HTTPS (fine for local development).
_client = Minio(
    settings.MINIO_ENDPOINT,
    access_key=settings.MINIO_ACCESS_KEY,
    secret_key=settings.MINIO_SECRET_KEY,
    secure=False,
)


def _ensure_bucket_exists():
    """
    Purpose: Creates the "tenderiq-documents" bucket the very first time
    this file is used, if it doesn't already exist. Safe to call
    repeatedly -- does nothing if the bucket is already there.

    Where it's used: Called once automatically, right below, when this
    module is first imported (e.g. by main.py or a router).
    """
    found = _client.bucket_exists(BUCKET_NAME)
    if not found:
        _client.make_bucket(BUCKET_NAME)


_ensure_bucket_exists()


def upload_file(file_bytes: bytes, original_filename: str, content_type: str) -> str:
    """
    Purpose: Saves a file's raw bytes into MinIO and returns a unique
    path string that identifies it, to be stored in a Document row's
    storage_path column.

    Where it gets its data: file_bytes comes from the uploaded file's
    content (read by a router, e.g. tenders.py's NIT upload endpoint).
    original_filename is only used to preserve the file extension.

    Where it's used: routers/tenders.py (NIT upload) and
    routers/bidders.py (bid document upload), both in this phase.
    """
    # A random, unique name prevents different users' files from ever
    # colliding, even if they upload files with the same original name.
    extension = original_filename.rsplit(".", 1)[-1] if "." in original_filename else "bin"
    storage_path = f"{uuid.uuid4()}.{extension}"

    _client.put_object(
        BUCKET_NAME,
        storage_path,
        data=BytesIO(file_bytes),
        length=len(file_bytes),
        content_type=content_type,
    )
    return storage_path


def download_file(storage_path: str) -> bytes:
    """
    Purpose: Retrieves a file's raw bytes back from MinIO, given the
    storage_path that was saved in its Document row.

    Where it's used: services/ocr.py (to run OCR on a file),
    routers/documents.py (to serve a file back to the browser).
    """
    response = _client.get_object(BUCKET_NAME, storage_path)
    try:
        return response.read()
    finally:
        response.close()
        response.release_conn()


def delete_file(storage_path: str):
    """
    Purpose: Removes a file from MinIO entirely. Not currently called
    anywhere in Phase 2, but provided since documents can be replaced
    before a bidder's deadline (per spec 2.3).

    Where it's used: Will be called by a future "replace document"
    endpoint if/when that's built.
    """
    try:
        _client.remove_object(BUCKET_NAME, storage_path)
    except S3Error:
        # If the file was already deleted or never existed, this is a
        # safe no-op rather than crashing the calling request.
        pass


def get_presigned_url(storage_path: str, expires_seconds: int = 3600) -> str:
    """
    Purpose: Generates a temporary, secure link to view/download a file
    directly from MinIO, without exposing MinIO's real credentials to
    the browser. The link stops working after expires_seconds.

    Where it's used: routers/documents.py, when building a link the
    frontend's DocumentViewer (Phase 5) can open directly.
    """
    from datetime import timedelta
    return _client.presigned_get_object(
        BUCKET_NAME, storage_path, expires=timedelta(seconds=expires_seconds)
    )