"""Invoice entity — table ``invoice``.

Tenant database, H. Folios, postings, invoices, end-of-day.

Invoices, credit notes, receipts.

Mirrors .ttest/contexts/schema-tenant.sql; the Alembic migration creates the table.
"""

import datetime as dt
from decimal import Decimal
from typing import Any, Literal
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
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel

from app.crud.base_model import MIGRATION_ONLY, TenantEntity, utc_datetime_field

InvoiceKind = Literal[
    "invoice",
    "credit_note",
    "deposit_invoice",
    "receipt",
]
InvoiceStatus = Literal[
    "draft",
    "issued",
    "cancelled_draft",
]


class Invoice(TenantEntity, table=True):
    """Invoices, credit notes, receipts."""

    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="invoice_tenant_id_id_key"),
        UniqueConstraint(
            "tenant_id",
            "legal_entity_id",
            "series",
            "number",
            name="invoice_tenant_id_legal_entity_id_series_number_key",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "legal_entity_id"],
            ["legalentity.tenant_id", "legalentity.id"],
            name="invoice_tenant_id_legal_entity_id_fkey",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "property_id"],
            ["property.tenant_id", "property.id"],
            name="invoice_tenant_id_property_id_fkey",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "folio_id"],
            ["folio.tenant_id", "folio.id"],
            name="invoice_tenant_id_folio_id_fkey",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "credit_note_for_invoice_id"],
            ["invoice.tenant_id", "invoice.id"],
            name="invoice_tenant_id_credit_note_for_invoice_id_fkey",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "account_id"],
            ["account.tenant_id", "account.id"],
            name="invoice_tenant_id_account_id_fkey",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "guest_id"],
            ["guest.tenant_id", "guest.id"],
            name="invoice_tenant_id_guest_id_fkey",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "pdf_document_id"],
            ["document.tenant_id", "document.id"],
            name="invoice_tenant_id_pdf_document_id_fkey",
        ),
        CheckConstraint(
            "kind IN ('invoice', 'credit_note', 'deposit_invoice', 'receipt')",
            name="invoice_kind_check",
        ),
        CheckConstraint(
            "status IN ('draft', 'issued', 'cancelled_draft')", name="invoice_status_check"
        ),
        CheckConstraint(
            ("((status <> 'issued'::text) OR ((number IS NOT NULL) AND (issued_at IS NOT NULL)))"),
            name="invoice_check",
        ),
        CheckConstraint(
            ("((kind = 'credit_note'::text) = (credit_note_for_invoice_id IS NOT NULL))"),
            name="invoice_check1",
        ),
        Index(
            "ix_invoice_account_open",
            "tenant_id",
            "account_id",
            postgresql_where=text("(status = 'issued'::text) AND (paid_amount < total)"),
        ),
        MIGRATION_ONLY,
    )

    legal_entity_id: UUID = Field(sa_type=Uuid)
    property_id: UUID = Field(sa_type=Uuid)
    folio_id: UUID = Field(sa_type=Uuid)
    kind: str = Field(sa_type=Text)
    series: str = Field(sa_type=Text)
    number: str | None = Field(default=None, sa_type=Text, description="assigned at issue")
    credit_note_for_invoice_id: UUID | None = Field(default=None, sa_type=Uuid)
    status: str = Field(
        default="draft", sa_type=Text, sa_column_kwargs={"server_default": text("'draft'::text")}
    )
    business_date: dt.date | None = Field(default=None)
    issued_at: dt.datetime | None = utc_datetime_field(nullable=True)  # type: ignore[assignment]
    account_id: UUID | None = Field(default=None, sa_type=Uuid)
    guest_id: UUID | None = Field(default=None, sa_type=Uuid)
    bill_to: dict[str, Any] = Field(
        default_factory=dict,
        sa_type=JSONB,
        sa_column_kwargs={"server_default": text("'{}'::jsonb")},
        description="addressee snapshot (name, tax id, address)",
    )
    currency: str = Field(
        default="IDR", sa_type=CHAR(3), sa_column_kwargs={"server_default": text("'IDR'::bpchar")}
    )
    subtotal: Decimal = Field(
        default=Decimal("0"),
        max_digits=18,
        decimal_places=2,
        sa_column_kwargs={"server_default": text("0")},
    )
    tax_total: Decimal = Field(
        default=Decimal("0"),
        max_digits=18,
        decimal_places=2,
        sa_column_kwargs={"server_default": text("0")},
    )
    total: Decimal = Field(
        default=Decimal("0"),
        max_digits=18,
        decimal_places=2,
        sa_column_kwargs={"server_default": text("0")},
    )
    due_on: dt.date | None = Field(default=None)
    paid_amount: Decimal = Field(
        default=Decimal("0"),
        max_digits=18,
        decimal_places=2,
        sa_column_kwargs={"server_default": text("0")},
    )
    fiscal_reference: str | None = Field(
        default=None, sa_type=Text, description="e-invoice / e-Faktur ref when applicable"
    )
    pdf_document_id: UUID | None = Field(default=None, sa_type=Uuid)


class InvoiceCreate(SQLModel):
    """Fields accepted when creating a Invoice."""

    legal_entity_id: UUID
    property_id: UUID
    folio_id: UUID
    kind: InvoiceKind
    series: str
    number: str | None = None
    credit_note_for_invoice_id: UUID | None = None
    status: InvoiceStatus = "draft"
    business_date: dt.date | None = None
    issued_at: dt.datetime | None = None
    account_id: UUID | None = None
    guest_id: UUID | None = None
    bill_to: dict[str, Any] = Field(default_factory=dict)
    currency: str = Field(default="IDR", min_length=3, max_length=3)
    subtotal: Decimal = Field(default=Decimal("0"), max_digits=18, decimal_places=2)
    tax_total: Decimal = Field(default=Decimal("0"), max_digits=18, decimal_places=2)
    total: Decimal = Field(default=Decimal("0"), max_digits=18, decimal_places=2)
    due_on: dt.date | None = None
    paid_amount: Decimal = Field(default=Decimal("0"), max_digits=18, decimal_places=2)
    fiscal_reference: str | None = None
    pdf_document_id: UUID | None = None


class InvoiceUpdate(SQLModel):
    """Fields accepted when patching a Invoice (all optional)."""

    legal_entity_id: UUID | None = None
    property_id: UUID | None = None
    folio_id: UUID | None = None
    kind: InvoiceKind | None = None
    series: str | None = None
    number: str | None = None
    credit_note_for_invoice_id: UUID | None = None
    status: InvoiceStatus | None = None
    business_date: dt.date | None = None
    issued_at: dt.datetime | None = None
    account_id: UUID | None = None
    guest_id: UUID | None = None
    bill_to: dict[str, Any] | None = None
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    subtotal: Decimal | None = Field(default=None, max_digits=18, decimal_places=2)
    tax_total: Decimal | None = Field(default=None, max_digits=18, decimal_places=2)
    total: Decimal | None = Field(default=None, max_digits=18, decimal_places=2)
    due_on: dt.date | None = None
    paid_amount: Decimal | None = Field(default=None, max_digits=18, decimal_places=2)
    fiscal_reference: str | None = None
    pdf_document_id: UUID | None = None


class InvoiceRead(SQLModel):
    """Fields returned when reading a Invoice."""

    id: UUID
    tenant_id: UUID
    legal_entity_id: UUID
    property_id: UUID
    folio_id: UUID
    kind: str
    series: str
    number: str | None
    credit_note_for_invoice_id: UUID | None
    status: str
    business_date: dt.date | None
    issued_at: dt.datetime | None
    account_id: UUID | None
    guest_id: UUID | None
    bill_to: dict[str, Any]
    currency: str
    subtotal: Decimal
    tax_total: Decimal
    total: Decimal
    due_on: dt.date | None
    paid_amount: Decimal
    fiscal_reference: str | None
    pdf_document_id: UUID | None
    created_at: dt.datetime
    updated_at: dt.datetime
    created_by: str | None
    updated_by: str | None
