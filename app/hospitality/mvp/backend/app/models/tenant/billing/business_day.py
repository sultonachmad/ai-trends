"""BusinessDay entity — table ``businessday``.

Tenant database, H. Folios, postings, invoices, end-of-day.

Night audit / end-of-day per property per business date.

Mirrors .ttest/contexts/schema-tenant.sql; the Alembic migration creates the table.
"""

import datetime as dt
from typing import Any, Literal
from uuid import UUID

from sqlalchemy import CheckConstraint, ForeignKeyConstraint, Text, UniqueConstraint, Uuid, text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlmodel import Field, SQLModel

from app.crud.base_model import MIGRATION_ONLY, TenantRecord, utc_datetime_field

BusinessDayStatus = Literal[
    "open",
    "closing",
    "closed",
    "failed",
]
BusinessDayRunMode = Literal[
    "auto",
    "attended",
]


class BusinessDay(TenantRecord, table=True):
    """Night audit / end-of-day per property per business date."""

    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="businessday_tenant_id_id_key"),
        UniqueConstraint(
            "tenant_id",
            "property_id",
            "business_date",
            name="businessday_tenant_id_property_id_business_date_key",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "property_id"],
            ["property.tenant_id", "property.id"],
            name="businessday_tenant_id_property_id_fkey",
        ),
        CheckConstraint(
            "status IN ('open', 'closing', 'closed', 'failed')", name="businessday_status_check"
        ),
        CheckConstraint("run_mode IN ('auto', 'attended')", name="businessday_run_mode_check"),
        MIGRATION_ONLY,
    )

    property_id: UUID = Field(sa_type=Uuid)
    business_date: dt.date = Field()
    status: str = Field(
        default="open", sa_type=Text, sa_column_kwargs={"server_default": text("'open'::text")}
    )
    opened_at: dt.datetime = utc_datetime_field(
        nullable=False, default_now=True, server_default_now=True
    )  # type: ignore[assignment]
    closed_at: dt.datetime | None = utc_datetime_field(nullable=True)  # type: ignore[assignment]
    closed_by: str | None = Field(default=None, sa_type=Text)
    run_mode: str | None = Field(default=None, sa_type=Text)
    checklist: dict[str, Any] = Field(
        default_factory=dict,
        sa_type=JSONB,
        sa_column_kwargs={"server_default": text("'{}'::jsonb")},
        description="pre-check results",
    )
    stats: dict[str, Any] = Field(
        default_factory=dict,
        sa_type=JSONB,
        sa_column_kwargs={"server_default": text("'{}'::jsonb")},
        description="occupancy, ADR, RevPAR, revenue by dept (snapshot)",
    )
    report_document_ids: list[UUID] = Field(
        default_factory=list,
        sa_type=ARRAY(Uuid),
        sa_column_kwargs={"server_default": text("'{}'::uuid[]")},
    )
    error: str | None = Field(default=None, sa_type=Text)


class BusinessDayCreate(SQLModel):
    """Fields accepted when creating a BusinessDay."""

    property_id: UUID
    business_date: dt.date
    status: BusinessDayStatus = "open"
    opened_at: dt.datetime = Field(default_factory=lambda: dt.datetime.now(dt.UTC))
    closed_at: dt.datetime | None = None
    closed_by: str | None = None
    run_mode: BusinessDayRunMode | None = None
    checklist: dict[str, Any] = Field(default_factory=dict)
    stats: dict[str, Any] = Field(default_factory=dict)
    report_document_ids: list[UUID] = Field(default_factory=list)
    error: str | None = None


class BusinessDayUpdate(SQLModel):
    """Fields accepted when patching a BusinessDay (all optional)."""

    property_id: UUID | None = None
    business_date: dt.date | None = None
    status: BusinessDayStatus | None = None
    opened_at: dt.datetime | None = None
    closed_at: dt.datetime | None = None
    closed_by: str | None = None
    run_mode: BusinessDayRunMode | None = None
    checklist: dict[str, Any] | None = None
    stats: dict[str, Any] | None = None
    report_document_ids: list[UUID] | None = None
    error: str | None = None


class BusinessDayRead(SQLModel):
    """Fields returned when reading a BusinessDay."""

    id: UUID
    tenant_id: UUID
    property_id: UUID
    business_date: dt.date
    status: str
    opened_at: dt.datetime
    closed_at: dt.datetime | None
    closed_by: str | None
    run_mode: str | None
    checklist: dict[str, Any]
    stats: dict[str, Any]
    report_document_ids: list[UUID]
    error: str | None
