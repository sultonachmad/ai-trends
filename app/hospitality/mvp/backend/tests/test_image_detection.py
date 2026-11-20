"""Only real JPEG / PNG / WebP content is accepted, whatever the file is called."""

import pytest

from app.documents.images import JPEG, PNG, WEBP, content_hash, detect_image_type

JPEG_BYTES = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00" + b"\x00" * 32
PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
WEBP_BYTES = b"RIFF\x24\x00\x00\x00WEBPVP8 " + b"\x00" * 32


@pytest.mark.parametrize(
    ("content", "expected"), [(JPEG_BYTES, JPEG), (PNG_BYTES, PNG), (WEBP_BYTES, WEBP)]
)
def test_accepted_images(content, expected) -> None:
    assert detect_image_type(content) == expected


@pytest.mark.parametrize(
    "content",
    [
        b"",
        b"\xff\xd8",  # too short to be a JPEG
        b"<html><script>alert(1)</script></html>",
        b'<?xml version="1.0"?><svg xmlns="http://www.w3.org/2000/svg" onload="alert(1)"/>',
        b"%PDF-1.7\n",
        b"GIF89a" + b"\x00" * 16,
        b"RIFF\x24\x00\x00\x00WAVEfmt ",  # RIFF, but audio
        b"RIFF\x24\x00",  # truncated RIFF
        b"PK\x03\x04",  # zip
        b"MZ\x90\x00",  # executable
        b" \xff\xd8\xff\xe0",  # image bytes not at the start
    ],
)
def test_everything_else_is_refused(content) -> None:
    assert detect_image_type(content) is None


def test_content_hash_identifies_identical_files_only() -> None:
    assert content_hash(JPEG_BYTES) == content_hash(bytes(JPEG_BYTES))
    assert content_hash(JPEG_BYTES) != content_hash(JPEG_BYTES + b"\x00")
    assert len(content_hash(b"")) == 64
