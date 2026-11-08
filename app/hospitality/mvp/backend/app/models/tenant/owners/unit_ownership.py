"""UnitOwnership entity — table ``unitownership``.

Tenant database, N. Owners.

Owners, shares, agreements.

Mirrors .ttest/contexts/schema-tenant.sql; the Alembic migration creates the table.
"""

import datetime as dt
from decimal import Decimal
from uuid import UUID

from sqlalchemy import CheckConstraint, ForeignKeyConstraint, UniqueConstraint, Uuid
from sqlmodel import Field, SQLModel

from app.crud.base_model import MIGRATION_ONLY, TenantEntity


class UnitOwnership(TenantEntity, table=True):
    """Owners, shares, agreements."""

    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="unitownership_tenant_id_id_key"),
        ForeignKeyConstraint(
            ["tenant_id", "unit_id"],
            ["unit.tenant_id", "unit.id"],
            name="unitownership_tenant_id_unit_id_fkey",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "owner_id"],
            ["owner.tenant_id", "owner.id"],
            name="unitownership_tenant_id_owner_id_fkey",
            ondelete="CASCADE",
        ),
        CheckConstraint(
            "((share_pct > (0)::numeric) AND (share_pct <= (100)::numeric))",
            name="unitownership_share_pct_check",
        ),
        CheckConstraint(
            "((effective_to IS NULL) OR (effective_to >= effective_from))",
            name="unitownership_check",
        ),
        MIGRATION_ONLY,
    )

    unit_id: UUID = Field(sa_type=Uuid)
    owner_id: UUID = Field(sa_type=Uuid)
    share_pct: Decimal = Field(max_digits=5, decimal_places=2)
    effective_from: dt.date = Field()
    effective_to: dt.date | None = Field(default=None)


class UnitOwnershipCreate(SQLModel):
    """Fields accepted when creating a UnitOwnership."""

    unit_id: UUID
    owner_id: UUID
    share_pct: Decimal = Field(max_digits=5, decimal_places=2, gt=0, le=100)
    effective_from: dt.date
    effective_to: dt.date | None = None


class UnitOwnershipUpdate(SQLModel):
    """Fields accepted when patching a UnitOwnership (all optional)."""

    unit_id: UUID | None = None
    owner_id: UUID | None = None
    share_pct: Decimal | None = Field(default=None, max_digits=5, decimal_places=2, gt=0, le=100)
    effective_from: dt.date | None = None
    effective_to: dt.date | None = None


class UnitOwnershipRead(SQLModel):
    """Fields returned when reading a UnitOwnership."""

    id: UUID
    tenant_id: UUID
    unit_id: UUID
    owner_id: UUID
    share_pct: Decimal
    effective_from: dt.date
    effective_to: dt.date | None
    created_at: dt.datetime
    updated_at: dt.datetime
    created_by: str | None
    updated_by: str | None
