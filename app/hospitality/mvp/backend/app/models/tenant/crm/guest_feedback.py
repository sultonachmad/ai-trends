"""GuestFeedback entity — table ``guestfeedback``.

Tenant database, L. CRM, messaging & reputation.

Complaints and feedback cases.

Mirrors .ttest/contexts/schema-tenant.sql; the Alembic migration creates the table.
"""

import datetime as dt
from decimal import Decimal
from typing import Literal
from uuid import UUID

from sqlalchemy import CheckConstraint, ForeignKeyConstraint, Text, UniqueConstraint, Uuid, text
from sqlmodel import Field, SQLModel

from app.crud.base_model import MIGRATION_ONLY, TenantEntity, utc_datetime_field

GuestFeedbackSource = Literal[
    "front_desk",
    "message",
    "survey",
    "review",
    "phone",
    "other",
]
GuestFeedbackSeverity = Literal[
    "low",
    "medium",
    "high",
    "critical",
]
GuestFeedbackStatus = Literal[
    "open",
    "in_progress",
    "resolved",
    "closed",
]


class GuestFeedback(TenantEntity, table=True):
    """Complaints and feedback cases."""

    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="guestfeedback_tenant_id_id_key"),
        ForeignKeyConstraint(
            ["tenant_id", "property_id"],
            ["property.tenant_id", "property.id"],
            name="guestfeedback_tenant_id_property_id_fkey",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "reservation_id"],
            ["reservation.tenant_id", "reservation.id"],
            name="guestfeedback_tenant_id_reservation_id_fkey",
            ondelete="SET NULL (reservation_id)",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "guest_id"],
            ["guest.tenant_id", "guest.id"],
            name="guestfeedback_tenant_id_guest_id_fkey",
            ondelete="SET NULL (guest_id)",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "unit_id"],
            ["unit.tenant_id", "unit.id"],
            name="guestfeedback_tenant_id_unit_id_fkey",
            ondelete="SET NULL (unit_id)",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "owner_staff_id"],
            ["staffmember.tenant_id", "staffmember.id"],
            name="guestfeedback_tenant_id_owner_staff_id_fkey",
            ondelete="SET NULL (owner_staff_id)",
        ),
        CheckConstraint(
            ("source IN ('front_desk', 'message', 'survey', 'review', 'phone', 'other')"),
            name="guestfeedback_source_check",
        ),
        CheckConstraint(
            "severity IN ('low', 'medium', 'high', 'critical')", name="guestfeedback_severity_check"
        ),
        CheckConstraint(
            "status IN ('open', 'in_progress', 'resolved', 'closed')",
            name="guestfeedback_status_check",
        ),
        MIGRATION_ONLY,
    )

    property_id: UUID = Field(sa_type=Uuid)
    reservation_id: UUID | None = Field(default=None, sa_type=Uuid)
    guest_id: UUID | None = Field(default=None, sa_type=Uuid)
    unit_id: UUID | None = Field(default=None, sa_type=Uuid)
    source: str = Field(sa_type=Text)
    category: str = Field(sa_type=Text)
    severity: str = Field(
        default="medium", sa_type=Text, sa_column_kwargs={"server_default": text("'medium'::text")}
    )
    description: str = Field(sa_type=Text)
    status: str = Field(
        default="open", sa_type=Text, sa_column_kwargs={"server_default": text("'open'::text")}
    )
    owner_staff_id: UUID | None = Field(default=None, sa_type=Uuid)
    resolution: str | None = Field(default=None, sa_type=Text)
    compensation_amount: Decimal | None = Field(default=None, max_digits=18, decimal_places=2)
    resolved_at: dt.datetime | None = utc_datetime_field(nullable=True)  # type: ignore[assignment]


class GuestFeedbackCreate(SQLModel):
    """Fields accepted when creating a GuestFeedback."""

    property_id: UUID
    reservation_id: UUID | None = None
    guest_id: UUID | None = None
    unit_id: UUID | None = None
    source: GuestFeedbackSource
    category: str
    severity: GuestFeedbackSeverity = "medium"
    description: str
    status: GuestFeedbackStatus = "open"
    owner_staff_id: UUID | None = None
    resolution: str | None = None
    compensation_amount: Decimal | None = Field(default=None, max_digits=18, decimal_places=2)
    resolved_at: dt.datetime | None = None


class GuestFeedbackUpdate(SQLModel):
    """Fields accepted when patching a GuestFeedback (all optional)."""

    property_id: UUID | None = None
    reservation_id: UUID | None = None
    guest_id: UUID | None = None
    unit_id: UUID | None = None
    source: GuestFeedbackSource | None = None
    category: str | None = None
    severity: GuestFeedbackSeverity | None = None
    description: str | None = None
    status: GuestFeedbackStatus | None = None
    owner_staff_id: UUID | None = None
    resolution: str | None = None
    compensation_amount: Decimal | None = Field(default=None, max_digits=18, decimal_places=2)
    resolved_at: dt.datetime | None = None


class GuestFeedbackRead(SQLModel):
    """Fields returned when reading a GuestFeedback."""

    id: UUID
    tenant_id: UUID
    property_id: UUID
    reservation_id: UUID | None
    guest_id: UUID | None
    unit_id: UUID | None
    source: str
    category: str
    severity: str
    description: str
    status: str
    owner_staff_id: UUID | None
    resolution: str | None
    compensation_amount: Decimal | None
    resolved_at: dt.datetime | None
    created_at: dt.datetime
    updated_at: dt.datetime
    created_by: str | None
    updated_by: str | None
