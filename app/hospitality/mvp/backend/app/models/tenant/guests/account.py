"""Account entity — table ``account``.

Tenant database, F. Accounts & guests.

Company / agent / OTA / government accounts (AR).

Mirrors .ttest/contexts/schema-tenant.sql; the Alembic migration creates the table.
"""

import datetime as dt
from decimal import Decimal
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

from app.crud.base_model import MIGRATION_ONLY, TenantEntity

AccountKind = Literal[
    "company",
    "travel_agent",
    "ota",
    "wholesaler",
    "government",
    "group_organizer",
    "other",
]
AccountStatus = Literal[
    "active",
    "on_hold",
    "closed",
]


class Account(TenantEntity, table=True):
    """Company / agent / OTA / government accounts (AR)."""

    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="account_tenant_id_id_key"),
        ForeignKeyConstraint(
            ["tenant_id", "channel_id"],
            ["channel.tenant_id", "channel.id"],
            name="account_tenant_id_channel_id_fkey",
            ondelete="SET NULL (channel_id)",
        ),
        CheckConstraint(
            (
                "kind IN ('company', 'travel_agent', 'ota', 'wholesaler', 'government', "
                "'group_organizer', 'other')"
            ),
            name="account_kind_check",
        ),
        CheckConstraint("status IN ('active', 'on_hold', 'closed')", name="account_status_check"),
        Index(
            "ix_account_name",
            "name",
            postgresql_using="gin",
            postgresql_ops={"name": "gin_trgm_ops"},
        ),
        MIGRATION_ONLY,
    )

    kind: str = Field(sa_type=Text)
    name: str = Field(sa_type=Text)
    tax_id: str | None = Field(default=None, sa_type=Text)
    email: str | None = Field(default=None, sa_type=Text)
    phone: str | None = Field(default=None, sa_type=Text)
    billing_address: dict[str, Any] = Field(
        default_factory=dict,
        sa_type=JSONB,
        sa_column_kwargs={"server_default": text("'{}'::jsonb")},
    )
    is_ar_enabled: bool = Field(
        default=False,
        sa_column_kwargs={"server_default": text("false")},
        description="direct bill / city ledger",
    )
    credit_limit: Decimal | None = Field(default=None, max_digits=18, decimal_places=2)
    payment_terms_days: int | None = Field(default=None)
    commission_pct: Decimal | None = Field(default=None, max_digits=5, decimal_places=2)
    channel_id: UUID | None = Field(default=None, sa_type=Uuid, description="for kind = 'ota'")
    status: str = Field(
        default="active", sa_type=Text, sa_column_kwargs={"server_default": text("'active'::text")}
    )
    notes: str | None = Field(default=None, sa_type=Text)


class AccountCreate(SQLModel):
    """Fields accepted when creating a Account."""

    kind: AccountKind
    name: str
    tax_id: str | None = None
    email: str | None = None
    phone: str | None = None
    billing_address: dict[str, Any] = Field(default_factory=dict)
    is_ar_enabled: bool = False
    credit_limit: Decimal | None = Field(default=None, max_digits=18, decimal_places=2)
    payment_terms_days: int | None = None
    commission_pct: Decimal | None = Field(default=None, max_digits=5, decimal_places=2)
    channel_id: UUID | None = None
    status: AccountStatus = "active"
    notes: str | None = None


class AccountUpdate(SQLModel):
    """Fields accepted when patching a Account (all optional)."""

    kind: AccountKind | None = None
    name: str | None = None
    tax_id: str | None = None
    email: str | None = None
    phone: str | None = None
    billing_address: dict[str, Any] | None = None
    is_ar_enabled: bool | None = None
    credit_limit: Decimal | None = Field(default=None, max_digits=18, decimal_places=2)
    payment_terms_days: int | None = None
    commission_pct: Decimal | None = Field(default=None, max_digits=5, decimal_places=2)
    channel_id: UUID | None = None
    status: AccountStatus | None = None
    notes: str | None = None


class AccountRead(SQLModel):
    """Fields returned when reading a Account."""

    id: UUID
    tenant_id: UUID
    kind: str
    name: str
    tax_id: str | None
    email: str | None
    phone: str | None
    billing_address: dict[str, Any]
    is_ar_enabled: bool
    credit_limit: Decimal | None
    payment_terms_days: int | None
    commission_pct: Decimal | None
    channel_id: UUID | None
    status: str
    notes: str | None
    created_at: dt.datetime
    updated_at: dt.datetime
    created_by: str | None
    updated_by: str | None
