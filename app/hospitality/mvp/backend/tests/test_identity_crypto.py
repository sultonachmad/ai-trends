"""Encrypting identity numbers and images, and the keyed hash for "seen before"."""

import base64
import logging
import uuid

import pytest

from app.config import Settings
from app.security import identity_crypto as crypto
from app.security.identity_crypto import (
    IdentityCipher,
    IdentityKeyError,
    cipher_from_settings,
)

KEY = base64.b64encode(bytes(range(32))).decode()
TENANT = uuid.UUID("11111111-1111-1111-1111-111111111111")
OTHER = uuid.UUID("22222222-2222-2222-2222-222222222222")
ROW = uuid.UUID("33333333-3333-3333-3333-333333333333")
OTHER_ROW = uuid.UUID("44444444-4444-4444-4444-444444444444")


def _cipher(key: str = KEY) -> IdentityCipher:
    return cipher_from_settings(Settings(IDENTITY_KEY=key))


def test_a_number_round_trips_and_is_not_stored_in_clear() -> None:
    cipher = _cipher()

    sealed = cipher.encrypt_number(TENANT, ROW, "3171234501900001")

    assert b"3171234501900001" not in sealed
    assert cipher.decrypt_number(TENANT, ROW, sealed) == "3171234501900001"


def test_the_same_number_encrypts_differently_each_time() -> None:
    cipher = _cipher()

    assert cipher.encrypt_number(TENANT, ROW, "A1234567") != cipher.encrypt_number(
        TENANT, ROW, "A1234567"
    )


def test_ciphertext_of_one_tenant_cannot_be_opened_as_another() -> None:
    cipher = _cipher()
    sealed = cipher.encrypt_number(TENANT, ROW, "A1234567")

    with pytest.raises(crypto.IdentityDecryptError):
        cipher.decrypt_number(OTHER, ROW, sealed)


def test_a_tampered_ciphertext_is_refused() -> None:
    cipher = _cipher()
    sealed = bytearray(cipher.encrypt_number(TENANT, ROW, "A1234567"))
    sealed[-1] ^= 1

    with pytest.raises(crypto.IdentityDecryptError):
        cipher.decrypt_number(TENANT, ROW, bytes(sealed))


def test_another_key_cannot_open_it() -> None:
    sealed = _cipher().encrypt_number(TENANT, ROW, "A1234567")
    other_key = base64.b64encode(bytes(range(1, 33))).decode()

    with pytest.raises(crypto.IdentityDecryptError):
        _cipher(other_key).decrypt_number(TENANT, ROW, sealed)


def test_files_round_trip() -> None:
    cipher = _cipher()
    image = b"\xff\xd8\xff" + bytes(2000)

    sealed = cipher.encrypt_file(TENANT, ROW, image)

    assert image not in sealed
    assert cipher.decrypt_file(TENANT, ROW, sealed) == image


def test_a_number_cannot_be_opened_as_a_file() -> None:
    cipher = _cipher()
    sealed = cipher.encrypt_number(TENANT, ROW, "A1234567")

    with pytest.raises(crypto.IdentityDecryptError):
        cipher.decrypt_file(TENANT, ROW, sealed)


def test_the_keyed_hash_is_stable_per_tenant_and_type_and_ignores_spacing() -> None:
    cipher = _cipher()

    one = cipher.number_hash(TENANT, "passport", "a 123 4567")
    assert one == cipher.number_hash(TENANT, "passport", "A1234567")
    assert one != cipher.number_hash(OTHER, "passport", "A1234567")
    assert one != cipher.number_hash(TENANT, "ktp", "A1234567")
    assert "A1234567" not in one


def test_a_key_that_is_not_32_bytes_is_refused() -> None:
    short = base64.b64encode(b"short").decode()

    with pytest.raises(IdentityKeyError):
        _cipher(short)


def test_a_key_that_is_not_base64_is_refused() -> None:
    with pytest.raises(IdentityKeyError):
        _cipher("not base64 at all!!")


def test_without_a_key_development_derives_one_and_warns(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.WARNING):
        cipher = cipher_from_settings(Settings(IDENTITY_KEY=""))

    assert cipher.uses_fallback_key
    assert "PREFAB_IDENTITY_KEY" in caplog.text
    sealed = cipher.encrypt_number(TENANT, ROW, "A1234567")
    assert cipher.decrypt_number(TENANT, ROW, sealed) == "A1234567"


def test_a_real_key_is_not_a_fallback() -> None:
    assert not _cipher().uses_fallback_key


def test_mask_shows_only_the_ends() -> None:
    assert crypto.mask("3171234501900001") == "3171••••••••0001"
    assert crypto.mask("A1234567") == "A1••••67"
    assert crypto.mask("1234") == "••••"


def test_ciphertext_copied_to_another_row_does_not_open() -> None:
    cipher = _cipher()
    sealed = cipher.encrypt_number(TENANT, ROW, "A1234567")

    with pytest.raises(crypto.IdentityDecryptError):
        cipher.decrypt_number(TENANT, OTHER_ROW, sealed)
