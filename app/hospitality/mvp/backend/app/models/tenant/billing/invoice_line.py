"""InvoiceLine entity — table ``invoiceline``.

Tenant database, H. Folios, postings, invoices, end-of-day.

Invoices, credit notes, receipts.

Mirrors .ttest/contexts/schema-tenant.sql; the Alembic migration creates the table.
"""

from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import ForeignKeyConstraint, Text, UniqueConstraint, Uuid, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel

from app.crud.base_model import MIGRATION_ONLY, TenantRecord


class InvoiceLine(TenantRecord, table=True):
    """Invoices, credit notes, receipts."""

    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="invoiceline_tenant_id_id_key"),
        UniqueConstraint(
            "tenant_id",
            "invoice_id",
            "line_no",
            name="invoiceline_tenant_id_invoice_id_line_no_key",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "invoice_id"],
            ["invoice.tenant_id", "invoice.id"],
            name="invoiceline_tenant_id_invoice_id_fkey",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "folio_transaction_id"],
            ["foliotransaction.tenant_id", "foliotransaction.id"],
            name="invoiceline_tenant_id_folio_transaction_id_fkey",
        ),
        MIGRATION_ONLY,
    )

    invoice_id: UUID = Field(sa_type=Uuid)
    line_no: int = Field()
    folio_transaction_id: UUID | None = Field(default=None, sa_type=Uuid)
    description: str = Field(sa_type=Text)
    quantity: Decimal = Field(
        default=Decimal("1"),
        max_digits=10,
        decimal_places=2,
        sa_column_kwargs={"server_default": text("1")},
    )
    unit_price: Decimal = Field(max_digits=18, decimal_places=2)
    amount: Decimal = Field(max_digits=18, decimal_places=2)
    tax_amount: Decimal = Field(
        default=Decimal("0"),
        max_digits=18,
        decimal_places=2,
        sa_column_kwargs={"server_default": text("0")},
    )
    tax_breakdown: list[Any] = Field(
        default_factory=list,
        sa_type=JSONB,
        sa_column_kwargs={"server_default": text("'[]'::jsonb")},
    )


class InvoiceLineCreate(SQLModel):
    """Fields accepted when creating a InvoiceLine."""

    invoice_id: UUID
    line_no: int
    folio_transaction_id: UUID | None = None
    description: str
    quantity: Decimal = Field(default=Decimal("1"), max_digits=10, decimal_places=2)
    unit_price: Decimal = Field(max_digits=18, decimal_places=2)
    amount: Decimal = Field(max_digits=18, decimal_places=2)
    tax_amount: Decimal = Field(default=Decimal("0"), max_digits=18, decimal_places=2)
    tax_breakdown: list[Any] = Field(default_factory=list)


class InvoiceLineUpdate(SQLModel):
    """Fields accepted when patching a InvoiceLine (all optional)."""

    invoice_id: UUID | None = None
    line_no: int | None = None
    folio_transaction_id: UUID | None = None
    description: str | None = None
    quantity: Decimal | None = Field(default=None, max_digits=10, decimal_places=2)
    unit_price: Decimal | None = Field(default=None, max_digits=18, decimal_places=2)
    amount: Decimal | None = Field(default=None, max_digits=18, decimal_places=2)
    tax_amount: Decimal | None = Field(default=None, max_digits=18, decimal_places=2)
    tax_breakdown: list[Any] | None = None


class InvoiceLineRead(SQLModel):
    """Fields returned when reading a InvoiceLine."""

    id: UUID
    tenant_id: UUID
    invoice_id: UUID
    line_no: int
    folio_transaction_id: UUID | None
    description: str
    quantity: Decimal
    unit_price: Decimal
    amount: Decimal
    tax_amount: Decimal
    tax_breakdown: list[Any]
