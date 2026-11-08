"""GuestDocument entity — table ``guestdocument``.

Tenant database, F. Accounts & guests.

Identity documents (KTP, passport, KITAS …). Number stored encrypted + hash.

Mirrors .ttest/contexts/schema-tenant.sql; the Alembic migration creates the table.
"""

import datetime as dt
from typing import Literal
from uuid import UUID

from sqlalchemy import (
    CHAR,
    CheckConstraint,
    ForeignKeyConstraint,
    Index,
    LargeBinary,
    Text,
    UniqueConstraint,
    Uuid,
    text,
)
from sqlmodel import Field, SQLModel

from app.crud.base_model import MIGRATION_ONLY, TenantEntity, utc_datetime_field

GuestDocumentDocType = Literal[
    "ktp",
    "passport",
    "kitas",
    "kitap",
    "sim",
    "visa",
    "marriage_certificate",
    "student_id",
    "other",
]


class GuestDocument(TenantEntity, table=True):
    """Identity documents (KTP, passport, KITAS …). Number stored encrypted + hash."""

    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="guestdocument_tenant_id_id_key"),
        ForeignKeyConstraint(
            ["tenant_id", "guest_id"],
            ["guest.tenant_id", "guest.id"],
            name="guestdocument_tenant_id_guest_id_fkey",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "scan_document_id"],
            ["document.tenant_id", "document.id"],
            name="guestdocument_tenant_id_scan_document_id_fkey",
            ondelete="SET NULL (scan_document_id)",
        ),
        CheckConstraint(
            (
                "doc_type IN ('ktp', 'passport', 'kitas', 'kitap', 'sim', 'visa', "
                "'marriage_certificate', 'student_id', 'other')"
            ),
            name="guestdocument_doc_type_check",
        ),
        Index("ix_guestdocument_hash", "tenant_id", "doc_type", "doc_number_hash"),
        MIGRATION_ONLY,
    )

    guest_id: UUID = Field(sa_type=Uuid)
    doc_type: str = Field(sa_type=Text)
    doc_number_encrypted: bytes | None = Field(
        default=None, sa_type=LargeBinary, description="application-level encryption (KMS)"
    )
    doc_number_hash: str | None = Field(
        default=None, sa_type=Text, description="HMAC for exact-match lookup / dedupe"
    )
    doc_number_last4: str | None = Field(default=None, sa_type=Text)
    issuing_country: str | None = Field(default=None, sa_type=CHAR(2))
    issued_on: dt.date | None = Field(default=None)
    expires_on: dt.date | None = Field(default=None)
    visa_type: str | None = Field(default=None, sa_type=Text, description="'voa','b211','kitas', …")
    entry_stamp_date: dt.date | None = Field(default=None)
    scan_document_id: UUID | None = Field(default=None, sa_type=Uuid)
    verified_at: dt.datetime | None = utc_datetime_field(nullable=True)  # type: ignore[assignment]
    verified_by: str | None = Field(default=None, sa_type=Text)
    extracted_by_ai: bool = Field(default=False, sa_column_kwargs={"server_default": text("false")})
    retention_until: dt.date | None = Field(default=None)


class GuestDocumentCreate(SQLModel):
    """Fields accepted when creating a GuestDocument."""

    guest_id: UUID
    doc_type: GuestDocumentDocType
    doc_number_last4: str | None = None
    issuing_country: str | None = Field(default=None, min_length=2, max_length=2)
    issued_on: dt.date | None = None
    expires_on: dt.date | None = None
    visa_type: str | None = None
    entry_stamp_date: dt.date | None = None
    scan_document_id: UUID | None = None
    verified_at: dt.datetime | None = None
    verified_by: str | None = None
    extracted_by_ai: bool = False
    retention_until: dt.date | None = None


class GuestDocumentUpdate(SQLModel):
    """Fields accepted when patching a GuestDocument (all optional)."""

    guest_id: UUID | None = None
    doc_type: GuestDocumentDocType | None = None
    doc_number_last4: str | None = None
    issuing_country: str | None = Field(default=None, min_length=2, max_length=2)
    issued_on: dt.date | None = None
    expires_on: dt.date | None = None
    visa_type: str | None = None
    entry_stamp_date: dt.date | None = None
    scan_document_id: UUID | None = None
    verified_at: dt.datetime | None = None
    verified_by: str | None = None
    extracted_by_ai: bool | None = None
    retention_until: dt.date | None = None


class GuestDocumentRead(SQLModel):
    """
    Fields returned when reading a GuestDocument (never returns: doc_number_encrypted,
    doc_number_hash).
    """

    id: UUID
    tenant_id: UUID
    guest_id: UUID
    doc_type: str
    doc_number_last4: str | None
    issuing_country: str | None
    issued_on: dt.date | None
    expires_on: dt.date | None
    visa_type: str | None
    entry_stamp_date: dt.date | None
    scan_document_id: UUID | None
    verified_at: dt.datetime | None
    verified_by: str | None
    extracted_by_ai: bool
    retention_until: dt.date | None
    created_at: dt.datetime
    updated_at: dt.datetime
    created_by: str | None
    updated_by: str | None
