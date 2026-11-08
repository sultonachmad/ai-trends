"""Meter entity — table ``meter``.

Tenant database, O. Long stay, kos & leases.

Electricity / PLN token / water.

Mirrors .ttest/contexts/schema-tenant.sql; the Alembic migration creates the table.
"""

import datetime as dt
from decimal import Decimal
from typing import Literal
from uuid import UUID

from sqlalchemy import CheckConstraint, ForeignKeyConstraint, Text, UniqueConstraint, Uuid, text
from sqlmodel import Field, SQLModel

from app.crud.base_model import MIGRATION_ONLY, TenantEntity

MeterKind = Literal[
    "electricity",
    "electricity_prepaid_token",
    "water",
    "gas",
]


class Meter(TenantEntity, table=True):
    """Electricity / PLN token / water."""

    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="meter_tenant_id_id_key"),
        UniqueConstraint(
            "tenant_id", "property_id", "meter_no", name="meter_tenant_id_property_id_meter_no_key"
        ),
        ForeignKeyConstraint(
            ["tenant_id", "property_id"],
            ["property.tenant_id", "property.id"],
            name="meter_tenant_id_property_id_fkey",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "unit_id"],
            ["unit.tenant_id", "unit.id"],
            name="meter_tenant_id_unit_id_fkey",
            ondelete="SET NULL (unit_id)",
        ),
        CheckConstraint(
            "kind IN ('electricity', 'electricity_prepaid_token', 'water', 'gas')",
            name="meter_kind_check",
        ),
        MIGRATION_ONLY,
    )

    property_id: UUID = Field(sa_type=Uuid)
    unit_id: UUID | None = Field(default=None, sa_type=Uuid)
    kind: str = Field(sa_type=Text)
    meter_no: str = Field(sa_type=Text, description="PLN customer/meter id")
    unit_price: Decimal | None = Field(
        default=None,
        max_digits=18,
        decimal_places=4,
        description="per kWh / m3 for postpaid sub-metering",
    )
    is_active: bool = Field(default=True, sa_column_kwargs={"server_default": text("true")})


class MeterCreate(SQLModel):
    """Fields accepted when creating a Meter."""

    property_id: UUID
    unit_id: UUID | None = None
    kind: MeterKind
    meter_no: str
    unit_price: Decimal | None = Field(default=None, max_digits=18, decimal_places=4)
    is_active: bool = True


class MeterUpdate(SQLModel):
    """Fields accepted when patching a Meter (all optional)."""

    property_id: UUID | None = None
    unit_id: UUID | None = None
    kind: MeterKind | None = None
    meter_no: str | None = None
    unit_price: Decimal | None = Field(default=None, max_digits=18, decimal_places=4)
    is_active: bool | None = None


class MeterRead(SQLModel):
    """Fields returned when reading a Meter."""

    id: UUID
    tenant_id: UUID
    property_id: UUID
    unit_id: UUID | None
    kind: str
    meter_no: str
    unit_price: Decimal | None
    is_active: bool
    created_at: dt.datetime
    updated_at: dt.datetime
    created_by: str | None
    updated_by: str | None
