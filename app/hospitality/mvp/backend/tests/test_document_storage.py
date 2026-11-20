"""Tenant file storage: per-tenant folders, server-chosen names, no path escapes."""

import uuid

import pytest

from app.documents.storage import DocumentStorage, InvalidStorageKeyError

TENANT_A = uuid.UUID("11111111-1111-4111-8111-111111111111")
TENANT_B = uuid.UUID("22222222-2222-4222-8222-222222222222")


@pytest.fixture
def storage(tmp_path) -> DocumentStorage:
    return DocumentStorage(str(tmp_path / "docs"))


async def test_save_read_delete_round_trip(storage, tmp_path) -> None:
    key = await storage.save(TENANT_A, b"image-bytes", "png")

    assert key.startswith(f"{TENANT_A}/") and key.endswith(".png")
    assert await storage.read(TENANT_A, key) == b"image-bytes"
    assert (tmp_path / "docs" / key).is_file()

    await storage.delete(TENANT_A, key)
    await storage.delete(TENANT_A, key)  # already gone: no error
    assert not (tmp_path / "docs" / key).exists()
    with pytest.raises(FileNotFoundError):
        await storage.read(TENANT_A, key)


async def test_each_save_gets_its_own_name(storage) -> None:
    first = await storage.save(TENANT_A, b"same", "jpg")
    second = await storage.save(TENANT_A, b"same", "jpg")

    assert first != second


async def test_a_tenant_cannot_address_another_tenants_file(storage) -> None:
    key = await storage.save(TENANT_A, b"secret of A", "jpg")

    with pytest.raises(InvalidStorageKeyError):
        await storage.read(TENANT_B, key)
    with pytest.raises(InvalidStorageKeyError):
        await storage.delete(TENANT_B, key)
    assert await storage.read(TENANT_A, key) == b"secret of A"


@pytest.mark.parametrize(
    "key",
    [
        "",
        "file.png",
        f"{TENANT_A}",
        f"{TENANT_A}/",
        f"{TENANT_A}/../{TENANT_B}/file.png",
        f"{TENANT_A}/..",
        f"{TENANT_A}/sub/file.png",
        f"{TENANT_A}/..\\file.png",
        f"../{TENANT_A}/file.png",
        "/etc/passwd",
        f"{TENANT_A}//etc/passwd",
    ],
)
async def test_keys_outside_the_tenant_folder_are_refused(storage, key) -> None:
    with pytest.raises(InvalidStorageKeyError):
        await storage.read(TENANT_A, key)
    with pytest.raises(InvalidStorageKeyError):
        await storage.delete(TENANT_A, key)
