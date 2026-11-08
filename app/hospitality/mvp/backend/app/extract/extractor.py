"""PDF and DOCX text extraction for document parsing (e.g. CV/resume extraction).

Supported formats:
    - PDF (`application/pdf`) via pdfplumber, extracted page by page.
    - DOCX (`application/vnd.openxmlformats-officedocument.wordprocessingml.document`)
      via python-docx, combining paragraph text and table cell text.

Legacy binary `.doc` files are NOT supported: python-docx only reads the
OOXML `.docx` format. Reject `.doc` uploads before calling `extract_text`
rather than attempting to parse them.

The extracted text returned here is ephemeral — callers are responsible for
not persisting it beyond the lifetime of the request/job that needed it. For
CV parsing, hand the raw `ExtractResult.text` to an LLM prompt to pull out
structured fields (name, skills, experience); this module does no NLP itself.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pdfplumber
from docx import Document as DocxDocument

PDF_CONTENT_TYPE = "application/pdf"
DOCX_CONTENT_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

# Hard cap on how long a single extraction may run in its worker thread.
# Prevents a large or pathological file from tying up a thread indefinitely.
_EXTRACTION_TIMEOUT_SECONDS = 30.0


class ExtractionError(Exception):
    """Raised when a document's content cannot be extracted.

    Covers corrupt files and password-protected/encrypted PDFs that
    pdfplumber cannot open, as well as extraction that exceeded
    `_EXTRACTION_TIMEOUT_SECONDS`.
    """


@dataclass(frozen=True)
class ExtractResult:
    """The result of extracting text from a single PDF or DOCX document."""

    text: str
    page_count: int | None
    metadata: dict[str, Any]


async def extract_text(file_path: Path | str, content_type: str) -> ExtractResult:
    """Extract text from the PDF or DOCX file at `file_path`.

    Routes to `_extract_pdf` or `_extract_docx` based on `content_type`. The
    underlying extraction is synchronous (pdfplumber/python-docx do blocking
    I/O and CPU work), so it runs in a worker thread with a timeout to avoid
    blocking the event loop on a large or malformed file.

    Raises:
        ValueError: `content_type` is not a supported PDF or DOCX MIME type.
        ExtractionError: the file could not be parsed, or extraction timed out.
    """
    path = Path(file_path)

    if content_type == PDF_CONTENT_TYPE:
        extractor = _extract_pdf
    elif content_type == DOCX_CONTENT_TYPE:
        extractor = _extract_docx
    else:
        raise ValueError(f"Unsupported content type for extraction: {content_type!r}")

    try:
        return await asyncio.wait_for(
            asyncio.to_thread(extractor, path),
            timeout=_EXTRACTION_TIMEOUT_SECONDS,
        )
    except TimeoutError as exc:
        raise ExtractionError(
            f"Extraction timed out after {_EXTRACTION_TIMEOUT_SECONDS:.0f}s: {path.name!r}"
        ) from exc


def _extract_pdf(path: Path) -> ExtractResult:
    """Extract text from a PDF, page by page, preserving reading order.

    Any failure to open or read the PDF — corrupt file, password-protected
    or otherwise encrypted content pdfplumber cannot decode, etc. — is
    raised as an `ExtractionError` instead of letting pdfminer's internal
    exceptions propagate.
    """
    pages: list[str] = []
    metadata: dict[str, Any] = {"author": None, "title": None}

    try:
        with pdfplumber.open(path) as pdf:
            if pdf.metadata:
                metadata = {
                    "author": pdf.metadata.get("Author"),
                    "title": pdf.metadata.get("Title"),
                }
            for page in pdf.pages:
                pages.append((page.extract_text() or "").strip())
    except Exception as exc:
        raise ExtractionError(f"Failed to extract PDF {path.name!r}: {exc}") from exc

    return ExtractResult(
        text="\n\n".join(pages),
        page_count=len(pages),
        metadata=metadata,
    )


def _extract_docx(path: Path) -> ExtractResult:
    """Extract text from a DOCX: all paragraph text, then all table cell text."""
    try:
        document = DocxDocument(str(path))
    except Exception as exc:
        raise ExtractionError(f"Failed to extract DOCX {path.name!r}: {exc}") from exc

    paragraphs = [p.text.strip() for p in document.paragraphs if p.text.strip()]

    table_cells = [
        cell.text.strip()
        for table in document.tables
        for row in table.rows
        for cell in row.cells
        if cell.text.strip()
    ]

    core_properties = document.core_properties
    metadata: dict[str, Any] = {
        "author": core_properties.author or None,
        "title": core_properties.title or None,
    }

    return ExtractResult(
        text="\n\n".join([*paragraphs, *table_cells]),
        page_count=None,
        metadata=metadata,
    )
