"""Where tenant files are kept: one folder per tenant, server-chosen names.

Built on the upload prefab's `LocalStorage` for the file I/O. A file is addressed by
a storage key `<tenant id>/<random>.<ext>`; the key is stored on the `document` row
and is never shown to clients. Nothing a client sends is used in a path.

To move to object storage, give `DocumentStorage` another backend with the same
three methods.
"""

import uuid
from pathlib import Path
from uuid import UUID

from app.config import settings
from app.upload.storage import LocalStorage

_KEY_PARTS = 2


class InvalidStorageKeyError(ValueError):
    """The key does not name a file inside the tenant's folder."""


class DocumentStorage:
    def __init__(self, base_dir: str | None = None) -> None:
        self._base_dir = Path(base_dir or settings.DOCUMENT_STORAGE_DIR)

    def _tenant_store(self, tenant_id: UUID) -> LocalStorage:
        return LocalStorage(str(self._base_dir / str(tenant_id)))

    def _split(self, tenant_id: UUID, storage_key: str) -> tuple[LocalStorage, str]:
        """The tenant's store and the file path for `storage_key`, or an error.

        A key must be exactly `<this tenant>/<file name>`; anything else — another
        tenant's folder, `..`, an absolute path — is refused before touching disk.
        """
        parts = storage_key.split("/")
        if len(parts) != _KEY_PARTS or parts[0] != str(tenant_id):
            raise InvalidStorageKeyError("storage key is outside the tenant folder")
        name = parts[1]
        if not name or name in {".", ".."} or Path(name).name != name or "\\" in name:
            raise InvalidStorageKeyError("storage key is not a plain file name")
        store = self._tenant_store(tenant_id)
        return store, str(store.base_dir / name)

    async def save(self, tenant_id: UUID, content: bytes, extension: str) -> str:
        """Store `content` and return its storage key."""
        stored_path = await self._tenant_store(tenant_id).save(
            f"{uuid.uuid4().hex}.{extension}", content
        )
        return f"{tenant_id}/{Path(stored_path).name}"

    async def read(self, tenant_id: UUID, storage_key: str) -> bytes:
        store, path = self._split(tenant_id, storage_key)
        return await store.read(path)

    async def delete(self, tenant_id: UUID, storage_key: str) -> None:
        """Remove the file. No error when it is already gone."""
        store, path = self._split(tenant_id, storage_key)
        await store.delete(path)


def get_document_storage() -> DocumentStorage:
    """FastAPI dependency / factory, so tests can point storage at a temp folder."""
    return DocumentStorage()
