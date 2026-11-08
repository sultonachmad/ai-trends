"""UnitBlock entity — table ``unitblock``.

Tenant database, N. Owners.

Out of order / out of service / owner block / house use on a unit.

Mirrors .ttest/contexts/schema-tenant.sql; the Alembic migration creates the table.
"""

import datetime as dt
from typing import Any, Literal
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    Column,
    Computed,
    ForeignKeyConstraint,
    Text,
    UniqueConstraint,
    Uuid,
    text,
)
from sqlalchemy.dialects.postgresql import TSTZRANGE, ExcludeConstraint
from sqlmodel import Field, SQLModel

from app.crud.base_model import MIGRATION_ONLY, TenantEntity, utc_datetime_field

UnitBlockKind = Literal[
    "out_of_order",
    "out_of_service",
    "owner_block",
    "house_use",
    "maintenance_hold",
]
UnitBlockStatus = Literal[
    "active",
    "released",
    "cancelled",
]


class UnitBlock(TenantEntity, table=True):
    """Out of order / out of service / owner block / house use on a unit."""

    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="unitblock_tenant_id_id_key"),
        ForeignKeyConstraint(
            ["tenant_id", "unit_id"],
            ["unit.tenant_id", "unit.id"],
            name="unitblock_tenant_id_unit_id_fkey",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "reason_code_id"],
            ["reasoncode.tenant_id", "reasoncode.id"],
            name="unitblock_tenant_id_reason_code_id_fkey",
            ondelete="SET NULL (reason_code_id)",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "work_order_id"],
            ["workorder.tenant_id", "workorder.id"],
            name="unitblock_tenant_id_work_order_id_fkey",
            ondelete="SET NULL (work_order_id)",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "owner_id"],
            ["owner.tenant_id", "owner.id"],
            name="unitblock_tenant_id_owner_id_fkey",
            ondelete="SET NULL (owner_id)",
        ),
        CheckConstraint(
            (
                "kind IN ('out_of_order', 'out_of_service', 'owner_block', 'house_use', "
                "'maintenance_hold')"
            ),
            name="unitblock_kind_check",
        ),
        CheckConstraint(
            "status IN ('active', 'released', 'cancelled')", name="unitblock_status_check"
        ),
        CheckConstraint("(end_at > start_at)", name="unitblock_check"),
        ExcludeConstraint(
            ("unit_id", "="),
            ("period", "&&"),
            using="gist",
            name="ex_unitblock_no_overlap",
            where=text("(status = 'active'::text)"),
        ),
        MIGRATION_ONLY,
    )

    unit_id: UUID = Field(sa_type=Uuid)
    kind: str = Field(sa_type=Text)
    start_at: dt.datetime = utc_datetime_field(nullable=False)  # type: ignore[assignment]
    end_at: dt.datetime = utc_datetime_field(nullable=False)  # type: ignore[assignment]
    period: Any = Field(
        default=None,
        sa_column=Column(
            "period", TSTZRANGE, Computed("tstzrange(start_at, end_at, '[)'::text)", persisted=True)
        ),
    )
    reason_code_id: UUID | None = Field(default=None, sa_type=Uuid)
    reason_text: str | None = Field(default=None, sa_type=Text)
    work_order_id: UUID | None = Field(default=None, sa_type=Uuid)
    owner_id: UUID | None = Field(default=None, sa_type=Uuid)
    status: str = Field(
        default="active", sa_type=Text, sa_column_kwargs={"server_default": text("'active'::text")}
    )


class UnitBlockCreate(SQLModel):
    """Fields accepted when creating a UnitBlock."""

    unit_id: UUID
    kind: UnitBlockKind
    start_at: dt.datetime
    end_at: dt.datetime
    reason_code_id: UUID | None = None
    reason_text: str | None = None
    work_order_id: UUID | None = None
    owner_id: UUID | None = None
    status: UnitBlockStatus = "active"


class UnitBlockUpdate(SQLModel):
    """Fields accepted when patching a UnitBlock (all optional)."""

    unit_id: UUID | None = None
    kind: UnitBlockKind | None = None
    start_at: dt.datetime | None = None
    end_at: dt.datetime | None = None
    reason_code_id: UUID | None = None
    reason_text: str | None = None
    work_order_id: UUID | None = None
    owner_id: UUID | None = None
    status: UnitBlockStatus | None = None


class UnitBlockRead(SQLModel):
    """Fields returned when reading a UnitBlock (never returns: period)."""

    id: UUID
    tenant_id: UUID
    unit_id: UUID
    kind: str
    start_at: dt.datetime
    end_at: dt.datetime
    reason_code_id: UUID | None
    reason_text: str | None
    work_order_id: UUID | None
    owner_id: UUID | None
    status: str
    created_at: dt.datetime
    updated_at: dt.datetime
    created_by: str | None
    updated_by: str | None
