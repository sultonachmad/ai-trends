"""Text embedding via litellm — supports Bedrock Titan, OpenAI, Cohere, etc."""

from __future__ import annotations

import logging

import litellm

from app.config import settings

log = logging.getLogger(__name__)


async def embed_texts(texts: list[str]) -> list[list[float]]:
    """Embed a batch of texts using the configured embedding model."""
    response = await litellm.aembedding(
        model=settings.EMBEDDING_MODEL,
        input=texts,
    )
    return [item["embedding"] for item in response.data]


async def embed_query(text: str) -> list[float]:
    """Embed a single query string."""
    vectors = await embed_texts([text])
    return vectors[0]
