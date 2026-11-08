"""DataSubjectRequest entity — table ``datasubjectrequest``.

Tenant database, P. Compliance.

PDP/GDPR requests.

Mirrors .ttest/contexts/schema-tenant.sql; the Alembic migration creates the table.
"""

import datetime as dt
from typing import Literal
from uuid import UUID

from sqlalchemy import CheckConstraint, ForeignKeyConstraint, Text, UniqueConstraint, Uuid, text
from sqlmodel import Field, SQLModel

from app.crud.base_model import MIGRATION_ONLY, TenantEntity, utc_datetime_field

DataSubjectRequestKind = Literal[
    "access",
    "export",
    "rectify",
    "erase",
    "restrict",
    "object",
]
DataSubjectRequestStatus = Literal[
    "received",
    "verifying",
    "in_progress",
    "completed",
    "rejected",
]


class DataSubjectRequest(TenantEntity, table=True):
    """PDP/GDPR requests."""

    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="datasubjectrequest_tenant_id_id_key"),
        ForeignKeyConstraint(
            ["tenant_id", "guest_id"],
            ["guest.tenant_id", "guest.id"],
            name="datasubjectrequest_tenant_id_guest_id_fkey",
            ondelete="SET NULL (guest_id)",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "export_document_id"],
            ["document.tenant_id", "document.id"],
            name="datasubjectrequest_tenant_id_export_document_id_fkey",
            ondelete="SET NULL (export_document_id)",
        ),
        CheckConstraint(
            "kind IN ('access', 'export', 'rectify', 'erase', 'restrict', 'object')",
            name="datasubjectrequest_kind_check",
        ),
        CheckConstraint(
            ("status IN ('received', 'verifying', 'in_progress', 'completed', 'rejected')"),
            name="datasubjectrequest_status_check",
        ),
        MIGRATION_ONLY,
    )

    guest_id: UUID | None = Field(default=None, sa_type=Uuid)
    requester_email: str | None = Field(default=None, sa_type=Text)
    kind: str = Field(sa_type=Text)
    status: str = Field(
        default="received",
        sa_type=Text,
        sa_column_kwargs={"server_default": text("'received'::text")},
    )
    received_at: dt.datetime = utc_datetime_field(
        nullable=False, default_now=True, server_default_now=True
    )  # type: ignore[assignment]
    due_at: dt.datetime | None = utc_datetime_field(nullable=True)  # type: ignore[assignment]
    completed_at: dt.datetime | None = utc_datetime_field(nullable=True)  # type: ignore[assignment]
    outcome: str | None = Field(
        default=None, sa_type=Text, description="incl. what was retained for legal reasons"
    )
    export_document_id: UUID | None = Field(default=None, sa_type=Uuid)


class DataSubjectRequestCreate(SQLModel):
    """Fields accepted when creating a DataSubjectRequest."""

    guest_id: UUID | None = None
    requester_email: str | None = None
    kind: DataSubjectRequestKind
    status: DataSubjectRequestStatus = "received"
    received_at: dt.datetime = Field(default_factory=lambda: dt.datetime.now(dt.UTC))
    due_at: dt.datetime | None = None
    completed_at: dt.datetime | None = None
    outcome: str | None = None
    export_document_id: UUID | None = None


class DataSubjectRequestUpdate(SQLModel):
    """Fields accepted when patching a DataSubjectRequest (all optional)."""

    guest_id: UUID | None = None
    requester_email: str | None = None
    kind: DataSubjectRequestKind | None = None
    status: DataSubjectRequestStatus | None = None
    received_at: dt.datetime | None = None
    due_at: dt.datetime | None = None
    completed_at: dt.datetime | None = None
    outcome: str | None = None
    export_document_id: UUID | None = None


class DataSubjectRequestRead(SQLModel):
    """Fields returned when reading a DataSubjectRequest."""

    id: UUID
    tenant_id: UUID
    guest_id: UUID | None
    requester_email: str | None
    kind: str
    status: str
    received_at: dt.datetime
    due_at: dt.datetime | None
    completed_at: dt.datetime | None
    outcome: str | None
    export_document_id: UUID | None
    created_at: dt.datetime
    updated_at: dt.datetime
    created_by: str | None
    updated_by: str | None
