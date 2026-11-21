"""Simple text chunker — splits documents into overlapping chunks for embedding."""

from __future__ import annotations


def chunk_text(
    text: str,
    chunk_size: int = 1000,
    chunk_overlap: int = 200,
) -> list[str]:
    """Split text into overlapping chunks by character count.

    Uses paragraph breaks as preferred split points, falling back to
    sentence boundaries, then hard character splits.
    """
    if len(text) <= chunk_size:
        return [text]

    separators = ["\n\n", "\n", ". ", " "]
    return _recursive_split(text, separators, chunk_size, chunk_overlap)


def _recursive_split(
    text: str,
    separators: list[str],
    chunk_size: int,
    chunk_overlap: int,
) -> list[str]:
    if len(text) <= chunk_size:
        return [text.strip()] if text.strip() else []

    sep = separators[0] if separators else ""
    remaining_seps = separators[1:] if len(separators) > 1 else []

    if sep and sep in text:
        parts = text.split(sep)
    else:
        if remaining_seps:
            return _recursive_split(text, remaining_seps, chunk_size, chunk_overlap)
        chunks = []
        for i in range(0, len(text), chunk_size - chunk_overlap):
            chunk = text[i : i + chunk_size].strip()
            if chunk:
                chunks.append(chunk)
        return chunks

    chunks: list[str] = []
    current = ""
    for part in parts:
        candidate = f"{current}{sep}{part}" if current else part
        if len(candidate) <= chunk_size:
            current = candidate
        else:
            if current.strip():
                chunks.append(current.strip())
            if len(part) > chunk_size and remaining_seps:
                chunks.extend(_recursive_split(part, remaining_seps, chunk_size, chunk_overlap))
                current = ""
            else:
                current = part

    if current.strip():
        chunks.append(current.strip())

    return chunks
