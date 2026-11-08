"""Tenant entity — table ``tenant``.

Control-plane database, Control plane.

Customer organisation, status, residency region, defaults.

Mirrors .ttest/contexts/schema-control-plane.sql; the Alembic migration creates the table.
"""

import datetime as dt
from typing import Any, Literal
from uuid import UUID

from sqlalchemy import CHAR, CheckConstraint, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel

from app.crud.base_model import MIGRATION_ONLY, UUIDEntity, utc_datetime_field

TenantStatus = Literal[
    "provisioning",
    "trial",
    "active",
    "past_due",
    "suspended",
    "cancelled",
    "deleted",
]
TenantIsolationTier = Literal[
    "pooled",
    "dedicated",
]


class Tenant(UUIDEntity, table=True):
    """Customer organisation, status, residency region, defaults."""

    __table_args__ = (
        UniqueConstraint("code", name="tenant_code_key"),
        CheckConstraint("(code ~ '^[a-z0-9][a-z0-9-]{1,62}$'::text)", name="tenant_code_check"),
        CheckConstraint(
            (
                "status IN ('provisioning', 'trial', 'active', 'past_due', 'suspended', "
                "'cancelled', 'deleted')"
            ),
            name="tenant_status_check",
        ),
        CheckConstraint(
            "isolation_tier IN ('pooled', 'dedicated')", name="tenant_isolation_tier_check"
        ),
        MIGRATION_ONLY,
    )

    code: str = Field(sa_type=Text)
    name: str = Field(sa_type=Text)
    legal_name: str | None = Field(default=None, sa_type=Text)
    status: str = Field(
        default="provisioning",
        sa_type=Text,
        sa_column_kwargs={"server_default": text("'provisioning'::text")},
    )
    country_code: str = Field(
        default="ID", sa_type=CHAR(2), sa_column_kwargs={"server_default": text("'ID'::bpchar")}
    )
    data_region: str = Field(
        default="ap-southeast-3",
        sa_type=Text,
        sa_column_kwargs={"server_default": text("'ap-southeast-3'::text")},
    )
    default_locale: str = Field(
        default="id-ID", sa_type=Text, sa_column_kwargs={"server_default": text("'id-ID'::text")}
    )
    default_currency: str = Field(
        default="IDR", sa_type=CHAR(3), sa_column_kwargs={"server_default": text("'IDR'::bpchar")}
    )
    default_timezone: str = Field(
        default="Asia/Jakarta",
        sa_type=Text,
        sa_column_kwargs={"server_default": text("'Asia/Jakarta'::text")},
    )
    isolation_tier: str = Field(
        default="pooled", sa_type=Text, sa_column_kwargs={"server_default": text("'pooled'::text")}
    )
    trial_ends_at: dt.datetime | None = utc_datetime_field(nullable=True)  # type: ignore[assignment]
    suspended_reason: str | None = Field(default=None, sa_type=Text)
    deleted_at: dt.datetime | None = utc_datetime_field(nullable=True)  # type: ignore[assignment]
    metadata_: dict[str, Any] = Field(
        default_factory=dict,
        sa_type=JSONB,
        sa_column_kwargs={"server_default": text("'{}'::jsonb"), "name": "metadata"},
    )


class TenantCreate(SQLModel):
    """Fields accepted when creating a Tenant."""

    code: str
    name: str
    legal_name: str | None = None
    status: TenantStatus = "provisioning"
    country_code: str = Field(default="ID", min_length=2, max_length=2)
    data_region: str = "ap-southeast-3"
    default_locale: str = "id-ID"
    default_currency: str = Field(default="IDR", min_length=3, max_length=3)
    default_timezone: str = "Asia/Jakarta"
    isolation_tier: TenantIsolationTier = "pooled"
    trial_ends_at: dt.datetime | None = None
    suspended_reason: str | None = None
    deleted_at: dt.datetime | None = None
    metadata_: dict[str, Any] = Field(default_factory=dict)


class TenantUpdate(SQLModel):
    """Fields accepted when patching a Tenant (all optional)."""

    code: str | None = None
    name: str | None = None
    legal_name: str | None = None
    status: TenantStatus | None = None
    country_code: str | None = Field(default=None, min_length=2, max_length=2)
    data_region: str | None = None
    default_locale: str | None = None
    default_currency: str | None = Field(default=None, min_length=3, max_length=3)
    default_timezone: str | None = None
    isolation_tier: TenantIsolationTier | None = None
    trial_ends_at: dt.datetime | None = None
    suspended_reason: str | None = None
    deleted_at: dt.datetime | None = None
    metadata_: dict[str, Any] | None = None


class TenantRead(SQLModel):
    """Fields returned when reading a Tenant."""

    id: UUID
    code: str
    name: str
    legal_name: str | None
    status: str
    country_code: str
    data_region: str
    default_locale: str
    default_currency: str
    default_timezone: str
    isolation_tier: str
    trial_ends_at: dt.datetime | None
    suspended_reason: str | None
    deleted_at: dt.datetime | None
    metadata_: dict[str, Any]
    created_at: dt.datetime
    updated_at: dt.datetime
    created_by: str | None
    updated_by: str | None
