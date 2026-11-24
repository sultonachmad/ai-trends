"""Encryption for identity numbers and ID images, and a keyed hash for "seen before".

One 32-byte key (`PREFAB_IDENTITY_KEY`, base64) is stretched with HKDF into three
sub-keys: one for numbers, one for files, one for the hash. Each is used for one job
only, so a number can never be opened as a file and the hash reveals nothing about the
encryption key.

Numbers and files are sealed with AES-GCM. The tenant id and the id of the row that
holds the value are bound in as associated data: ciphertext copied into another
tenant's rows, or onto another guest's record, does not open. A sealed value is
`version (1 byte) || nonce (12 bytes) || ciphertext+tag`.

Without a key (development) a key is derived from `PREFAB_SECRET_KEY` and a loud
warning is logged. Production refuses to start without a real key
(`app.security.startup_checks`). Losing the key makes stored numbers unreadable.
"""

import base64
import binascii
import hashlib
import hmac
import logging
import os
import re
from functools import lru_cache
from uuid import UUID

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from app.config import Settings, settings

log = logging.getLogger(__name__)

KEY_BYTES = 32
NONCE_BYTES = 12
VERSION = b"\x01"
_HEADER = len(VERSION) + NONCE_BYTES
_FALLBACK_LABEL = b"prefab-identity-development-fallback"
_NOT_NUMBER = re.compile(r"[^0-9A-Z]")
MASK = "•"
_MASK_KEEP = 4  # characters kept at each end of a long number


class IdentityKeyError(ValueError):
    """`PREFAB_IDENTITY_KEY` is not a base64 encoded 32-byte key."""


class IdentityDecryptError(ValueError):
    """The value was not sealed with this key, for this tenant and this purpose."""


def parse_key(raw: str) -> bytes:
    """The 32 key bytes of a base64 `PREFAB_IDENTITY_KEY`, or IdentityKeyError."""
    try:
        key = base64.b64decode(raw.strip(), validate=True)
    except (binascii.Error, ValueError):
        raise IdentityKeyError("PREFAB_IDENTITY_KEY is not valid base64") from None
    if len(key) != KEY_BYTES:
        raise IdentityKeyError(f"PREFAB_IDENTITY_KEY must decode to {KEY_BYTES} bytes")
    return key


def _subkey(master: bytes, purpose: bytes) -> bytes:
    return HKDF(algorithm=hashes.SHA256(), length=KEY_BYTES, salt=None, info=purpose).derive(master)


def normalise_number(number: str) -> str:
    """Upper case, without spaces, dots or dashes: how a number is compared."""
    return _NOT_NUMBER.sub("", number.upper())


def mask(number: str) -> str:
    """`3171••••••••0001`: the ends of a long number, nothing of a short one."""
    if len(number) <= _MASK_KEEP:
        return MASK * len(number)
    keep = _MASK_KEEP if len(number) >= 3 * _MASK_KEEP else 2
    return number[:keep] + MASK * (len(number) - 2 * keep) + number[-keep:]


class IdentityCipher:
    """Seals and opens identity numbers and files for one tenant at a time."""

    def __init__(self, master: bytes, *, uses_fallback_key: bool = False) -> None:
        self._numbers = AESGCM(_subkey(master, b"identity-number-v1"))
        self._files = AESGCM(_subkey(master, b"identity-file-v1"))
        self._hash_key = _subkey(master, b"identity-hash-v1")
        self.uses_fallback_key = uses_fallback_key

    @staticmethod
    def _seal(aead: AESGCM, bound: bytes, plain: bytes) -> bytes:
        nonce = os.urandom(NONCE_BYTES)
        return VERSION + nonce + aead.encrypt(nonce, plain, bound)

    @staticmethod
    def _open(aead: AESGCM, bound: bytes, sealed: bytes) -> bytes:
        if len(sealed) <= _HEADER or sealed[:1] != VERSION:
            raise IdentityDecryptError("not a sealed identity value")
        try:
            return aead.decrypt(sealed[1:_HEADER], sealed[_HEADER:], bound)
        except InvalidTag:
            raise IdentityDecryptError("identity value does not open with this key") from None

    def encrypt_number(self, tenant_id: UUID, row_id: UUID, number: str) -> bytes:
        return self._seal(self._numbers, tenant_id.bytes + row_id.bytes, number.encode())

    def decrypt_number(self, tenant_id: UUID, row_id: UUID, sealed: bytes) -> str:
        return self._open(self._numbers, tenant_id.bytes + row_id.bytes, sealed).decode()

    def encrypt_file(self, tenant_id: UUID, row_id: UUID, content: bytes) -> bytes:
        return self._seal(self._files, tenant_id.bytes + row_id.bytes, content)

    def decrypt_file(self, tenant_id: UUID, row_id: UUID, sealed: bytes) -> bytes:
        return self._open(self._files, tenant_id.bytes + row_id.bytes, sealed)

    def number_hash(self, tenant_id: UUID, doc_type: str, number: str) -> str:
        """HMAC of tenant, type and normalised number: equal for the same document only."""
        message = f"{tenant_id}|{doc_type}|{normalise_number(number)}".encode()
        return hmac.new(self._hash_key, message, hashlib.sha256).hexdigest()


def cipher_from_settings(config: Settings) -> IdentityCipher:
    """The cipher for `config`; falls back to a key derived from the secret key, loudly."""
    if config.IDENTITY_KEY.strip():
        return IdentityCipher(parse_key(config.IDENTITY_KEY))
    log.warning(
        "PREFAB_IDENTITY_KEY is not set: guest ID numbers and images are encrypted with a "
        "key derived from PREFAB_SECRET_KEY. Set a random 32-byte base64 key and back it "
        "up before any real guest data is stored."
    )
    master = hmac.new(config.SECRET_KEY.encode(), _FALLBACK_LABEL, hashlib.sha256).digest()
    return IdentityCipher(master, uses_fallback_key=True)


@lru_cache(maxsize=1)
def get_identity_cipher() -> IdentityCipher:
    """The app's cipher (FastAPI dependency; built once)."""
    return cipher_from_settings(settings)
