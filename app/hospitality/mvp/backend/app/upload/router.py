"""Upload API router for the file-upload prefab.

Exposes `/api/uploads` (multipart create, list, download-by-id, delete-by-id)
backed by `app/upload/storage.py::LocalStorage` for file bytes and a SQLModel
table (`UploadedFile`, defined in `app/upload/models.py`) for metadata. See
AGENTS.md for the full contract and DO/DO NOT rules (server-side validation,
unique filenames, no filename trust).
"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.database import get_session
from app.upload.models import UploadedFile
from app.upload.storage import LocalStorage, sanitize_filename

router = APIRouter(prefix="/api/uploads", tags=["uploads"])

_storage = LocalStorage()

# Configure per use case (see AGENTS.md "Configuring Limits").
MAX_FILE_SIZE_MB = 50
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024

# `None` accepts any content type. Restrict per use case, e.g.:
# ALLOWED_CONTENT_TYPES = {"application/pdf", "image/png", "image/jpeg"}
ALLOWED_CONTENT_TYPES: set[str] | None = None


class UploadedFileRead(BaseModel):
    """Public shape returned by every endpoint below.

    Excludes `stored_path` so the server-side storage layout is never
    exposed to clients.
    """

    id: str
    name: str
    content_type: str
    size: int
    uploaded_at: datetime


def _to_read_model(record: UploadedFile) -> UploadedFileRead:
    return UploadedFileRead(
        id=record.id,
        name=record.original_name,
        content_type=record.content_type,
        size=record.size,
        uploaded_at=record.uploaded_at,
    )


def _content_disposition(filename: str) -> str:
    """Build a `Content-Disposition` header value safe against header injection.

    Strips CR/LF (header-splitting) and quotes from the original filename
    before it is embedded — `filename` here is client-supplied and therefore
    untrusted.
    """
    safe = filename.replace("\r", "").replace("\n", "").replace('"', "'")
    return f'attachment; filename="{safe}"'


@router.post("", response_model=UploadedFileRead, status_code=201)
async def upload_file(
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_session),
) -> UploadedFileRead:
    """Accept one multipart file, validate it, and persist bytes + metadata."""
    if (
        ALLOWED_CONTENT_TYPES is not None
        and file.content_type not in ALLOWED_CONTENT_TYPES
    ):
        raise HTTPException(
            status_code=415, detail=f"Unsupported content type: {file.content_type}"
        )

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")
    if len(content) > MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File exceeds maximum size of {MAX_FILE_SIZE_MB} MB",
        )

    # `file.filename` is client-supplied and untrusted — sanitize it before it
    # touches the filesystem. `storage.save` additionally prefixes a UUID so
    # two uploads (even with an identical, already-sanitized name) can never
    # collide or overwrite one another.
    original_name = sanitize_filename(file.filename or "upload")
    stored_path = await _storage.save(original_name, content)

    record = UploadedFile(
        original_name=original_name,
        stored_path=stored_path,
        content_type=file.content_type or "application/octet-stream",
        size=len(content),
    )
    session.add(record)
    await session.commit()
    await session.refresh(record)

    return _to_read_model(record)


@router.get("", response_model=list[UploadedFileRead])
async def list_uploaded_files(
    session: AsyncSession = Depends(get_session),
) -> list[UploadedFileRead]:
    """List all uploaded files, most recently uploaded first."""
    result = await session.execute(
        select(UploadedFile).order_by(UploadedFile.uploaded_at.desc())
    )
    records = result.scalars().all()
    return [_to_read_model(record) for record in records]


@router.get("/{file_id}")
async def download_file(
    file_id: str, session: AsyncSession = Depends(get_session)
) -> StreamingResponse:
    """Stream a previously uploaded file back with its original content type."""
    record = await session.get(UploadedFile, file_id)
    if record is None:
        raise HTTPException(status_code=404, detail="File not found")

    content = await _storage.read(record.stored_path)
    return StreamingResponse(
        iter([content]),
        media_type=record.content_type,
        headers={"Content-Disposition": _content_disposition(record.original_name)},
    )


@router.delete("/{file_id}", status_code=204)
async def delete_file(
    file_id: str, session: AsyncSession = Depends(get_session)
) -> Response:
    """Delete a file's bytes and its metadata row."""
    record = await session.get(UploadedFile, file_id)
    if record is None:
        raise HTTPException(status_code=404, detail="File not found")

    await _storage.delete(record.stored_path)
    await session.delete(record)
    await session.commit()
    return Response(status_code=204)
