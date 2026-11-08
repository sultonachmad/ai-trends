"""Restriction entity — table ``restriction``.

Tenant database, E. Rates, policies, products & restrictions.

Restrictions. NULL scope column = applies to all (all unit types / rate plans / channels).

Mirrors .ttest/contexts/schema-tenant.sql; the Alembic migration creates the table.
"""

import datetime as dt
from typing import Literal
from uuid import UUID

from sqlalchemy import CheckConstraint, ForeignKeyConstraint, Text, UniqueConstraint, Uuid, text
from sqlmodel import Field, SQLModel

from app.crud.base_model import MIGRATION_ONLY, TenantRecord, utc_datetime_field

RestrictionSource = Literal[
    "manual",
    "bulk",
    "rms",
    "rule",
    "import",
]


class Restriction(TenantRecord, table=True):
    """
    Restrictions. NULL scope column = applies to all (all unit types / rate plans / channels).
    """

    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="restriction_tenant_id_id_key"),
        UniqueConstraint(
            "tenant_id",
            "property_id",
            "stay_date",
            "unit_type_id",
            "rate_plan_id",
            "channel_id",
            name="restriction_tenant_id_property_id_stay_date_unit_type_id_ra_key",
            postgresql_nulls_not_distinct=True,
        ),
        ForeignKeyConstraint(
            ["tenant_id", "property_id"],
            ["property.tenant_id", "property.id"],
            name="restriction_tenant_id_property_id_fkey",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "unit_type_id"],
            ["unittype.tenant_id", "unittype.id"],
            name="restriction_tenant_id_unit_type_id_fkey",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "rate_plan_id"],
            ["rateplan.tenant_id", "rateplan.id"],
            name="restriction_tenant_id_rate_plan_id_fkey",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "channel_id"],
            ["channel.tenant_id", "channel.id"],
            name="restriction_tenant_id_channel_id_fkey",
            ondelete="CASCADE",
        ),
        CheckConstraint("(min_stay_arrival > 0)", name="restriction_min_stay_arrival_check"),
        CheckConstraint("(min_stay_through > 0)", name="restriction_min_stay_through_check"),
        CheckConstraint("(max_stay > 0)", name="restriction_max_stay_check"),
        CheckConstraint("(min_advance_days >= 0)", name="restriction_min_advance_days_check"),
        CheckConstraint("(max_advance_days >= 0)", name="restriction_max_advance_days_check"),
        CheckConstraint(
            "source IN ('manual', 'bulk', 'rms', 'rule', 'import')", name="restriction_source_check"
        ),
        MIGRATION_ONLY,
    )

    property_id: UUID = Field(sa_type=Uuid)
    stay_date: dt.date = Field()
    unit_type_id: UUID | None = Field(default=None, sa_type=Uuid)
    rate_plan_id: UUID | None = Field(default=None, sa_type=Uuid)
    channel_id: UUID | None = Field(default=None, sa_type=Uuid)
    stop_sell: bool = Field(default=False, sa_column_kwargs={"server_default": text("false")})
    closed_to_arrival: bool = Field(
        default=False, sa_column_kwargs={"server_default": text("false")}
    )
    closed_to_departure: bool = Field(
        default=False, sa_column_kwargs={"server_default": text("false")}
    )
    min_stay_arrival: int | None = Field(default=None)
    min_stay_through: int | None = Field(default=None)
    max_stay: int | None = Field(default=None)
    min_advance_days: int | None = Field(default=None)
    max_advance_days: int | None = Field(default=None)
    source: str = Field(
        default="manual", sa_type=Text, sa_column_kwargs={"server_default": text("'manual'::text")}
    )
    updated_at: dt.datetime = utc_datetime_field(
        nullable=False, default_now=True, onupdate_now=True, server_default_now=True
    )  # type: ignore[assignment]
    updated_by: str | None = Field(default=None, sa_type=Text)


class RestrictionCreate(SQLModel):
    """Fields accepted when creating a Restriction."""

    property_id: UUID
    stay_date: dt.date
    unit_type_id: UUID | None = None
    rate_plan_id: UUID | None = None
    channel_id: UUID | None = None
    stop_sell: bool = False
    closed_to_arrival: bool = False
    closed_to_departure: bool = False
    min_stay_arrival: int | None = Field(default=None, gt=0)
    min_stay_through: int | None = Field(default=None, gt=0)
    max_stay: int | None = Field(default=None, gt=0)
    min_advance_days: int | None = Field(default=None, ge=0)
    max_advance_days: int | None = Field(default=None, ge=0)
    source: RestrictionSource = "manual"


class RestrictionUpdate(SQLModel):
    """Fields accepted when patching a Restriction (all optional)."""

    property_id: UUID | None = None
    stay_date: dt.date | None = None
    unit_type_id: UUID | None = None
    rate_plan_id: UUID | None = None
    channel_id: UUID | None = None
    stop_sell: bool | None = None
    closed_to_arrival: bool | None = None
    closed_to_departure: bool | None = None
    min_stay_arrival: int | None = Field(default=None, gt=0)
    min_stay_through: int | None = Field(default=None, gt=0)
    max_stay: int | None = Field(default=None, gt=0)
    min_advance_days: int | None = Field(default=None, ge=0)
    max_advance_days: int | None = Field(default=None, ge=0)
    source: RestrictionSource | None = None


class RestrictionRead(SQLModel):
    """Fields returned when reading a Restriction."""

    id: UUID
    tenant_id: UUID
    property_id: UUID
    stay_date: dt.date
    unit_type_id: UUID | None
    rate_plan_id: UUID | None
    channel_id: UUID | None
    stop_sell: bool
    closed_to_arrival: bool
    closed_to_departure: bool
    min_stay_arrival: int | None
    min_stay_through: int | None
    max_stay: int | None
    min_advance_days: int | None
    max_advance_days: int | None
    source: str
    updated_at: dt.datetime
    updated_by: str | None
