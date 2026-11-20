"""Deciding whether uploaded bytes are an image we accept — from the content itself.

File names and the browser's declared type are both chosen by the uploader, so
neither is trusted. Only JPEG, PNG and WebP are accepted; SVG and HTML (which can
carry scripts) never match.
"""

import hashlib
from dataclasses import dataclass


@dataclass(frozen=True)
class ImageType:
    content_type: str
    extension: str


JPEG = ImageType("image/jpeg", "jpg")
PNG = ImageType("image/png", "png")
WEBP = ImageType("image/webp", "webp")
ACCEPTED_IMAGE_TYPES: tuple[ImageType, ...] = (JPEG, PNG, WEBP)

_JPEG_START = b"\xff\xd8\xff"
_PNG_START = b"\x89PNG\r\n\x1a\n"
_RIFF = b"RIFF"
_WEBP = b"WEBP"
_WEBP_HEADER_LENGTH = 12


def detect_image_type(content: bytes) -> ImageType | None:
    """The image type of `content`, judged by its leading bytes; None when not accepted."""
    if content.startswith(_JPEG_START):
        return JPEG
    if content.startswith(_PNG_START):
        return PNG
    if (
        len(content) >= _WEBP_HEADER_LENGTH
        and content.startswith(_RIFF)
        and content[8:_WEBP_HEADER_LENGTH] == _WEBP
    ):
        return WEBP
    return None


def content_hash(content: bytes) -> str:
    """SHA-256 of the file, used to spot the same image submitted again."""
    return hashlib.sha256(content).hexdigest()
