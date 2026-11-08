"""Owner entity — table ``owner``.

Tenant database, N. Owners.

Owners, shares, agreements.

Mirrors .ttest/contexts/schema-tenant.sql; the Alembic migration creates the table.
"""

import datetime as dt
from typing import Any, Literal
from uuid import UUID

from sqlalchemy import CHAR, CheckConstraint, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel

from app.crud.base_model import MIGRATION_ONLY, TenantEntity

OwnerKind = Literal[
    "individual",
    "company",
]
OwnerStatus = Literal[
    "active",
    "inactive",
]


class Owner(TenantEntity, table=True):
    """Owners, shares, agreements."""

    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="owner_tenant_id_id_key"),
        CheckConstraint("kind IN ('individual', 'company')", name="owner_kind_check"),
        CheckConstraint("status IN ('active', 'inactive')", name="owner_status_check"),
        MIGRATION_ONLY,
    )

    kind: str = Field(
        default="individual",
        sa_type=Text,
        sa_column_kwargs={"server_default": text("'individual'::text")},
    )
    name: str = Field(sa_type=Text)
    email: str | None = Field(default=None, sa_type=Text)
    phone: str | None = Field(default=None, sa_type=Text)
    nationality: str | None = Field(default=None, sa_type=CHAR(2))
    tax_id: str | None = Field(default=None, sa_type=Text)
    reporting_currency: str = Field(
        default="IDR", sa_type=CHAR(3), sa_column_kwargs={"server_default": text("'IDR'::bpchar")}
    )
    payout_details: dict[str, Any] = Field(
        default_factory=dict,
        sa_type=JSONB,
        sa_column_kwargs={"server_default": text("'{}'::jsonb")},
        description="masked; full numbers in secret store",
    )
    portal_user_id: int | None = Field(default=None, description='control-plane "user".id')
    status: str = Field(
        default="active", sa_type=Text, sa_column_kwargs={"server_default": text("'active'::text")}
    )


class OwnerCreate(SQLModel):
    """Fields accepted when creating a Owner."""

    kind: OwnerKind = "individual"
    name: str
    email: str | None = None
    phone: str | None = None
    nationality: str | None = Field(default=None, min_length=2, max_length=2)
    tax_id: str | None = None
    reporting_currency: str = Field(default="IDR", min_length=3, max_length=3)
    payout_details: dict[str, Any] = Field(default_factory=dict)
    portal_user_id: int | None = None
    status: OwnerStatus = "active"


class OwnerUpdate(SQLModel):
    """Fields accepted when patching a Owner (all optional)."""

    kind: OwnerKind | None = None
    name: str | None = None
    email: str | None = None
    phone: str | None = None
    nationality: str | None = Field(default=None, min_length=2, max_length=2)
    tax_id: str | None = None
    reporting_currency: str | None = Field(default=None, min_length=3, max_length=3)
    payout_details: dict[str, Any] | None = None
    portal_user_id: int | None = None
    status: OwnerStatus | None = None


class OwnerRead(SQLModel):
    """Fields returned when reading a Owner."""

    id: UUID
    tenant_id: UUID
    kind: str
    name: str
    email: str | None
    phone: str | None
    nationality: str | None
    tax_id: str | None
    reporting_currency: str
    payout_details: dict[str, Any]
    portal_user_id: int | None
    status: str
    created_at: dt.datetime
    updated_at: dt.datetime
    created_by: str | None
    updated_by: str | None
