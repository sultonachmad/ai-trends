"""AiUsage entity — table ``aiusage``.

Tenant database, S. AI assistant layer.

Per-call metering (high volume -> partition by month later).

Mirrors .ttest/contexts/schema-tenant.sql; the Alembic migration creates the table.
"""

import datetime as dt
from decimal import Decimal
from uuid import UUID

from sqlalchemy import CHAR, ForeignKeyConstraint, Index, Text, UniqueConstraint, Uuid, text
from sqlmodel import Field, SQLModel

from app.crud.base_model import MIGRATION_ONLY, TenantRecord, utc_datetime_field


class AiUsage(TenantRecord, table=True):
    """Per-call metering (high volume -> partition by month later)."""

    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="aiusage_tenant_id_id_key"),
        ForeignKeyConstraint(
            ["tenant_id", "property_id"],
            ["property.tenant_id", "property.id"],
            name="aiusage_tenant_id_property_id_fkey",
            ondelete="SET NULL (property_id)",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "suggestion_id"],
            ["aisuggestion.tenant_id", "aisuggestion.id"],
            name="aiusage_tenant_id_suggestion_id_fkey",
            ondelete="SET NULL (suggestion_id)",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "staff_member_id"],
            ["staffmember.tenant_id", "staffmember.id"],
            name="aiusage_tenant_id_staff_member_id_fkey",
            ondelete="SET NULL (staff_member_id)",
        ),
        Index("ix_aiusage_month", "tenant_id", "property_id", "occurred_at"),
        MIGRATION_ONLY,
    )

    property_id: UUID | None = Field(default=None, sa_type=Uuid)
    feature: str = Field(sa_type=Text)
    provider: str = Field(sa_type=Text)
    model: str = Field(sa_type=Text)
    input_tokens: int = Field(default=0, sa_column_kwargs={"server_default": text("0")})
    output_tokens: int = Field(default=0, sa_column_kwargs={"server_default": text("0")})
    cached_tokens: int = Field(default=0, sa_column_kwargs={"server_default": text("0")})
    cost_amount: Decimal = Field(
        default=Decimal("0"),
        max_digits=18,
        decimal_places=6,
        sa_column_kwargs={"server_default": text("0")},
    )
    currency: str = Field(
        default="IDR", sa_type=CHAR(3), sa_column_kwargs={"server_default": text("'IDR'::bpchar")}
    )
    latency_ms: int | None = Field(default=None)
    was_cache_hit: bool = Field(default=False, sa_column_kwargs={"server_default": text("false")})
    suggestion_id: UUID | None = Field(default=None, sa_type=Uuid)
    staff_member_id: UUID | None = Field(default=None, sa_type=Uuid)
    request_id: str | None = Field(default=None, sa_type=Text)
    occurred_at: dt.datetime = utc_datetime_field(
        nullable=False, default_now=True, server_default_now=True
    )  # type: ignore[assignment]


class AiUsageCreate(SQLModel):
    """Fields accepted when creating a AiUsage."""

    property_id: UUID | None = None
    feature: str
    provider: str
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    cached_tokens: int = 0
    cost_amount: Decimal = Field(default=Decimal("0"), max_digits=18, decimal_places=6)
    currency: str = Field(default="IDR", min_length=3, max_length=3)
    latency_ms: int | None = None
    was_cache_hit: bool = False
    suggestion_id: UUID | None = None
    staff_member_id: UUID | None = None
    request_id: str | None = None
    occurred_at: dt.datetime = Field(default_factory=lambda: dt.datetime.now(dt.UTC))


class AiUsageUpdate(SQLModel):
    """Fields accepted when patching a AiUsage (all optional)."""

    property_id: UUID | None = None
    feature: str | None = None
    provider: str | None = None
    model: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    cached_tokens: int | None = None
    cost_amount: Decimal | None = Field(default=None, max_digits=18, decimal_places=6)
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    latency_ms: int | None = None
    was_cache_hit: bool | None = None
    suggestion_id: UUID | None = None
    staff_member_id: UUID | None = None
    request_id: str | None = None
    occurred_at: dt.datetime | None = None


class AiUsageRead(SQLModel):
    """Fields returned when reading a AiUsage."""

    id: UUID
    tenant_id: UUID
    property_id: UUID | None
    feature: str
    provider: str
    model: str
    input_tokens: int
    output_tokens: int
    cached_tokens: int
    cost_amount: Decimal
    currency: str
    latency_ms: int | None
    was_cache_hit: bool
    suggestion_id: UUID | None
    staff_member_id: UUID | None
    request_id: str | None
    occurred_at: dt.datetime
