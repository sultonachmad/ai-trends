"""AiChunk entity — table ``aichunk``.

Tenant database, S. AI assistant layer.

Grounding knowledge base (full-text now; pgvector later).

Mirrors .ttest/contexts/schema-tenant.sql; the Alembic migration creates the table.
"""

from uuid import UUID

from sqlalchemy import (
    REAL,
    Column,
    Computed,
    ForeignKeyConstraint,
    Index,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.dialects.postgresql import ARRAY, TSVECTOR
from sqlmodel import Field, SQLModel

from app.crud.base_model import MIGRATION_ONLY, TenantRecord


class AiChunk(TenantRecord, table=True):
    """Grounding knowledge base (full-text now; pgvector later)."""

    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="aichunk_tenant_id_id_key"),
        UniqueConstraint(
            "tenant_id",
            "knowledge_item_id",
            "chunk_index",
            name="aichunk_tenant_id_knowledge_item_id_chunk_index_key",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "knowledge_item_id"],
            ["aiknowledgeitem.tenant_id", "aiknowledgeitem.id"],
            name="aichunk_tenant_id_knowledge_item_id_fkey",
            ondelete="CASCADE",
        ),
        Index("ix_aichunk_tsv", "content_tsv", postgresql_using="gin"),
        MIGRATION_ONLY,
    )

    knowledge_item_id: UUID = Field(sa_type=Uuid)
    chunk_index: int = Field()
    content: str = Field(sa_type=Text)
    content_tsv: str | None = Field(
        default=None,
        sa_column=Column(
            "content_tsv",
            TSVECTOR,
            Computed("to_tsvector('simple'::regconfig, content)", persisted=True),
        ),
    )
    embedding: list[float] | None = Field(
        default=None,
        sa_type=ARRAY(REAL),
        description="switch to vector(N) when pgvector is installed",
    )
    embedding_model: str | None = Field(default=None, sa_type=Text)


class AiChunkCreate(SQLModel):
    """Fields accepted when creating a AiChunk."""

    knowledge_item_id: UUID
    chunk_index: int
    content: str
    embedding: list[float] | None = None
    embedding_model: str | None = None


class AiChunkUpdate(SQLModel):
    """Fields accepted when patching a AiChunk (all optional)."""

    knowledge_item_id: UUID | None = None
    chunk_index: int | None = None
    content: str | None = None
    embedding: list[float] | None = None
    embedding_model: str | None = None


class AiChunkRead(SQLModel):
    """Fields returned when reading a AiChunk (never returns: content_tsv)."""

    id: UUID
    tenant_id: UUID
    knowledge_item_id: UUID
    chunk_index: int
    content: str
    embedding: list[float] | None
    embedding_model: str | None
