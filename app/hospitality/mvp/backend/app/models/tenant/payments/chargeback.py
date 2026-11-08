"""Chargeback entity — table ``chargeback``.

Tenant database, I. Payments.

Reconciliation and disputes.

Mirrors .ttest/contexts/schema-tenant.sql; the Alembic migration creates the table.
"""

import datetime as dt
from decimal import Decimal
from typing import Literal
from uuid import UUID

from sqlalchemy import CheckConstraint, ForeignKeyConstraint, Text, UniqueConstraint, Uuid, text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlmodel import Field, SQLModel

from app.crud.base_model import MIGRATION_ONLY, TenantEntity

ChargebackStatus = Literal[
    "open",
    "evidence_submitted",
    "won",
    "lost",
    "accepted",
]


class Chargeback(TenantEntity, table=True):
    """Reconciliation and disputes."""

    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="chargeback_tenant_id_id_key"),
        ForeignKeyConstraint(
            ["tenant_id", "payment_id"],
            ["payment.tenant_id", "payment.id"],
            name="chargeback_tenant_id_payment_id_fkey",
        ),
        CheckConstraint(
            "status IN ('open', 'evidence_submitted', 'won', 'lost', 'accepted')",
            name="chargeback_status_check",
        ),
        MIGRATION_ONLY,
    )

    payment_id: UUID = Field(sa_type=Uuid)
    reason_code: str | None = Field(default=None, sa_type=Text)
    amount: Decimal = Field(max_digits=18, decimal_places=2)
    status: str = Field(
        default="open", sa_type=Text, sa_column_kwargs={"server_default": text("'open'::text")}
    )
    respond_by: dt.date | None = Field(default=None)
    evidence_document_ids: list[UUID] = Field(
        default_factory=list,
        sa_type=ARRAY(Uuid),
        sa_column_kwargs={"server_default": text("'{}'::uuid[]")},
    )
    outcome_note: str | None = Field(default=None, sa_type=Text)


class ChargebackCreate(SQLModel):
    """Fields accepted when creating a Chargeback."""

    payment_id: UUID
    reason_code: str | None = None
    amount: Decimal = Field(max_digits=18, decimal_places=2)
    status: ChargebackStatus = "open"
    respond_by: dt.date | None = None
    evidence_document_ids: list[UUID] = Field(default_factory=list)
    outcome_note: str | None = None


class ChargebackUpdate(SQLModel):
    """Fields accepted when patching a Chargeback (all optional)."""

    payment_id: UUID | None = None
    reason_code: str | None = None
    amount: Decimal | None = Field(default=None, max_digits=18, decimal_places=2)
    status: ChargebackStatus | None = None
    respond_by: dt.date | None = None
    evidence_document_ids: list[UUID] | None = None
    outcome_note: str | None = None


class ChargebackRead(SQLModel):
    """Fields returned when reading a Chargeback."""

    id: UUID
    tenant_id: UUID
    payment_id: UUID
    reason_code: str | None
    amount: Decimal
    status: str
    respond_by: dt.date | None
    evidence_document_ids: list[UUID]
    outcome_note: str | None
    created_at: dt.datetime
    updated_at: dt.datetime
    created_by: str | None
    updated_by: str | None
