"""Document entity — table ``document``.

Tenant database, A. Organisation & property.

File metadata (scans, contracts, photos, PDFs). Bytes live in object storage.

Mirrors .ttest/contexts/schema-tenant.sql; the Alembic migration creates the table.
"""

import datetime as dt
from typing import Literal
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    ForeignKeyConstraint,
    Text,
    UniqueConstraint,
    Uuid,
    text,
)
from sqlmodel import Field, SQLModel

from app.crud.base_model import MIGRATION_ONLY, TenantEntity

DocumentKind = Literal[
    "identity_scan",
    "registration_card",
    "contract",
    "invoice_pdf",
    "report",
    "photo",
    "transfer_proof",
    "manual",
    "receipt",
    "owner_statement",
    "other",
]
DocumentClassification = Literal[
    "public",
    "internal",
    "personal",
    "identity",
    "financial",
]


class Document(TenantEntity, table=True):
    """File metadata (scans, contracts, photos, PDFs). Bytes live in object storage."""

    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="document_tenant_id_id_key"),
        ForeignKeyConstraint(
            ["tenant_id", "property_id"],
            ["property.tenant_id", "property.id"],
            name="document_tenant_id_property_id_fkey",
            ondelete="SET NULL (property_id)",
        ),
        CheckConstraint(
            (
                "kind IN ('identity_scan', 'registration_card', 'contract', "
                "'invoice_pdf', 'report', 'photo', 'transfer_proof', 'manual', "
                "'receipt', 'owner_statement', 'other')"
            ),
            name="document_kind_check",
        ),
        CheckConstraint(
            ("classification IN ('public', 'internal', 'personal', 'identity', 'financial')"),
            name="document_classification_check",
        ),
        CheckConstraint("(size_bytes >= 0)", name="document_size_bytes_check"),
        MIGRATION_ONLY,
    )

    property_id: UUID | None = Field(default=None, sa_type=Uuid)
    kind: str = Field(sa_type=Text)
    classification: str = Field(
        default="internal",
        sa_type=Text,
        sa_column_kwargs={"server_default": text("'internal'::text")},
    )
    storage_key: str = Field(
        sa_type=Text, description="object-storage key; never exposed to clients"
    )
    original_name: str | None = Field(default=None, sa_type=Text)
    content_type: str = Field(sa_type=Text)
    size_bytes: int = Field(sa_type=BigInteger)
    sha256: str | None = Field(default=None, sa_type=Text)
    retention_until: dt.date | None = Field(default=None)
    uploaded_by: str | None = Field(default=None, sa_type=Text)


class DocumentCreate(SQLModel):
    """Fields accepted when creating a Document."""

    property_id: UUID | None = None
    kind: DocumentKind
    classification: DocumentClassification = "internal"
    original_name: str | None = None
    content_type: str
    size_bytes: int = Field(ge=0)
    sha256: str | None = None
    retention_until: dt.date | None = None
    uploaded_by: str | None = None


class DocumentUpdate(SQLModel):
    """Fields accepted when patching a Document (all optional)."""

    property_id: UUID | None = None
    kind: DocumentKind | None = None
    classification: DocumentClassification | None = None
    original_name: str | None = None
    content_type: str | None = None
    size_bytes: int | None = Field(default=None, ge=0)
    sha256: str | None = None
    retention_until: dt.date | None = None
    uploaded_by: str | None = None


class DocumentRead(SQLModel):
    """Fields returned when reading a Document (never returns: storage_key)."""

    id: UUID
    tenant_id: UUID
    property_id: UUID | None
    kind: str
    classification: str
    original_name: str | None
    content_type: str
    size_bytes: int
    sha256: str | None
    retention_until: dt.date | None
    uploaded_by: str | None
    created_at: dt.datetime
    updated_at: dt.datetime
    created_by: str | None
    updated_by: str | None
