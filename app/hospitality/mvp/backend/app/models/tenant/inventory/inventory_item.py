"""InventoryItem entity — table ``inventoryitem``.

Tenant database, C. Inventory.

Countable non-unit inventory: parking, cots, extra beds, lockers, bikes, EV chargers.

Mirrors .ttest/contexts/schema-tenant.sql; the Alembic migration creates the table.
"""

import datetime as dt
from typing import Literal
from uuid import UUID

from sqlalchemy import CheckConstraint, ForeignKeyConstraint, Text, UniqueConstraint, Uuid, text
from sqlmodel import Field, SQLModel

from app.crud.base_model import MIGRATION_ONLY, TenantEntity

InventoryItemKind = Literal[
    "parking",
    "cot",
    "extra_bed",
    "locker",
    "equipment",
    "ev_charger",
    "other",
]


class InventoryItem(TenantEntity, table=True):
    """
    Countable non-unit inventory: parking, cots, extra beds, lockers, bikes, EV chargers.
    """

    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="inventoryitem_tenant_id_id_key"),
        UniqueConstraint(
            "tenant_id", "property_id", "code", name="inventoryitem_tenant_id_property_id_code_key"
        ),
        ForeignKeyConstraint(
            ["tenant_id", "property_id"],
            ["property.tenant_id", "property.id"],
            name="inventoryitem_tenant_id_property_id_fkey",
            ondelete="CASCADE",
        ),
        CheckConstraint(
            (
                "kind IN ('parking', 'cot', 'extra_bed', 'locker', 'equipment', "
                "'ev_charger', 'other')"
            ),
            name="inventoryitem_kind_check",
        ),
        CheckConstraint("(total_quantity >= 0)", name="inventoryitem_total_quantity_check"),
        MIGRATION_ONLY,
    )

    property_id: UUID = Field(sa_type=Uuid)
    code: str = Field(sa_type=Text)
    name: str = Field(sa_type=Text)
    kind: str = Field(sa_type=Text)
    total_quantity: int = Field()
    is_active: bool = Field(default=True, sa_column_kwargs={"server_default": text("true")})


class InventoryItemCreate(SQLModel):
    """Fields accepted when creating a InventoryItem."""

    property_id: UUID
    code: str
    name: str
    kind: InventoryItemKind
    total_quantity: int = Field(ge=0)
    is_active: bool = True


class InventoryItemUpdate(SQLModel):
    """Fields accepted when patching a InventoryItem (all optional)."""

    property_id: UUID | None = None
    code: str | None = None
    name: str | None = None
    kind: InventoryItemKind | None = None
    total_quantity: int | None = Field(default=None, ge=0)
    is_active: bool | None = None


class InventoryItemRead(SQLModel):
    """Fields returned when reading a InventoryItem."""

    id: UUID
    tenant_id: UUID
    property_id: UUID
    code: str
    name: str
    kind: str
    total_quantity: int
    is_active: bool
    created_at: dt.datetime
    updated_at: dt.datetime
    created_by: str | None
    updated_by: str | None
