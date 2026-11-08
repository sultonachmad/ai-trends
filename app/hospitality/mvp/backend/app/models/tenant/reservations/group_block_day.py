"""GroupBlockDay entity — table ``groupblockday``.

Tenant database, G. Groups & reservations.

Group/allotment blocks and per-day pickup.

Mirrors .ttest/contexts/schema-tenant.sql; the Alembic migration creates the table.
"""

import datetime as dt
from decimal import Decimal
from uuid import UUID

from sqlalchemy import CheckConstraint, ForeignKeyConstraint, UniqueConstraint, Uuid, text
from sqlmodel import Field, SQLModel

from app.crud.base_model import MIGRATION_ONLY, TenantRecord


class GroupBlockDay(TenantRecord, table=True):
    """Group/allotment blocks and per-day pickup."""

    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="groupblockday_tenant_id_id_key"),
        UniqueConstraint(
            "tenant_id",
            "group_block_id",
            "unit_type_id",
            "stay_date",
            name="groupblockday_tenant_id_group_block_id_unit_type_id_stay_da_key",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "group_block_id"],
            ["groupblock.tenant_id", "groupblock.id"],
            name="groupblockday_tenant_id_group_block_id_fkey",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "unit_type_id"],
            ["unittype.tenant_id", "unittype.id"],
            name="groupblockday_tenant_id_unit_type_id_fkey",
        ),
        CheckConstraint("(contracted >= 0)", name="groupblockday_contracted_check"),
        CheckConstraint("(picked_up >= 0)", name="groupblockday_picked_up_check"),
        MIGRATION_ONLY,
    )

    group_block_id: UUID = Field(sa_type=Uuid)
    unit_type_id: UUID = Field(sa_type=Uuid)
    stay_date: dt.date = Field()
    contracted: int = Field()
    picked_up: int = Field(default=0, sa_column_kwargs={"server_default": text("0")})
    rate_amount: Decimal | None = Field(default=None, max_digits=18, decimal_places=2)


class GroupBlockDayCreate(SQLModel):
    """Fields accepted when creating a GroupBlockDay."""

    group_block_id: UUID
    unit_type_id: UUID
    stay_date: dt.date
    contracted: int = Field(ge=0)
    picked_up: int = Field(default=0, ge=0)
    rate_amount: Decimal | None = Field(default=None, max_digits=18, decimal_places=2)


class GroupBlockDayUpdate(SQLModel):
    """Fields accepted when patching a GroupBlockDay (all optional)."""

    group_block_id: UUID | None = None
    unit_type_id: UUID | None = None
    stay_date: dt.date | None = None
    contracted: int | None = Field(default=None, ge=0)
    picked_up: int | None = Field(default=None, ge=0)
    rate_amount: Decimal | None = Field(default=None, max_digits=18, decimal_places=2)


class GroupBlockDayRead(SQLModel):
    """Fields returned when reading a GroupBlockDay."""

    id: UUID
    tenant_id: UUID
    group_block_id: UUID
    unit_type_id: UUID
    stay_date: dt.date
    contracted: int
    picked_up: int
    rate_amount: Decimal | None
