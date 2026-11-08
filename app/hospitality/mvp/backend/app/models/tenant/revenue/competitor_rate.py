"""CompetitorRate entity — table ``competitorrate``.

Tenant database, R. Revenue management.

Competitor set and shopped rates.

Mirrors .ttest/contexts/schema-tenant.sql; the Alembic migration creates the table.
"""

import datetime as dt
from decimal import Decimal
from uuid import UUID

from sqlalchemy import (
    CHAR,
    ForeignKeyConstraint,
    Index,
    SmallInteger,
    Text,
    UniqueConstraint,
    Uuid,
    text,
)
from sqlmodel import Field, SQLModel

from app.crud.base_model import MIGRATION_ONLY, TenantRecord, utc_datetime_field


class CompetitorRate(TenantRecord, table=True):
    """Competitor set and shopped rates."""

    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="competitorrate_tenant_id_id_key"),
        ForeignKeyConstraint(
            ["tenant_id", "competitor_id"],
            ["competitor.tenant_id", "competitor.id"],
            name="competitorrate_tenant_id_competitor_id_fkey",
            ondelete="CASCADE",
        ),
        Index(
            "ix_competitorrate_lookup",
            "tenant_id",
            "competitor_id",
            "stay_date",
            text("captured_at DESC"),
        ),
        MIGRATION_ONLY,
    )

    competitor_id: UUID = Field(sa_type=Uuid)
    stay_date: dt.date = Field()
    captured_at: dt.datetime = utc_datetime_field(nullable=False)  # type: ignore[assignment]
    room_label: str | None = Field(default=None, sa_type=Text)
    los: int = Field(
        default=1, sa_type=SmallInteger, sa_column_kwargs={"server_default": text("1")}
    )
    amount: Decimal | None = Field(default=None, max_digits=18, decimal_places=2)
    currency: str = Field(
        default="IDR", sa_type=CHAR(3), sa_column_kwargs={"server_default": text("'IDR'::bpchar")}
    )
    is_sold_out: bool = Field(default=False, sa_column_kwargs={"server_default": text("false")})
    source: str = Field(sa_type=Text)


class CompetitorRateCreate(SQLModel):
    """Fields accepted when creating a CompetitorRate."""

    competitor_id: UUID
    stay_date: dt.date
    captured_at: dt.datetime
    room_label: str | None = None
    los: int = 1
    amount: Decimal | None = Field(default=None, max_digits=18, decimal_places=2)
    currency: str = Field(default="IDR", min_length=3, max_length=3)
    is_sold_out: bool = False
    source: str


class CompetitorRateUpdate(SQLModel):
    """Fields accepted when patching a CompetitorRate (all optional)."""

    competitor_id: UUID | None = None
    stay_date: dt.date | None = None
    captured_at: dt.datetime | None = None
    room_label: str | None = None
    los: int | None = None
    amount: Decimal | None = Field(default=None, max_digits=18, decimal_places=2)
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    is_sold_out: bool | None = None
    source: str | None = None


class CompetitorRateRead(SQLModel):
    """Fields returned when reading a CompetitorRate."""

    id: UUID
    tenant_id: UUID
    competitor_id: UUID
    stay_date: dt.date
    captured_at: dt.datetime
    room_label: str | None
    los: int
    amount: Decimal | None
    currency: str
    is_sold_out: bool
    source: str
