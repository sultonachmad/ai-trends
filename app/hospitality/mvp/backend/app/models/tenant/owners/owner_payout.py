"""OwnerPayout entity — table ``ownerpayout``.

Tenant database, N. Owners.

Owner accounting.

Mirrors .ttest/contexts/schema-tenant.sql; the Alembic migration creates the table.
"""

import datetime as dt
from decimal import Decimal
from typing import Literal
from uuid import UUID

from sqlalchemy import (
    CHAR,
    CheckConstraint,
    ForeignKeyConstraint,
    Text,
    UniqueConstraint,
    Uuid,
    text,
)
from sqlmodel import Field, SQLModel

from app.crud.base_model import MIGRATION_ONLY, TenantEntity

OwnerPayoutMethod = Literal[
    "bank_transfer",
    "cash",
    "wise",
    "other",
]


class OwnerPayout(TenantEntity, table=True):
    """Owner accounting."""

    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="ownerpayout_tenant_id_id_key"),
        ForeignKeyConstraint(
            ["tenant_id", "owner_id"],
            ["owner.tenant_id", "owner.id"],
            name="ownerpayout_tenant_id_owner_id_fkey",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "statement_id"],
            ["ownerstatement.tenant_id", "ownerstatement.id"],
            name="ownerpayout_tenant_id_statement_id_fkey",
            ondelete="SET NULL (statement_id)",
        ),
        CheckConstraint("(amount > (0)::numeric)", name="ownerpayout_amount_check"),
        CheckConstraint(
            "method IN ('bank_transfer', 'cash', 'wise', 'other')", name="ownerpayout_method_check"
        ),
        MIGRATION_ONLY,
    )

    owner_id: UUID = Field(sa_type=Uuid)
    statement_id: UUID | None = Field(default=None, sa_type=Uuid)
    amount: Decimal = Field(max_digits=18, decimal_places=2)
    currency: str = Field(
        default="IDR", sa_type=CHAR(3), sa_column_kwargs={"server_default": text("'IDR'::bpchar")}
    )
    paid_on: dt.date = Field()
    method: str = Field(sa_type=Text)
    reference: str | None = Field(default=None, sa_type=Text)
    withholding_tax: Decimal = Field(
        default=Decimal("0"),
        max_digits=18,
        decimal_places=2,
        sa_column_kwargs={"server_default": text("0")},
    )


class OwnerPayoutCreate(SQLModel):
    """Fields accepted when creating a OwnerPayout."""

    owner_id: UUID
    statement_id: UUID | None = None
    amount: Decimal = Field(max_digits=18, decimal_places=2, gt=0)
    currency: str = Field(default="IDR", min_length=3, max_length=3)
    paid_on: dt.date
    method: OwnerPayoutMethod
    reference: str | None = None
    withholding_tax: Decimal = Field(default=Decimal("0"), max_digits=18, decimal_places=2)


class OwnerPayoutUpdate(SQLModel):
    """Fields accepted when patching a OwnerPayout (all optional)."""

    owner_id: UUID | None = None
    statement_id: UUID | None = None
    amount: Decimal | None = Field(default=None, max_digits=18, decimal_places=2, gt=0)
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    paid_on: dt.date | None = None
    method: OwnerPayoutMethod | None = None
    reference: str | None = None
    withholding_tax: Decimal | None = Field(default=None, max_digits=18, decimal_places=2)


class OwnerPayoutRead(SQLModel):
    """Fields returned when reading a OwnerPayout."""

    id: UUID
    tenant_id: UUID
    owner_id: UUID
    statement_id: UUID | None
    amount: Decimal
    currency: str
    paid_on: dt.date
    method: str
    reference: str | None
    withholding_tax: Decimal
    created_at: dt.datetime
    updated_at: dt.datetime
    created_by: str | None
    updated_by: str | None
