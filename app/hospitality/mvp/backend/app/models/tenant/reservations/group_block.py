"""GroupBlock entity — table ``groupblock``.

Tenant database, G. Groups & reservations.

Group/allotment blocks and per-day pickup.

Mirrors .ttest/contexts/schema-tenant.sql; the Alembic migration creates the table.
"""

import datetime as dt
from typing import Any, Literal
from uuid import UUID

from sqlalchemy import CheckConstraint, ForeignKeyConstraint, Text, UniqueConstraint, Uuid, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel

from app.crud.base_model import MIGRATION_ONLY, TenantEntity

GroupBlockKind = Literal[
    "group",
    "allotment",
    "wedding",
    "event",
    "buyout",
]
GroupBlockStatus = Literal[
    "enquiry",
    "tentative",
    "definite",
    "released",
    "cancelled",
    "completed",
]


class GroupBlock(TenantEntity, table=True):
    """Group/allotment blocks and per-day pickup."""

    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="groupblock_tenant_id_id_key"),
        UniqueConstraint(
            "tenant_id", "property_id", "code", name="groupblock_tenant_id_property_id_code_key"
        ),
        ForeignKeyConstraint(
            ["tenant_id", "property_id"],
            ["property.tenant_id", "property.id"],
            name="groupblock_tenant_id_property_id_fkey",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "account_id"],
            ["account.tenant_id", "account.id"],
            name="groupblock_tenant_id_account_id_fkey",
            ondelete="SET NULL (account_id)",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "rate_plan_id"],
            ["rateplan.tenant_id", "rateplan.id"],
            name="groupblock_tenant_id_rate_plan_id_fkey",
            ondelete="SET NULL (rate_plan_id)",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "master_folio_id"],
            ["folio.tenant_id", "folio.id"],
            name="groupblock_tenant_id_master_folio_id_fkey",
            ondelete="SET NULL (master_folio_id)",
            use_alter=True,
        ),
        CheckConstraint(
            "kind IN ('group', 'allotment', 'wedding', 'event', 'buyout')",
            name="groupblock_kind_check",
        ),
        CheckConstraint(
            (
                "status IN ('enquiry', 'tentative', 'definite', 'released', 'cancelled', "
                "'completed')"
            ),
            name="groupblock_status_check",
        ),
        CheckConstraint("(departure_date > arrival_date)", name="groupblock_check"),
        MIGRATION_ONLY,
    )

    property_id: UUID = Field(sa_type=Uuid)
    account_id: UUID | None = Field(default=None, sa_type=Uuid)
    code: str = Field(sa_type=Text)
    name: str = Field(sa_type=Text)
    kind: str = Field(
        default="group", sa_type=Text, sa_column_kwargs={"server_default": text("'group'::text")}
    )
    status: str = Field(
        default="tentative",
        sa_type=Text,
        sa_column_kwargs={"server_default": text("'tentative'::text")},
    )
    arrival_date: dt.date = Field()
    departure_date: dt.date = Field()
    cutoff_date: dt.date | None = Field(default=None)
    release_rule: dict[str, Any] = Field(
        default_factory=dict,
        sa_type=JSONB,
        sa_column_kwargs={"server_default": text("'{}'::jsonb")},
        description="rolling releases",
    )
    rate_plan_id: UUID | None = Field(default=None, sa_type=Uuid)
    contact: dict[str, Any] = Field(
        default_factory=dict,
        sa_type=JSONB,
        sa_column_kwargs={"server_default": text("'{}'::jsonb")},
    )
    notes: str | None = Field(default=None, sa_type=Text)
    master_folio_id: UUID | None = Field(default=None, sa_type=Uuid)


class GroupBlockCreate(SQLModel):
    """Fields accepted when creating a GroupBlock."""

    property_id: UUID
    account_id: UUID | None = None
    code: str
    name: str
    kind: GroupBlockKind = "group"
    status: GroupBlockStatus = "tentative"
    arrival_date: dt.date
    departure_date: dt.date
    cutoff_date: dt.date | None = None
    release_rule: dict[str, Any] = Field(default_factory=dict)
    rate_plan_id: UUID | None = None
    contact: dict[str, Any] = Field(default_factory=dict)
    notes: str | None = None
    master_folio_id: UUID | None = None


class GroupBlockUpdate(SQLModel):
    """Fields accepted when patching a GroupBlock (all optional)."""

    property_id: UUID | None = None
    account_id: UUID | None = None
    code: str | None = None
    name: str | None = None
    kind: GroupBlockKind | None = None
    status: GroupBlockStatus | None = None
    arrival_date: dt.date | None = None
    departure_date: dt.date | None = None
    cutoff_date: dt.date | None = None
    release_rule: dict[str, Any] | None = None
    rate_plan_id: UUID | None = None
    contact: dict[str, Any] | None = None
    notes: str | None = None
    master_folio_id: UUID | None = None


class GroupBlockRead(SQLModel):
    """Fields returned when reading a GroupBlock."""

    id: UUID
    tenant_id: UUID
    property_id: UUID
    account_id: UUID | None
    code: str
    name: str
    kind: str
    status: str
    arrival_date: dt.date
    departure_date: dt.date
    cutoff_date: dt.date | None
    release_rule: dict[str, Any]
    rate_plan_id: UUID | None
    contact: dict[str, Any]
    notes: str | None
    created_at: dt.datetime
    updated_at: dt.datetime
    created_by: str | None
    updated_by: str | None
    master_folio_id: UUID | None
