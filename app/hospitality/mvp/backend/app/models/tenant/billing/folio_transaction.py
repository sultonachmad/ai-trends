"""FolioTransaction entity — table ``foliotransaction``.

Tenant database, H. Folios, postings, invoices, end-of-day.

Ledger postings. APPEND-ONLY: corrections are new rows (void / adjustment).

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
    Index,
    Text,
    UniqueConstraint,
    Uuid,
    text,
)
from sqlmodel import Field, SQLModel

from app.crud.base_model import MIGRATION_ONLY, TenantRecord, utc_datetime_field

FolioTransactionKind = Literal[
    "charge",
    "tax",
    "payment",
    "refund",
    "deposit",
    "adjustment",
    "void",
    "transfer_in",
    "transfer_out",
]
FolioTransactionSource = Literal[
    "night_audit",
    "manual",
    "pos",
    "channel",
    "payment",
    "system",
    "import",
]


class FolioTransaction(TenantRecord, table=True):
    """Ledger postings. APPEND-ONLY: corrections are new rows (void / adjustment)."""

    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="foliotransaction_tenant_id_id_key"),
        ForeignKeyConstraint(
            ["tenant_id", "folio_id"],
            ["folio.tenant_id", "folio.id"],
            name="foliotransaction_tenant_id_folio_id_fkey",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "property_id"],
            ["property.tenant_id", "property.id"],
            name="foliotransaction_tenant_id_property_id_fkey",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "transaction_code_id"],
            ["transactioncode.tenant_id", "transactioncode.id"],
            name="foliotransaction_tenant_id_transaction_code_id_fkey",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "parent_transaction_id"],
            ["foliotransaction.tenant_id", "foliotransaction.id"],
            name="foliotransaction_tenant_id_parent_transaction_id_fkey",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "reverses_transaction_id"],
            ["foliotransaction.tenant_id", "foliotransaction.id"],
            name="foliotransaction_tenant_id_reverses_transaction_id_fkey",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "transfer_counterpart_id"],
            ["foliotransaction.tenant_id", "foliotransaction.id"],
            name="foliotransaction_tenant_id_transfer_counterpart_id_fkey",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "tax_rule_id"],
            ["taxrule.tenant_id", "taxrule.id"],
            name="foliotransaction_tenant_id_tax_rule_id_fkey",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "reservation_daily_rate_id"],
            ["reservationdailyrate.tenant_id", "reservationdailyrate.id"],
            name="foliotransaction_tenant_id_reservation_daily_rate_id_fkey",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "reservation_product_id"],
            ["reservationproduct.tenant_id", "reservationproduct.id"],
            name="foliotransaction_tenant_id_reservation_product_id_fkey",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "payment_id"],
            ["payment.tenant_id", "payment.id"],
            name="foliotransaction_tenant_id_payment_id_fkey",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "reason_code_id"],
            ["reasoncode.tenant_id", "reasoncode.id"],
            name="foliotransaction_tenant_id_reason_code_id_fkey",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "cashier_shift_id"],
            ["cashiershift.tenant_id", "cashiershift.id"],
            name="foliotransaction_tenant_id_cashier_shift_id_fkey",
        ),
        CheckConstraint(
            (
                "kind IN ('charge', 'tax', 'payment', 'refund', 'deposit', 'adjustment', "
                "'void', 'transfer_in', 'transfer_out')"
            ),
            name="foliotransaction_kind_check",
        ),
        CheckConstraint(
            (
                "source IN ('night_audit', 'manual', 'pos', 'channel', 'payment', "
                "'system', 'import')"
            ),
            name="foliotransaction_source_check",
        ),
        Index("ix_foliotransaction_folio", "tenant_id", "folio_id", "posted_at"),
        Index("ix_foliotransaction_bizdate", "tenant_id", "property_id", "business_date"),
        Index(
            "ux_foliotransaction_dailyrate",
            "tenant_id",
            "reservation_daily_rate_id",
            unique=True,
            postgresql_where=text(
                "(reservation_daily_rate_id IS NOT NULL) AND (kind = 'charge'::text)"
            ),
        ),
        MIGRATION_ONLY,
    )

    folio_id: UUID = Field(sa_type=Uuid)
    property_id: UUID = Field(sa_type=Uuid)
    business_date: dt.date = Field()
    posted_at: dt.datetime = utc_datetime_field(
        nullable=False, default_now=True, server_default_now=True
    )  # type: ignore[assignment]
    transaction_code_id: UUID = Field(sa_type=Uuid)
    kind: str = Field(sa_type=Text)
    description: str = Field(sa_type=Text)
    quantity: Decimal = Field(
        default=Decimal("1"),
        max_digits=10,
        decimal_places=2,
        sa_column_kwargs={"server_default": text("1")},
    )
    unit_price: Decimal | None = Field(default=None, max_digits=18, decimal_places=2)
    amount: Decimal = Field(
        max_digits=18, decimal_places=2, description="signed: charges +, payments −"
    )
    currency: str = Field(
        default="IDR", sa_type=CHAR(3), sa_column_kwargs={"server_default": text("'IDR'::bpchar")}
    )
    parent_transaction_id: UUID | None = Field(
        default=None, sa_type=Uuid, description="tax/service line -> its charge"
    )
    reverses_transaction_id: UUID | None = Field(
        default=None, sa_type=Uuid, description="void/adjustment target"
    )
    transfer_counterpart_id: UUID | None = Field(default=None, sa_type=Uuid)
    tax_rule_id: UUID | None = Field(default=None, sa_type=Uuid)
    reservation_daily_rate_id: UUID | None = Field(default=None, sa_type=Uuid)
    reservation_product_id: UUID | None = Field(default=None, sa_type=Uuid)
    payment_id: UUID | None = Field(default=None, sa_type=Uuid)
    reason_code_id: UUID | None = Field(default=None, sa_type=Uuid)
    cashier_shift_id: UUID | None = Field(default=None, sa_type=Uuid)
    source: str = Field(sa_type=Text)
    source_ref: str | None = Field(default=None, sa_type=Text)
    posted_by: str | None = Field(default=None, sa_type=Text)


class FolioTransactionCreate(SQLModel):
    """Fields accepted when creating a FolioTransaction."""

    folio_id: UUID
    property_id: UUID
    business_date: dt.date
    posted_at: dt.datetime = Field(default_factory=lambda: dt.datetime.now(dt.UTC))
    transaction_code_id: UUID
    kind: FolioTransactionKind
    description: str
    quantity: Decimal = Field(default=Decimal("1"), max_digits=10, decimal_places=2)
    unit_price: Decimal | None = Field(default=None, max_digits=18, decimal_places=2)
    amount: Decimal = Field(max_digits=18, decimal_places=2)
    currency: str = Field(default="IDR", min_length=3, max_length=3)
    parent_transaction_id: UUID | None = None
    reverses_transaction_id: UUID | None = None
    transfer_counterpart_id: UUID | None = None
    tax_rule_id: UUID | None = None
    reservation_daily_rate_id: UUID | None = None
    reservation_product_id: UUID | None = None
    payment_id: UUID | None = None
    reason_code_id: UUID | None = None
    cashier_shift_id: UUID | None = None
    source: FolioTransactionSource
    source_ref: str | None = None
    posted_by: str | None = None


class FolioTransactionUpdate(SQLModel):
    """
    Patch shape for a FolioTransaction. The table is append-only (the DB rejects UPDATE); post a
    reversing entry instead.
    """

    folio_id: UUID | None = None
    property_id: UUID | None = None
    business_date: dt.date | None = None
    posted_at: dt.datetime | None = None
    transaction_code_id: UUID | None = None
    kind: FolioTransactionKind | None = None
    description: str | None = None
    quantity: Decimal | None = Field(default=None, max_digits=10, decimal_places=2)
    unit_price: Decimal | None = Field(default=None, max_digits=18, decimal_places=2)
    amount: Decimal | None = Field(default=None, max_digits=18, decimal_places=2)
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    parent_transaction_id: UUID | None = None
    reverses_transaction_id: UUID | None = None
    transfer_counterpart_id: UUID | None = None
    tax_rule_id: UUID | None = None
    reservation_daily_rate_id: UUID | None = None
    reservation_product_id: UUID | None = None
    payment_id: UUID | None = None
    reason_code_id: UUID | None = None
    cashier_shift_id: UUID | None = None
    source: FolioTransactionSource | None = None
    source_ref: str | None = None
    posted_by: str | None = None


class FolioTransactionRead(SQLModel):
    """Fields returned when reading a FolioTransaction."""

    id: UUID
    tenant_id: UUID
    folio_id: UUID
    property_id: UUID
    business_date: dt.date
    posted_at: dt.datetime
    transaction_code_id: UUID
    kind: str
    description: str
    quantity: Decimal
    unit_price: Decimal | None
    amount: Decimal
    currency: str
    parent_transaction_id: UUID | None
    reverses_transaction_id: UUID | None
    transfer_counterpart_id: UUID | None
    tax_rule_id: UUID | None
    reservation_daily_rate_id: UUID | None
    reservation_product_id: UUID | None
    payment_id: UUID | None
    reason_code_id: UUID | None
    cashier_shift_id: UUID | None
    source: str
    source_ref: str | None
    posted_by: str | None
