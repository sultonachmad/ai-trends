"""RatePlanUnitType entity — table ``rateplanunittype``.

Tenant database, E. Rates, policies, products & restrictions.

Applicability and package inclusions.

Mirrors .ttest/contexts/schema-tenant.sql; the Alembic migration creates the table.
"""

from uuid import UUID

from sqlalchemy import ForeignKeyConstraint, Uuid
from sqlmodel import Field, SQLModel

from app.crud.base_model import MIGRATION_ONLY


class RatePlanUnitType(SQLModel, table=True):
    """Applicability and package inclusions."""

    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "rate_plan_id"],
            ["rateplan.tenant_id", "rateplan.id"],
            name="rateplanunittype_tenant_id_rate_plan_id_fkey",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "unit_type_id"],
            ["unittype.tenant_id", "unittype.id"],
            name="rateplanunittype_tenant_id_unit_type_id_fkey",
            ondelete="CASCADE",
        ),
        MIGRATION_ONLY,
    )

    tenant_id: UUID = Field(primary_key=True, sa_type=Uuid)
    rate_plan_id: UUID = Field(primary_key=True, sa_type=Uuid)
    unit_type_id: UUID = Field(primary_key=True, sa_type=Uuid)


class RatePlanUnitTypeCreate(SQLModel):
    """Fields accepted when creating a RatePlanUnitType."""

    rate_plan_id: UUID
    unit_type_id: UUID


class RatePlanUnitTypeUpdate(SQLModel):
    """
    Patch shape for a RatePlanUnitType: every column is part of the key, nothing is patchable.
    """

    pass


class RatePlanUnitTypeRead(SQLModel):
    """Fields returned when reading a RatePlanUnitType."""

    tenant_id: UUID
    rate_plan_id: UUID
    unit_type_id: UUID
