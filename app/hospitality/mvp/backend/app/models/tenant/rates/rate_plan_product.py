"""RatePlanProduct entity — table ``rateplanproduct``.

Tenant database, E. Rates, policies, products & restrictions.

Package inclusions (breakfast in BB rate, spa credit …).

Mirrors .ttest/contexts/schema-tenant.sql; the Alembic migration creates the table.
"""

from decimal import Decimal
from uuid import UUID

from sqlalchemy import ForeignKeyConstraint, Uuid, text
from sqlmodel import Field, SQLModel

from app.crud.base_model import MIGRATION_ONLY


class RatePlanProduct(SQLModel, table=True):
    """Package inclusions (breakfast in BB rate, spa credit …)."""

    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "rate_plan_id"],
            ["rateplan.tenant_id", "rateplan.id"],
            name="rateplanproduct_tenant_id_rate_plan_id_fkey",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "product_id"],
            ["product.tenant_id", "product.id"],
            name="rateplanproduct_tenant_id_product_id_fkey",
            ondelete="CASCADE",
        ),
        MIGRATION_ONLY,
    )

    tenant_id: UUID = Field(primary_key=True, sa_type=Uuid)
    rate_plan_id: UUID = Field(primary_key=True, sa_type=Uuid)
    product_id: UUID = Field(primary_key=True, sa_type=Uuid)
    quantity: Decimal = Field(
        default=Decimal("1"),
        max_digits=10,
        decimal_places=2,
        sa_column_kwargs={"server_default": text("1")},
    )
    allocation_amount: Decimal | None = Field(
        default=None,
        max_digits=18,
        decimal_places=2,
        description="revenue split to the product's department",
    )


class RatePlanProductCreate(SQLModel):
    """Fields accepted when creating a RatePlanProduct."""

    rate_plan_id: UUID
    product_id: UUID
    quantity: Decimal = Field(default=Decimal("1"), max_digits=10, decimal_places=2)
    allocation_amount: Decimal | None = Field(default=None, max_digits=18, decimal_places=2)


class RatePlanProductUpdate(SQLModel):
    """Fields accepted when patching a RatePlanProduct (all optional)."""

    quantity: Decimal | None = Field(default=None, max_digits=10, decimal_places=2)
    allocation_amount: Decimal | None = Field(default=None, max_digits=18, decimal_places=2)


class RatePlanProductRead(SQLModel):
    """Fields returned when reading a RatePlanProduct."""

    tenant_id: UUID
    rate_plan_id: UUID
    product_id: UUID
    quantity: Decimal
    allocation_amount: Decimal | None
