"""RAG API endpoints — upload documents, search, and ask with LLM."""

from __future__ import annotations

import hashlib
import logging
import tempfile
from pathlib import Path

import litellm
from fastapi import APIRouter, HTTPException, UploadFile
from pydantic import BaseModel

from app.access import (
    FEATURES_DELETE,
    FEATURES_DELETE_DESCRIPTION,
    FEATURES_USE,
    FEATURES_USE_DESCRIPTION,
    require_access,
)
from app.config import settings
from app.rag.chunker import chunk_text
from app.rag.embedder import embed_query, embed_texts
from app.rag.vectorstore import (
    delete_by_metadata,
    delete_collection,
    ensure_collection,
    search,
    upsert_points,
)

log = logging.getLogger(__name__)

# Uploads, searches and asks check features:use; the two deletes also check features:delete
# (app.access, ADR-0058): rbac's permission when rbac is installed, else the session
# (auth-session is a hard `requires` of this prefab).
router = APIRouter(
    prefix="/api/rag",
    tags=["rag"],
    dependencies=[require_access(FEATURES_USE, FEATURES_USE_DESCRIPTION)],
)

DEFAULT_COLLECTION = settings.RAG_COLLECTION


def _extract_text(path: Path) -> str:
    """Extract plain text from a file. Supports .txt, .md, .csv, .pdf."""
    suffix = path.suffix.lower()
    if suffix in (".txt", ".md", ".csv", ".json"):
        return path.read_text(encoding="utf-8", errors="replace")
    if suffix == ".pdf":
        try:
            from pypdf import PdfReader
            reader = PdfReader(str(path))
            return "\n\n".join(p.extract_text() or "" for p in reader.pages)
        except ImportError:
            raise HTTPException(status_code=422, detail="pypdf not installed — cannot process PDF")
    raise HTTPException(status_code=422, detail=f"Unsupported file type: {suffix}")


class UploadResponse(BaseModel):
    filename: str
    chunks: int
    collection: str


@router.post("/upload", response_model=UploadResponse)
async def upload_document(
    file: UploadFile,
    collection: str = DEFAULT_COLLECTION,
) -> UploadResponse:
    """Upload a document, chunk it, embed chunks, and store in Qdrant."""
    filename = file.filename or "untitled"
    # Reject an over-limit upload as early as the handler can. `UploadFile.size`
    # is populated by the multipart parser, so this refuses an oversized file
    # before it is read into memory or embedded. NOTE: the ASGI server has
    # already spooled the request body (to a SpooledTemporaryFile) before this
    # handler runs, so a COMPLETE ingress DoS bound must ALSO be enforced at the
    # server/reverse-proxy layer (a max request-body size) — this cap governs
    # in-app processing, not the raw receive.
    if file.size is not None and file.size > settings.RAG_MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File exceeds the {settings.RAG_MAX_UPLOAD_BYTES}-byte upload limit",
        )
    # Defense-in-depth for the case where `size` is unset: read one byte past
    # the cap so an over-limit body never lands fully in memory.
    content = await file.read(settings.RAG_MAX_UPLOAD_BYTES + 1)
    if len(content) > settings.RAG_MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File exceeds the {settings.RAG_MAX_UPLOAD_BYTES}-byte upload limit",
        )

    with tempfile.NamedTemporaryFile(suffix=Path(filename).suffix, delete=False) as tmp:
        tmp.write(content)
        tmp_path = Path(tmp.name)

    try:
        text = _extract_text(tmp_path)
    finally:
        tmp_path.unlink(missing_ok=True)

    if not text.strip():
        raise HTTPException(status_code=422, detail="No text could be extracted from the file")

    chunks = chunk_text(text, chunk_size=1000, chunk_overlap=200)
    vectors = await embed_texts(chunks)

    ensure_collection(collection, vector_size=len(vectors[0]))

    file_hash = hashlib.sha256(filename.encode()).hexdigest()[:16]
    metadatas = [
        {"file_name": filename, "file_hash": file_hash, "chunk_index": i}
        for i in range(len(chunks))
    ]
    count = upsert_points(collection, chunks, vectors, metadatas)

    return UploadResponse(filename=filename, chunks=count, collection=collection)


async def _retrieve(query: str, collection: str, top_k: int) -> list[dict]:
    """Embed the query and search the vector store, mapping any embedding-provider
    or vector-store failure to the same sanitized shape the LLM path returns.
    Left unwrapped, this leg surfaces as FastAPI's default 500 — generic, so
    nothing leaks, but inconsistent with the hardened error contract.
    """
    try:
        query_vec = await embed_query(query)
        return search(collection, query_vec, top_k=top_k)
    except HTTPException:
        raise
    except Exception:
        log.exception("RAG retrieval failed")
        raise HTTPException(status_code=502, detail="Retrieval failed")


class SearchRequest(BaseModel):
    query: str
    collection: str = DEFAULT_COLLECTION
    top_k: int = 5


class SearchHit(BaseModel):
    text: str
    score: float
    metadata: dict


class SearchResponse(BaseModel):
    hits: list[SearchHit]


@router.post("/search", response_model=SearchResponse)
async def similarity_search(body: SearchRequest) -> SearchResponse:
    """Search for similar documents in the vector store."""
    hits = await _retrieve(body.query, body.collection, body.top_k)
    return SearchResponse(hits=[SearchHit(**h) for h in hits])


class AskRequest(BaseModel):
    question: str
    collection: str = DEFAULT_COLLECTION
    top_k: int = 5
    model: str | None = None


class AskResponse(BaseModel):
    answer: str
    model: str
    sources: list[SearchHit]


@router.post("/ask", response_model=AskResponse)
async def ask_with_rag(body: AskRequest) -> AskResponse:
    """Retrieve relevant chunks and answer the question using an LLM."""
    hits = await _retrieve(body.question, body.collection, body.top_k)

    if not hits:
        return AskResponse(
            answer="No relevant documents found. Please upload documents first.",
            model=body.model or settings.LLM_MODEL,
            sources=[],
        )

    context = "\n\n---\n\n".join(
        f"[Source: {h['metadata'].get('file_name', 'unknown')}]\n{h['text']}"
        for h in hits
    )

    system_prompt = (
        "You are a helpful assistant that answers questions based on the provided context. "
        "Use ONLY the context below to answer. If the answer is not in the context, say so. "
        "Cite the source file name when possible."
    )

    try:
        response = await litellm.acompletion(
            model=body.model or settings.LLM_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Context:\n{context}\n\nQuestion: {body.question}"},
            ],
            max_tokens=2000,
        )
        answer = response.choices[0].message.content
        model_used = response.model
    except Exception:
        log.exception("RAG ask request failed")
        raise HTTPException(status_code=502, detail="LLM request failed")

    return AskResponse(
        answer=answer,
        model=model_used,
        sources=[SearchHit(**h) for h in hits],
    )


class DeleteByMetadataRequest(BaseModel):
    filters: dict[str, str]
    collection: str = DEFAULT_COLLECTION


@router.delete(
    "/points",
    dependencies=[require_access(FEATURES_DELETE, FEATURES_DELETE_DESCRIPTION)],
)
async def remove_by_metadata(body: DeleteByMetadataRequest) -> dict:
    """Delete all vectors matching the given metadata filters.

    Examples:
        {"filters": {"file_name": "resume.pdf"}}
        {"filters": {"file_hash": "a3f1b2c4"}}
        {"filters": {"file_name": "old.pdf", "file_hash": "abc123"}}
    """
    if not body.filters:
        raise HTTPException(status_code=422, detail="At least one filter is required")
    delete_by_metadata(body.collection, body.filters)
    return {"status": "ok", "filters": body.filters}


class DeleteCollectionRequest(BaseModel):
    collection: str = DEFAULT_COLLECTION


@router.delete(
    "/collection",
    dependencies=[require_access(FEATURES_DELETE, FEATURES_DELETE_DESCRIPTION)],
)
async def remove_collection(body: DeleteCollectionRequest) -> dict:
    """Delete an entire collection from Qdrant."""
    delete_collection(body.collection)
    return {"status": "ok", "deleted": body.collection}
