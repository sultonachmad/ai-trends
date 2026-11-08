"""Product entity — table ``product``.

Tenant database, E. Rates, policies, products & restrictions.

Anything sellable besides the unit itself: breakfast, parking, fees, services, package parts.

Mirrors .ttest/contexts/schema-tenant.sql; the Alembic migration creates the table.
"""

import datetime as dt
from decimal import Decimal
from typing import Any, Literal
from uuid import UUID

from sqlalchemy import CheckConstraint, ForeignKeyConstraint, Text, UniqueConstraint, Uuid, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel

from app.crud.base_model import MIGRATION_ONLY, TenantEntity

ProductKind = Literal[
    "meal",
    "fee",
    "service",
    "parking",
    "rental",
    "retail",
    "activity",
    "transfer",
    "upgrade",
    "other",
]
ProductPricingUnit = Literal[
    "per_stay",
    "per_night",
    "per_person",
    "per_person_night",
    "per_item",
    "per_hour",
    "per_month",
]


class Product(TenantEntity, table=True):
    """
    Anything sellable besides the unit itself: breakfast, parking, fees, services, package
    parts.
    """

    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="product_tenant_id_id_key"),
        UniqueConstraint(
            "tenant_id", "property_id", "code", name="product_tenant_id_property_id_code_key"
        ),
        ForeignKeyConstraint(
            ["tenant_id", "property_id"],
            ["property.tenant_id", "property.id"],
            name="product_tenant_id_property_id_fkey",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "inventory_item_id"],
            ["inventoryitem.tenant_id", "inventoryitem.id"],
            name="product_tenant_id_inventory_item_id_fkey",
            ondelete="SET NULL (inventory_item_id)",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "transaction_code_id"],
            ["transactioncode.tenant_id", "transactioncode.id"],
            name="product_tenant_id_transaction_code_id_fkey",
        ),
        CheckConstraint(
            (
                "kind IN ('meal', 'fee', 'service', 'parking', 'rental', 'retail', "
                "'activity', 'transfer', 'upgrade', 'other')"
            ),
            name="product_kind_check",
        ),
        CheckConstraint(
            (
                "pricing_unit IN ('per_stay', 'per_night', 'per_person', "
                "'per_person_night', 'per_item', 'per_hour', 'per_month')"
            ),
            name="product_pricing_unit_check",
        ),
        CheckConstraint("(price >= (0)::numeric)", name="product_price_check"),
        MIGRATION_ONLY,
    )

    property_id: UUID = Field(sa_type=Uuid)
    code: str = Field(sa_type=Text)
    name: str = Field(sa_type=Text)
    kind: str = Field(sa_type=Text)
    pricing_unit: str = Field(sa_type=Text)
    price: Decimal = Field(
        default=Decimal("0"),
        max_digits=18,
        decimal_places=2,
        sa_column_kwargs={"server_default": text("0")},
    )
    is_mandatory: bool = Field(
        default=False,
        sa_column_kwargs={"server_default": text("false")},
        description="resort/cleaning fee auto-added",
    )
    is_bookable_online: bool = Field(
        default=False, sa_column_kwargs={"server_default": text("false")}
    )
    inventory_item_id: UUID | None = Field(default=None, sa_type=Uuid)
    transaction_code_id: UUID = Field(sa_type=Uuid)
    content: dict[str, Any] = Field(
        default_factory=dict,
        sa_type=JSONB,
        sa_column_kwargs={"server_default": text("'{}'::jsonb")},
    )
    is_active: bool = Field(default=True, sa_column_kwargs={"server_default": text("true")})


class ProductCreate(SQLModel):
    """Fields accepted when creating a Product."""

    property_id: UUID
    code: str
    name: str
    kind: ProductKind
    pricing_unit: ProductPricingUnit
    price: Decimal = Field(default=Decimal("0"), max_digits=18, decimal_places=2, ge=0)
    is_mandatory: bool = False
    is_bookable_online: bool = False
    inventory_item_id: UUID | None = None
    transaction_code_id: UUID
    content: dict[str, Any] = Field(default_factory=dict)
    is_active: bool = True


class ProductUpdate(SQLModel):
    """Fields accepted when patching a Product (all optional)."""

    property_id: UUID | None = None
    code: str | None = None
    name: str | None = None
    kind: ProductKind | None = None
    pricing_unit: ProductPricingUnit | None = None
    price: Decimal | None = Field(default=None, max_digits=18, decimal_places=2, ge=0)
    is_mandatory: bool | None = None
    is_bookable_online: bool | None = None
    inventory_item_id: UUID | None = None
    transaction_code_id: UUID | None = None
    content: dict[str, Any] | None = None
    is_active: bool | None = None


class ProductRead(SQLModel):
    """Fields returned when reading a Product."""

    id: UUID
    tenant_id: UUID
    property_id: UUID
    code: str
    name: str
    kind: str
    pricing_unit: str
    price: Decimal
    is_mandatory: bool
    is_bookable_online: bool
    inventory_item_id: UUID | None
    transaction_code_id: UUID
    content: dict[str, Any]
    is_active: bool
    created_at: dt.datetime
    updated_at: dt.datetime
    created_by: str | None
    updated_by: str | None
