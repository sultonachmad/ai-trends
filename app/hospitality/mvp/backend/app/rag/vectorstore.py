"""Qdrant vector store helpers — collection management, upsert, and search."""

from __future__ import annotations

import logging
import uuid

from qdrant_client import QdrantClient, models
from qdrant_client.models import Distance, PointStruct, VectorParams

from app.config import settings

log = logging.getLogger(__name__)

_client: QdrantClient | None = None


def get_client() -> QdrantClient:
    global _client
    if _client is None:
        _client = QdrantClient(url=settings.QDRANT_URL)
    return _client


def ensure_collection(collection: str, vector_size: int = 1024) -> None:
    client = get_client()
    if not client.collection_exists(collection):
        client.create_collection(
            collection_name=collection,
            vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE),
        )
        log.info("Created Qdrant collection: %s (dim=%d)", collection, vector_size)


def upsert_points(collection: str, texts: list[str], vectors: list[list[float]], metadatas: list[dict]) -> int:
    client = get_client()
    points = [
        PointStruct(
            id=str(uuid.uuid4()),
            vector=vec,
            payload={**meta, "text": text},
        )
        for text, vec, meta in zip(texts, vectors, metadatas)
    ]
    client.upsert(collection_name=collection, points=points)
    return len(points)


def search(collection: str, query_vector: list[float], top_k: int = 5) -> list[dict]:
    client = get_client()
    results = client.query_points(
        collection_name=collection,
        query=query_vector,
        limit=top_k,
    )
    return [
        {
            "text": hit.payload.get("text", ""),
            "score": hit.score,
            "metadata": {k: v for k, v in hit.payload.items() if k != "text"},
        }
        for hit in results.points
    ]


def delete_by_metadata(collection: str, filters: dict[str, str]) -> int:
    """Delete all points matching the given payload key-value filters.

    Args:
        collection: Qdrant collection name.
        filters: Dict of payload field → value to match. All conditions
                 are ANDed (a point must match every filter to be deleted).

    Examples:
        delete_by_metadata("docs", {"file_name": "resume.pdf"})
        delete_by_metadata("docs", {"file_hash": "a3f1b2c4"})
        delete_by_metadata("docs", {"file_name": "old.pdf", "file_hash": "abc123"})
    """
    if not filters:
        raise ValueError("At least one filter is required")
    client = get_client()
    conditions = [
        models.FieldCondition(key=k, match=models.MatchValue(value=v))
        for k, v in filters.items()
    ]
    result = client.delete(
        collection_name=collection,
        points_selector=models.FilterSelector(
            filter=models.Filter(must=conditions)
        ),
    )
    log.info("Deleted points matching %s in %s", filters, collection)
    return getattr(result, "operation_id", 0)


def delete_collection(collection: str) -> None:
    client = get_client()
    if client.collection_exists(collection):
        client.delete_collection(collection)
        log.info("Deleted Qdrant collection: %s", collection)
