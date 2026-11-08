"""PosOrderLine entity — table ``posorderline``.

Tenant database, Q. Ancillary / POS lite.

POS Lite, services, gift vouchers.

Mirrors .ttest/contexts/schema-tenant.sql; the Alembic migration creates the table.
"""

from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import CheckConstraint, ForeignKeyConstraint, UniqueConstraint, Uuid, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel

from app.crud.base_model import MIGRATION_ONLY, TenantRecord


class PosOrderLine(TenantRecord, table=True):
    """POS Lite, services, gift vouchers."""

    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="posorderline_tenant_id_id_key"),
        ForeignKeyConstraint(
            ["tenant_id", "pos_order_id"],
            ["posorder.tenant_id", "posorder.id"],
            name="posorderline_tenant_id_pos_order_id_fkey",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "product_id"],
            ["product.tenant_id", "product.id"],
            name="posorderline_tenant_id_product_id_fkey",
        ),
        CheckConstraint("(quantity > (0)::numeric)", name="posorderline_quantity_check"),
        MIGRATION_ONLY,
    )

    pos_order_id: UUID = Field(sa_type=Uuid)
    product_id: UUID = Field(sa_type=Uuid)
    quantity: Decimal = Field(max_digits=10, decimal_places=2)
    unit_price: Decimal = Field(max_digits=18, decimal_places=2)
    amount: Decimal = Field(max_digits=18, decimal_places=2)
    modifiers: list[Any] = Field(
        default_factory=list,
        sa_type=JSONB,
        sa_column_kwargs={"server_default": text("'[]'::jsonb")},
    )


class PosOrderLineCreate(SQLModel):
    """Fields accepted when creating a PosOrderLine."""

    pos_order_id: UUID
    product_id: UUID
    quantity: Decimal = Field(max_digits=10, decimal_places=2, gt=0)
    unit_price: Decimal = Field(max_digits=18, decimal_places=2)
    amount: Decimal = Field(max_digits=18, decimal_places=2)
    modifiers: list[Any] = Field(default_factory=list)


class PosOrderLineUpdate(SQLModel):
    """Fields accepted when patching a PosOrderLine (all optional)."""

    pos_order_id: UUID | None = None
    product_id: UUID | None = None
    quantity: Decimal | None = Field(default=None, max_digits=10, decimal_places=2, gt=0)
    unit_price: Decimal | None = Field(default=None, max_digits=18, decimal_places=2)
    amount: Decimal | None = Field(default=None, max_digits=18, decimal_places=2)
    modifiers: list[Any] | None = None


class PosOrderLineRead(SQLModel):
    """Fields returned when reading a PosOrderLine."""

    id: UUID
    tenant_id: UUID
    pos_order_id: UUID
    product_id: UUID
    quantity: Decimal
    unit_price: Decimal
    amount: Decimal
    modifiers: list[Any]
