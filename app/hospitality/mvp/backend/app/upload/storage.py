"""Local filesystem storage adapter for the file-upload prefab.

`LocalStorage` implements the `StorageBackend` protocol by writing files to a
directory on disk, each prefixed with a UUID to avoid collisions and to keep
client-supplied filenames from ever being used as-is on the filesystem. Swap
in an S3/Azure-backed class that implements the same four async methods
(`save`, `read`, `delete`, `list_files`) to change backends without touching
`app/upload/router.py`.
"""

from __future__ import annotations

import re
import stat as stat_module
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol

import aiofiles
import aiofiles.os

from app.database import async_session_factory
from app.upload.models import UploadedFile

_UNSAFE_CHARS = re.compile(r"[^A-Za-z0-9._-]")


def sanitize_filename(filename: str) -> str:
    """Strip directory components and unsafe characters from a client-supplied filename.

    Removes path traversal attempts (`../`, absolute paths, embedded path
    separators) and replaces anything outside a conservative safe character
    set. The result is still client-influenced — callers must combine it with
    a server-generated unique prefix (see `LocalStorage.save`) rather than
    trusting it to be collision-free or non-empty on its own.
    """
    name = filename.strip().replace("\\", "/")
    name = Path(name).name  # drop any directory components, ../ included
    name = _UNSAFE_CHARS.sub("_", name)
    return name or "file"


class StorageBackend(Protocol):
    """Storage adapter contract. Implement this to swap in S3/Azure/etc.

    Any class that implements these four async methods can be dropped in for
    `LocalStorage` in `app/upload/router.py` without changing the router.
    """

    async def save(self, filename: str, content: bytes) -> str: ...

    async def read(self, path: str) -> bytes: ...

    async def delete(self, path: str) -> None: ...

    async def list_files(self) -> list[dict]: ...


class LocalStorage:
    """Stores uploaded files on the local filesystem under `base_dir`."""

    def __init__(self, base_dir: str = "uploads") -> None:
        self._base_dir = Path(base_dir)
        self._base_dir.mkdir(parents=True, exist_ok=True)

    @property
    def base_dir(self) -> Path:
        """Public accessor for the storage root directory."""
        return self._base_dir

    async def save(self, filename: str, content: bytes) -> str:
        """Write `content` to a new UUID-prefixed file and return its stored path."""
        safe_name = sanitize_filename(filename)
        stored_name = f"{uuid.uuid4().hex}_{safe_name}"
        stored_path = self._base_dir / stored_name

        async with aiofiles.open(stored_path, "wb") as handle:
            await handle.write(content)

        return str(stored_path)

    async def read(self, path: str) -> bytes:
        """Read the raw bytes stored at `path`."""
        resolved = self._resolve(path)
        async with aiofiles.open(resolved, "rb") as handle:
            return await handle.read()

    async def delete(self, path: str) -> None:
        """Remove the file at `path`. No-op if it does not exist."""
        resolved = self._resolve(path)
        try:
            await aiofiles.os.remove(resolved)
        except FileNotFoundError:
            pass

    async def list_files(self) -> list[dict]:
        """Return metadata for every file directly under `base_dir`.

        This lists the raw filesystem contents (stored name, path, size,
        last-modified time) — it is independent of any database metadata
        table a caller layers on top, and exists mainly for reconciliation /
        disaster-recovery tooling. `app/upload/router.py`'s `GET /api/uploads`
        lists from the database instead, since that is where original
        filenames and content types live.
        """
        entries: list[dict] = []
        names = await aiofiles.os.listdir(self._base_dir)

        for name in names:
            entry_path = self._base_dir / name
            file_stat = await aiofiles.os.stat(entry_path)
            if not stat_module.S_ISREG(file_stat.st_mode):
                continue

            entries.append(
                {
                    "stored_name": name,
                    "path": str(entry_path),
                    "size": file_stat.st_size,
                    "modified_at": datetime.fromtimestamp(
                        file_stat.st_mtime, tz=timezone.utc
                    ).isoformat(),
                }
            )

        return entries

    def _resolve(self, path: str) -> Path:
        """Resolve `path` and ensure it stays within `base_dir`.

        Defence in depth: `path` normally comes from a database record this
        same class wrote, but if a caller ever passes through an
        externally-influenced path, this stops it from escaping the storage
        root.
        """
        resolved = Path(path).resolve()
        base_resolved = self._base_dir.resolve()
        if resolved != base_resolved and base_resolved not in resolved.parents:
            raise ValueError(f"Path {path!r} escapes storage base directory")
        return resolved


async def get_upload_path(upload_id: str) -> Path | None:
    """Resolve an upload id to its file path on disk, or `None` if it doesn't exist.

    Integration point for other prefabs (e.g. `document-extract`) that need
    to read an already-uploaded file without going through the `/api/uploads`
    HTTP endpoints. Looks up `stored_path` from the `UploadedFile` table
    directly — the same metadata `app/upload/router.py` writes on upload —
    rather than opening a second, competing way to resolve uploads.
    """
    async with async_session_factory() as session:
        record = await session.get(UploadedFile, upload_id)
        if record is None:
            return None
        return Path(record.stored_path)
