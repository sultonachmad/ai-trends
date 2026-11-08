"""BankStatementLine entity — table ``bankstatementline``.

Tenant database, I. Payments.

Imported bank statement lines (manual transfers without VA).

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

BankStatementLineMatchStatus = Literal[
    "unmatched",
    "matched",
    "ignored",
]


class BankStatementLine(TenantEntity, table=True):
    """Imported bank statement lines (manual transfers without VA)."""

    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="bankstatementline_tenant_id_id_key"),
        ForeignKeyConstraint(
            ["tenant_id", "property_id"],
            ["property.tenant_id", "property.id"],
            name="bankstatementline_tenant_id_property_id_fkey",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "source_document_id"],
            ["document.tenant_id", "document.id"],
            name="bankstatementline_tenant_id_source_document_id_fkey",
            ondelete="SET NULL (source_document_id)",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "matched_payment_id"],
            ["payment.tenant_id", "payment.id"],
            name="bankstatementline_tenant_id_matched_payment_id_fkey",
            ondelete="SET NULL (matched_payment_id)",
        ),
        CheckConstraint(
            "match_status IN ('unmatched', 'matched', 'ignored')",
            name="bankstatementline_match_status_check",
        ),
        MIGRATION_ONLY,
    )

    property_id: UUID = Field(sa_type=Uuid)
    bank_code: str = Field(sa_type=Text, description="'BCA','MANDIRI','BRI','BNI'")
    account_masked: str = Field(sa_type=Text)
    booked_on: dt.date = Field()
    amount: Decimal = Field(max_digits=18, decimal_places=2)
    currency: str = Field(
        default="IDR", sa_type=CHAR(3), sa_column_kwargs={"server_default": text("'IDR'::bpchar")}
    )
    description: str | None = Field(default=None, sa_type=Text)
    reference: str | None = Field(default=None, sa_type=Text)
    source_document_id: UUID | None = Field(default=None, sa_type=Uuid)
    matched_payment_id: UUID | None = Field(default=None, sa_type=Uuid)
    match_status: str = Field(
        default="unmatched",
        sa_type=Text,
        sa_column_kwargs={"server_default": text("'unmatched'::text")},
    )


class BankStatementLineCreate(SQLModel):
    """Fields accepted when creating a BankStatementLine."""

    property_id: UUID
    bank_code: str
    account_masked: str
    booked_on: dt.date
    amount: Decimal = Field(max_digits=18, decimal_places=2)
    currency: str = Field(default="IDR", min_length=3, max_length=3)
    description: str | None = None
    reference: str | None = None
    source_document_id: UUID | None = None
    matched_payment_id: UUID | None = None
    match_status: BankStatementLineMatchStatus = "unmatched"


class BankStatementLineUpdate(SQLModel):
    """Fields accepted when patching a BankStatementLine (all optional)."""

    property_id: UUID | None = None
    bank_code: str | None = None
    account_masked: str | None = None
    booked_on: dt.date | None = None
    amount: Decimal | None = Field(default=None, max_digits=18, decimal_places=2)
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    description: str | None = None
    reference: str | None = None
    source_document_id: UUID | None = None
    matched_payment_id: UUID | None = None
    match_status: BankStatementLineMatchStatus | None = None


class BankStatementLineRead(SQLModel):
    """Fields returned when reading a BankStatementLine."""

    id: UUID
    tenant_id: UUID
    property_id: UUID
    bank_code: str
    account_masked: str
    booked_on: dt.date
    amount: Decimal
    currency: str
    description: str | None
    reference: str | None
    source_document_id: UUID | None
    matched_payment_id: UUID | None
    match_status: str
    created_at: dt.datetime
    updated_at: dt.datetime
    created_by: str | None
    updated_by: str | None
