"""AiKnowledgeItem entity — table ``aiknowledgeitem``.

Tenant database, S. AI assistant layer.

Property knowledge base used to ground every guest-facing answer.

Mirrors .ttest/contexts/schema-tenant.sql; the Alembic migration creates the table.
"""

import datetime as dt
from typing import Literal
from uuid import UUID

from sqlalchemy import CheckConstraint, ForeignKeyConstraint, Text, UniqueConstraint, Uuid, text
from sqlmodel import Field, SQLModel

from app.crud.base_model import MIGRATION_ONLY, TenantEntity

AiKnowledgeItemKind = Literal[
    "faq",
    "policy",
    "guide",
    "local_info",
    "manual",
    "menu",
    "other",
]


class AiKnowledgeItem(TenantEntity, table=True):
    """Property knowledge base used to ground every guest-facing answer."""

    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="aiknowledgeitem_tenant_id_id_key"),
        ForeignKeyConstraint(
            ["tenant_id", "property_id"],
            ["property.tenant_id", "property.id"],
            name="aiknowledgeitem_tenant_id_property_id_fkey",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "source_document_id"],
            ["document.tenant_id", "document.id"],
            name="aiknowledgeitem_tenant_id_source_document_id_fkey",
            ondelete="SET NULL (source_document_id)",
        ),
        CheckConstraint(
            ("kind IN ('faq', 'policy', 'guide', 'local_info', 'manual', 'menu', 'other')"),
            name="aiknowledgeitem_kind_check",
        ),
        MIGRATION_ONLY,
    )

    property_id: UUID = Field(sa_type=Uuid)
    kind: str = Field(sa_type=Text)
    title: str = Field(sa_type=Text)
    body: str = Field(sa_type=Text)
    locale: str = Field(
        default="id-ID", sa_type=Text, sa_column_kwargs={"server_default": text("'id-ID'::text")}
    )
    allow_autoreply: bool = Field(default=False, sa_column_kwargs={"server_default": text("false")})
    source_document_id: UUID | None = Field(default=None, sa_type=Uuid)
    version: int = Field(default=1, sa_column_kwargs={"server_default": text("1")})
    is_active: bool = Field(default=True, sa_column_kwargs={"server_default": text("true")})


class AiKnowledgeItemCreate(SQLModel):
    """Fields accepted when creating a AiKnowledgeItem."""

    property_id: UUID
    kind: AiKnowledgeItemKind
    title: str
    body: str
    locale: str = "id-ID"
    allow_autoreply: bool = False
    source_document_id: UUID | None = None
    is_active: bool = True


class AiKnowledgeItemUpdate(SQLModel):
    """Fields accepted when patching a AiKnowledgeItem (all optional)."""

    property_id: UUID | None = None
    kind: AiKnowledgeItemKind | None = None
    title: str | None = None
    body: str | None = None
    locale: str | None = None
    allow_autoreply: bool | None = None
    source_document_id: UUID | None = None
    is_active: bool | None = None


class AiKnowledgeItemRead(SQLModel):
    """Fields returned when reading a AiKnowledgeItem."""

    id: UUID
    tenant_id: UUID
    property_id: UUID
    kind: str
    title: str
    body: str
    locale: str
    allow_autoreply: bool
    source_document_id: UUID | None
    version: int
    is_active: bool
    created_at: dt.datetime
    updated_at: dt.datetime
    created_by: str | None
    updated_by: str | None
