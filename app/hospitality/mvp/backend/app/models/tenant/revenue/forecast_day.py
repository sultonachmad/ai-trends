"""ForecastDay entity — table ``forecastday``.

Tenant database, R. Revenue management.

Daily forecast snapshot per unit type.

Mirrors .ttest/contexts/schema-tenant.sql; the Alembic migration creates the table.
"""

import datetime as dt
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import ForeignKeyConstraint, UniqueConstraint, Uuid, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel

from app.crud.base_model import MIGRATION_ONLY, TenantRecord


class ForecastDay(TenantRecord, table=True):
    """Daily forecast snapshot per unit type."""

    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="forecastday_tenant_id_id_key"),
        UniqueConstraint(
            "tenant_id",
            "unit_type_id",
            "stay_date",
            "snapshot_date",
            name="forecastday_tenant_id_unit_type_id_stay_date_snapshot_date_key",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "property_id"],
            ["property.tenant_id", "property.id"],
            name="forecastday_tenant_id_property_id_fkey",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "unit_type_id"],
            ["unittype.tenant_id", "unittype.id"],
            name="forecastday_tenant_id_unit_type_id_fkey",
            ondelete="CASCADE",
        ),
        MIGRATION_ONLY,
    )

    property_id: UUID = Field(sa_type=Uuid)
    unit_type_id: UUID = Field(sa_type=Uuid)
    stay_date: dt.date = Field()
    snapshot_date: dt.date = Field()
    on_books: int = Field()
    forecast_occupancy: Decimal | None = Field(default=None, max_digits=6, decimal_places=4)
    forecast_low: Decimal | None = Field(default=None, max_digits=6, decimal_places=4)
    forecast_high: Decimal | None = Field(default=None, max_digits=6, decimal_places=4)
    forecast_adr: Decimal | None = Field(default=None, max_digits=18, decimal_places=2)
    components: dict[str, Any] = Field(
        default_factory=dict,
        sa_type=JSONB,
        sa_column_kwargs={"server_default": text("'{}'::jsonb")},
        description="explainable parts: baseline, dow, pace, events",
    )


class ForecastDayCreate(SQLModel):
    """Fields accepted when creating a ForecastDay."""

    property_id: UUID
    unit_type_id: UUID
    stay_date: dt.date
    snapshot_date: dt.date
    on_books: int
    forecast_occupancy: Decimal | None = Field(default=None, max_digits=6, decimal_places=4)
    forecast_low: Decimal | None = Field(default=None, max_digits=6, decimal_places=4)
    forecast_high: Decimal | None = Field(default=None, max_digits=6, decimal_places=4)
    forecast_adr: Decimal | None = Field(default=None, max_digits=18, decimal_places=2)
    components: dict[str, Any] = Field(default_factory=dict)


class ForecastDayUpdate(SQLModel):
    """Fields accepted when patching a ForecastDay (all optional)."""

    property_id: UUID | None = None
    unit_type_id: UUID | None = None
    stay_date: dt.date | None = None
    snapshot_date: dt.date | None = None
    on_books: int | None = None
    forecast_occupancy: Decimal | None = Field(default=None, max_digits=6, decimal_places=4)
    forecast_low: Decimal | None = Field(default=None, max_digits=6, decimal_places=4)
    forecast_high: Decimal | None = Field(default=None, max_digits=6, decimal_places=4)
    forecast_adr: Decimal | None = Field(default=None, max_digits=18, decimal_places=2)
    components: dict[str, Any] | None = None


class ForecastDayRead(SQLModel):
    """Fields returned when reading a ForecastDay."""

    id: UUID
    tenant_id: UUID
    property_id: UUID
    unit_type_id: UUID
    stay_date: dt.date
    snapshot_date: dt.date
    on_books: int
    forecast_occupancy: Decimal | None
    forecast_low: Decimal | None
    forecast_high: Decimal | None
    forecast_adr: Decimal | None
    components: dict[str, Any]
