"""FastAPI routes for PDF/DOCX text extraction.

Two entry points:
    - POST /api/extract                       — extract from a direct file upload.
    - POST /api/extract/from-upload/{upload_id} — extract from a file already
      stored via the file-upload prefab.

Extracted text is returned in the response only — nothing extracted here is
persisted by this router.
"""

from __future__ import annotations

import mimetypes
import tempfile
import uuid
from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile

from app.extract.extractor import ExtractionError, ExtractResult, extract_text

# `app.upload.storage` is provided by the `file-upload` prefab (a declared
# dependency of this prefab — see manifest.yaml `requires`). It must expose:
#
#   async def get_upload_path(upload_id: str) -> Path | None
#
# resolving an upload id to its file on disk, or None if the upload does not
# exist. Do not read from upload storage by any other path.
from app.upload.storage import get_upload_path

router = APIRouter(prefix="/api/extract", tags=["extract"])

MAX_UPLOAD_SIZE_BYTES = 50 * 1024 * 1024  # 50MB
_CHUNK_SIZE_BYTES = 1024 * 1024  # 1MB

_SUPPORTED_CONTENT_TYPES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}
_EXTENSION_CONTENT_TYPES = {
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}


@router.post("")
async def extract_from_file(file: UploadFile) -> ExtractResult:
    """Accept a file upload, extract its text, and return the result.

    The uploaded file is streamed to a temporary directory for the duration
    of extraction and removed afterwards, regardless of outcome.
    """
    content_type = _resolve_content_type(file.filename, file.content_type)

    with tempfile.TemporaryDirectory(prefix="document-extract-") as tmp_dir:
        tmp_path = await _save_upload(file, Path(tmp_dir))
        return await _run_extraction(tmp_path, content_type)


@router.post("/from-upload/{upload_id}")
async def extract_from_upload_id(upload_id: str) -> ExtractResult:
    """Extract text from a file already stored by the file-upload prefab."""
    upload_path = await get_upload_path(upload_id)
    if upload_path is None:
        raise HTTPException(status_code=404, detail=f"Upload not found: {upload_id!r}")

    if upload_path.stat().st_size > MAX_UPLOAD_SIZE_BYTES:
        raise HTTPException(
            status_code=422,
            detail=f"File exceeds maximum size of {MAX_UPLOAD_SIZE_BYTES // (1024 * 1024)}MB",
        )

    guessed_type, _ = mimetypes.guess_type(upload_path.name)
    content_type = _resolve_content_type(upload_path.name, guessed_type)
    return await _run_extraction(upload_path, content_type)


async def _run_extraction(path: Path, content_type: str) -> ExtractResult:
    """Run extraction and translate extractor failures into HTTP errors."""
    try:
        return await extract_text(path, content_type)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except ExtractionError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


async def _save_upload(upload: UploadFile, dest_dir: Path) -> Path:
    """Stream `upload` into `dest_dir`, enforcing `MAX_UPLOAD_SIZE_BYTES`."""
    suffix = Path(upload.filename or "").suffix
    dest_path = dest_dir / f"{uuid.uuid4().hex}{suffix}"

    size = 0
    with dest_path.open("wb") as buffer:
        while chunk := await upload.read(_CHUNK_SIZE_BYTES):
            size += len(chunk)
            if size > MAX_UPLOAD_SIZE_BYTES:
                raise HTTPException(
                    status_code=422,
                    detail=f"File exceeds maximum size of {MAX_UPLOAD_SIZE_BYTES // (1024 * 1024)}MB",
                )
            buffer.write(chunk)

    return dest_path


def _resolve_content_type(filename: str | None, content_type: str | None) -> str:
    """Resolve and validate the effective content type for `filename`.

    A client-supplied `content_type` is trusted only if it is already one of
    the supported types; otherwise the file extension is used to resolve it.
    Raises 422 if neither yields a supported PDF/DOCX type.
    """
    if content_type is not None and content_type in _SUPPORTED_CONTENT_TYPES:
        return content_type

    suffix = Path(filename or "").suffix.lower()
    resolved = _EXTENSION_CONTENT_TYPES.get(suffix)
    if resolved is None:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Unsupported file type: {filename!r}. "
                "Only PDF (.pdf) and DOCX (.docx) are supported."
            ),
        )
    return resolved
