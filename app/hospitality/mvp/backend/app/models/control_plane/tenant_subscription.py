"""TenantSubscription entity — table ``tenantsubscription``.

Control-plane database, Control plane.

Tenant's plan over time.

Mirrors .ttest/contexts/schema-control-plane.sql; the Alembic migration creates the table.
"""

import datetime as dt
from typing import Literal
from uuid import UUID

from sqlalchemy import CheckConstraint, ForeignKeyConstraint, Index, Text, Uuid, text
from sqlmodel import Field, SQLModel

from app.crud.base_model import MIGRATION_ONLY, UUIDEntity

TenantSubscriptionStatus = Literal[
    "trialing",
    "active",
    "past_due",
    "paused",
    "cancelled",
    "ended",
]


class TenantSubscription(UUIDEntity, table=True):
    """Tenant's plan over time."""

    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id"],
            ["tenant.id"],
            name="tenantsubscription_tenant_id_fkey",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(["plan_id"], ["plan.id"], name="tenantsubscription_plan_id_fkey"),
        CheckConstraint(
            ("status IN ('trialing', 'active', 'past_due', 'paused', 'cancelled', 'ended')"),
            name="tenantsubscription_status_check",
        ),
        Index("ix_tenantsubscription_tenant", "tenant_id"),
        MIGRATION_ONLY,
    )

    tenant_id: UUID = Field(sa_type=Uuid)
    plan_id: UUID = Field(sa_type=Uuid)
    status: str = Field(
        default="active", sa_type=Text, sa_column_kwargs={"server_default": text("'active'::text")}
    )
    started_on: dt.date = Field()
    ends_on: dt.date | None = Field(default=None)
    billed_unit_count: int | None = Field(default=None)
    external_billing_ref: str | None = Field(default=None, sa_type=Text)


class TenantSubscriptionCreate(SQLModel):
    """Fields accepted when creating a TenantSubscription."""

    tenant_id: UUID
    plan_id: UUID
    status: TenantSubscriptionStatus = "active"
    started_on: dt.date
    ends_on: dt.date | None = None
    billed_unit_count: int | None = None
    external_billing_ref: str | None = None


class TenantSubscriptionUpdate(SQLModel):
    """Fields accepted when patching a TenantSubscription (all optional)."""

    tenant_id: UUID | None = None
    plan_id: UUID | None = None
    status: TenantSubscriptionStatus | None = None
    started_on: dt.date | None = None
    ends_on: dt.date | None = None
    billed_unit_count: int | None = None
    external_billing_ref: str | None = None


class TenantSubscriptionRead(SQLModel):
    """Fields returned when reading a TenantSubscription."""

    id: UUID
    tenant_id: UUID
    plan_id: UUID
    status: str
    started_on: dt.date
    ends_on: dt.date | None
    billed_unit_count: int | None
    external_billing_ref: str | None
    created_at: dt.datetime
    updated_at: dt.datetime
    created_by: str | None
    updated_by: str | None
