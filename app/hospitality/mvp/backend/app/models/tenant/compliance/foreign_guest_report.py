"""ForeignGuestReport entity — table ``foreignguestreport``.

Tenant database, P. Compliance.

Foreign-guest report to immigration (APOA) per occupant.

Mirrors .ttest/contexts/schema-tenant.sql; the Alembic migration creates the table.
"""

import datetime as dt
from typing import Any, Literal
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    ForeignKeyConstraint,
    Index,
    Text,
    UniqueConstraint,
    Uuid,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel

from app.crud.base_model import MIGRATION_ONLY, TenantEntity, utc_datetime_field

ForeignGuestReportReportKind = Literal[
    "arrival",
    "departure",
    "amendment",
]
ForeignGuestReportMethod = Literal[
    "api",
    "assisted_export",
    "manual",
]
ForeignGuestReportStatus = Literal[
    "pending",
    "ready",
    "submitted",
    "failed",
    "not_required",
    "cancelled",
]


class ForeignGuestReport(TenantEntity, table=True):
    """Foreign-guest report to immigration (APOA) per occupant."""

    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="foreignguestreport_tenant_id_id_key"),
        UniqueConstraint(
            "tenant_id",
            "reservation_guest_id",
            "report_system",
            "report_kind",
            name="foreignguestreport_tenant_id_reservation_guest_id_report_sy_key",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "property_id"],
            ["property.tenant_id", "property.id"],
            name="foreignguestreport_tenant_id_property_id_fkey",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "reservation_guest_id"],
            ["reservationguest.tenant_id", "reservationguest.id"],
            name="foreignguestreport_tenant_id_reservation_guest_id_fkey",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "guest_id"],
            ["guest.tenant_id", "guest.id"],
            name="foreignguestreport_tenant_id_guest_id_fkey",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "guest_document_id"],
            ["guestdocument.tenant_id", "guestdocument.id"],
            name="foreignguestreport_tenant_id_guest_document_id_fkey",
            ondelete="SET NULL (guest_document_id)",
        ),
        CheckConstraint(
            "report_kind IN ('arrival', 'departure', 'amendment')",
            name="foreignguestreport_report_kind_check",
        ),
        CheckConstraint(
            "method IN ('api', 'assisted_export', 'manual')", name="foreignguestreport_method_check"
        ),
        CheckConstraint(
            ("status IN ('pending', 'ready', 'submitted', 'failed', 'not_required', 'cancelled')"),
            name="foreignguestreport_status_check",
        ),
        Index(
            "ix_foreignguestreport_due",
            "tenant_id",
            "property_id",
            "due_at",
            postgresql_where=text(
                "status = ANY (ARRAY['pending'::text, 'ready'::text, 'failed'::text])"
            ),
        ),
        MIGRATION_ONLY,
    )

    property_id: UUID = Field(sa_type=Uuid)
    reservation_guest_id: UUID = Field(sa_type=Uuid)
    guest_id: UUID = Field(sa_type=Uuid)
    guest_document_id: UUID | None = Field(default=None, sa_type=Uuid)
    report_system: str = Field(
        default="apoa", sa_type=Text, sa_column_kwargs={"server_default": text("'apoa'::text")}
    )
    report_kind: str = Field(
        default="arrival",
        sa_type=Text,
        sa_column_kwargs={"server_default": text("'arrival'::text")},
    )
    method: str = Field(
        default="assisted_export",
        sa_type=Text,
        sa_column_kwargs={"server_default": text("'assisted_export'::text")},
    )
    status: str = Field(
        default="pending",
        sa_type=Text,
        sa_column_kwargs={"server_default": text("'pending'::text")},
    )
    due_at: dt.datetime = utc_datetime_field(nullable=False, description="e.g. check-in + 24h")  # type: ignore[assignment]
    submitted_at: dt.datetime | None = utc_datetime_field(nullable=True)  # type: ignore[assignment]
    submitted_by: str | None = Field(default=None, sa_type=Text)
    external_reference: str | None = Field(default=None, sa_type=Text)
    payload: dict[str, Any] = Field(
        default_factory=dict,
        sa_type=JSONB,
        sa_column_kwargs={"server_default": text("'{}'::jsonb")},
        description="exact fields sent/exported",
    )
    error: str | None = Field(default=None, sa_type=Text)


class ForeignGuestReportCreate(SQLModel):
    """Fields accepted when creating a ForeignGuestReport."""

    property_id: UUID
    reservation_guest_id: UUID
    guest_id: UUID
    guest_document_id: UUID | None = None
    report_system: str = "apoa"
    report_kind: ForeignGuestReportReportKind = "arrival"
    method: ForeignGuestReportMethod = "assisted_export"
    status: ForeignGuestReportStatus = "pending"
    due_at: dt.datetime
    submitted_at: dt.datetime | None = None
    submitted_by: str | None = None
    external_reference: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None


class ForeignGuestReportUpdate(SQLModel):
    """Fields accepted when patching a ForeignGuestReport (all optional)."""

    property_id: UUID | None = None
    reservation_guest_id: UUID | None = None
    guest_id: UUID | None = None
    guest_document_id: UUID | None = None
    report_system: str | None = None
    report_kind: ForeignGuestReportReportKind | None = None
    method: ForeignGuestReportMethod | None = None
    status: ForeignGuestReportStatus | None = None
    due_at: dt.datetime | None = None
    submitted_at: dt.datetime | None = None
    submitted_by: str | None = None
    external_reference: str | None = None
    payload: dict[str, Any] | None = None
    error: str | None = None


class ForeignGuestReportRead(SQLModel):
    """Fields returned when reading a ForeignGuestReport."""

    id: UUID
    tenant_id: UUID
    property_id: UUID
    reservation_guest_id: UUID
    guest_id: UUID
    guest_document_id: UUID | None
    report_system: str
    report_kind: str
    method: str
    status: str
    due_at: dt.datetime
    submitted_at: dt.datetime | None
    submitted_by: str | None
    external_reference: str | None
    payload: dict[str, Any]
    error: str | None
    created_at: dt.datetime
    updated_at: dt.datetime
    created_by: str | None
    updated_by: str | None
