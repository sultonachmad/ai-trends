"""ReasonCode entity — table ``reasoncode``.

Tenant database, A. Organisation & property.

Reason codes for cancellations, voids, discounts, upgrades, OOO, comps …

Mirrors .ttest/contexts/schema-tenant.sql; the Alembic migration creates the table.
"""

import datetime as dt
from typing import Literal
from uuid import UUID

from sqlalchemy import CheckConstraint, Text, UniqueConstraint, text
from sqlmodel import Field, SQLModel

from app.crud.base_model import MIGRATION_ONLY, TenantEntity

ReasonCodeKind = Literal[
    "cancellation",
    "void",
    "adjustment",
    "discount",
    "upgrade",
    "room_move",
    "out_of_order",
    "complimentary",
    "no_show_waiver",
    "refund",
    "blacklist",
    "other",
]


class ReasonCode(TenantEntity, table=True):
    """Reason codes for cancellations, voids, discounts, upgrades, OOO, comps …"""

    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="reasoncode_tenant_id_id_key"),
        UniqueConstraint("tenant_id", "kind", "code", name="reasoncode_tenant_id_kind_code_key"),
        CheckConstraint(
            (
                "kind IN ('cancellation', 'void', 'adjustment', 'discount', 'upgrade', "
                "'room_move', 'out_of_order', 'complimentary', 'no_show_waiver', "
                "'refund', 'blacklist', 'other')"
            ),
            name="reasoncode_kind_check",
        ),
        MIGRATION_ONLY,
    )

    kind: str = Field(sa_type=Text)
    code: str = Field(sa_type=Text)
    name: str = Field(sa_type=Text)
    requires_approval: bool = Field(
        default=False, sa_column_kwargs={"server_default": text("false")}
    )
    is_active: bool = Field(default=True, sa_column_kwargs={"server_default": text("true")})


class ReasonCodeCreate(SQLModel):
    """Fields accepted when creating a ReasonCode."""

    kind: ReasonCodeKind
    code: str
    name: str
    requires_approval: bool = False
    is_active: bool = True


class ReasonCodeUpdate(SQLModel):
    """Fields accepted when patching a ReasonCode (all optional)."""

    kind: ReasonCodeKind | None = None
    code: str | None = None
    name: str | None = None
    requires_approval: bool | None = None
    is_active: bool | None = None


class ReasonCodeRead(SQLModel):
    """Fields returned when reading a ReasonCode."""

    id: UUID
    tenant_id: UUID
    kind: str
    code: str
    name: str
    requires_approval: bool
    is_active: bool
    created_at: dt.datetime
    updated_at: dt.datetime
    created_by: str | None
    updated_by: str | None
