"""ExchangeRate entity — table ``exchangerate``.

Tenant database, D. Finance configuration.

FX for display and owner reporting.

Mirrors .ttest/contexts/schema-tenant.sql; the Alembic migration creates the table.
"""

import datetime as dt
from decimal import Decimal
from uuid import UUID

from sqlalchemy import CHAR, CheckConstraint, Text, UniqueConstraint, text
from sqlmodel import Field, SQLModel

from app.crud.base_model import MIGRATION_ONLY, TenantEntity


class ExchangeRate(TenantEntity, table=True):
    """FX for display and owner reporting."""

    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="exchangerate_tenant_id_id_key"),
        UniqueConstraint(
            "tenant_id",
            "base_currency",
            "quote_currency",
            "effective_date",
            name="exchangerate_tenant_id_base_currency_quote_currency_effecti_key",
        ),
        CheckConstraint("(rate > (0)::numeric)", name="exchangerate_rate_check"),
        MIGRATION_ONLY,
    )

    base_currency: str = Field(sa_type=CHAR(3))
    quote_currency: str = Field(sa_type=CHAR(3))
    rate: Decimal = Field(max_digits=20, decimal_places=8)
    effective_date: dt.date = Field()
    source: str = Field(
        default="manual", sa_type=Text, sa_column_kwargs={"server_default": text("'manual'::text")}
    )


class ExchangeRateCreate(SQLModel):
    """Fields accepted when creating a ExchangeRate."""

    base_currency: str = Field(min_length=3, max_length=3)
    quote_currency: str = Field(min_length=3, max_length=3)
    rate: Decimal = Field(max_digits=20, decimal_places=8, gt=0)
    effective_date: dt.date
    source: str = "manual"


class ExchangeRateUpdate(SQLModel):
    """Fields accepted when patching a ExchangeRate (all optional)."""

    base_currency: str | None = Field(default=None, min_length=3, max_length=3)
    quote_currency: str | None = Field(default=None, min_length=3, max_length=3)
    rate: Decimal | None = Field(default=None, max_digits=20, decimal_places=8, gt=0)
    effective_date: dt.date | None = None
    source: str | None = None


class ExchangeRateRead(SQLModel):
    """Fields returned when reading a ExchangeRate."""

    id: UUID
    tenant_id: UUID
    base_currency: str
    quote_currency: str
    rate: Decimal
    effective_date: dt.date
    source: str
    created_at: dt.datetime
    updated_at: dt.datetime
    created_by: str | None
    updated_by: str | None
