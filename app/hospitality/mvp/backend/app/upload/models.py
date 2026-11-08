"""Persistence model for the file-upload prefab.

Split out from `app/upload/router.py` so `app/upload/storage.py` can resolve
an upload id to its stored path (`get_upload_path`) without importing the
router module and creating a circular import.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime
from sqlmodel import Field, SQLModel


class UploadedFile(SQLModel, table=True):
    """Metadata for one uploaded file.

    `stored_path` is the on-disk (or backend-specific) location returned by
    the storage adapter — it is internal and must never be returned to
    clients directly; see `UploadedFileRead` in `app/upload/router.py`.
    """

    id: str = Field(default_factory=lambda: uuid.uuid4().hex, primary_key=True)
    original_name: str
    stored_path: str
    content_type: str
    size: int
    uploaded_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        nullable=False,
        sa_type=DateTime(timezone=True),
    )
