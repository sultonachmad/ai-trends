"""SettlementLine entity — table ``settlementline``.

Tenant database, I. Payments.

Reconciliation and disputes.

Mirrors .ttest/contexts/schema-tenant.sql; the Alembic migration creates the table.
"""

from decimal import Decimal
from typing import Literal
from uuid import UUID

from sqlalchemy import CheckConstraint, ForeignKeyConstraint, Text, UniqueConstraint, Uuid, text
from sqlmodel import Field, SQLModel

from app.crud.base_model import MIGRATION_ONLY, TenantRecord

SettlementLineMatchStatus = Literal[
    "unmatched",
    "matched",
    "amount_mismatch",
    "ignored",
]


class SettlementLine(TenantRecord, table=True):
    """Reconciliation and disputes."""

    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="settlementline_tenant_id_id_key"),
        ForeignKeyConstraint(
            ["tenant_id", "settlement_id"],
            ["settlement.tenant_id", "settlement.id"],
            name="settlementline_tenant_id_settlement_id_fkey",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "payment_id"],
            ["payment.tenant_id", "payment.id"],
            name="settlementline_tenant_id_payment_id_fkey",
            ondelete="SET NULL (payment_id)",
        ),
        CheckConstraint(
            "match_status IN ('unmatched', 'matched', 'amount_mismatch', 'ignored')",
            name="settlementline_match_status_check",
        ),
        MIGRATION_ONLY,
    )

    settlement_id: UUID = Field(sa_type=Uuid)
    payment_id: UUID | None = Field(default=None, sa_type=Uuid)
    gateway_reference: str = Field(sa_type=Text)
    amount: Decimal = Field(max_digits=18, decimal_places=2)
    fee_amount: Decimal = Field(
        default=Decimal("0"),
        max_digits=18,
        decimal_places=2,
        sa_column_kwargs={"server_default": text("0")},
    )
    match_status: str = Field(
        default="unmatched",
        sa_type=Text,
        sa_column_kwargs={"server_default": text("'unmatched'::text")},
    )


class SettlementLineCreate(SQLModel):
    """Fields accepted when creating a SettlementLine."""

    settlement_id: UUID
    payment_id: UUID | None = None
    gateway_reference: str
    amount: Decimal = Field(max_digits=18, decimal_places=2)
    fee_amount: Decimal = Field(default=Decimal("0"), max_digits=18, decimal_places=2)
    match_status: SettlementLineMatchStatus = "unmatched"


class SettlementLineUpdate(SQLModel):
    """Fields accepted when patching a SettlementLine (all optional)."""

    settlement_id: UUID | None = None
    payment_id: UUID | None = None
    gateway_reference: str | None = None
    amount: Decimal | None = Field(default=None, max_digits=18, decimal_places=2)
    fee_amount: Decimal | None = Field(default=None, max_digits=18, decimal_places=2)
    match_status: SettlementLineMatchStatus | None = None


class SettlementLineRead(SQLModel):
    """Fields returned when reading a SettlementLine."""

    id: UUID
    tenant_id: UUID
    settlement_id: UUID
    payment_id: UUID | None
    gateway_reference: str
    amount: Decimal
    fee_amount: Decimal
    match_status: str
