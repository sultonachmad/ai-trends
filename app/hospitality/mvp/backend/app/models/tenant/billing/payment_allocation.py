"""PaymentAllocation entity — table ``paymentallocation``.

Tenant database, H. Folios, postings, invoices, end-of-day.

AR: allocate payments to issued invoices (city ledger).

Mirrors .ttest/contexts/schema-tenant.sql; the Alembic migration creates the table.
"""

import datetime as dt
from decimal import Decimal
from uuid import UUID

from sqlalchemy import CheckConstraint, ForeignKeyConstraint, Text, UniqueConstraint, Uuid
from sqlmodel import Field, SQLModel

from app.crud.base_model import MIGRATION_ONLY, TenantRecord, utc_datetime_field


class PaymentAllocation(TenantRecord, table=True):
    """AR: allocate payments to issued invoices (city ledger)."""

    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="paymentallocation_tenant_id_id_key"),
        UniqueConstraint(
            "tenant_id",
            "payment_id",
            "invoice_id",
            name="paymentallocation_tenant_id_payment_id_invoice_id_key",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "payment_id"],
            ["payment.tenant_id", "payment.id"],
            name="paymentallocation_tenant_id_payment_id_fkey",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "invoice_id"],
            ["invoice.tenant_id", "invoice.id"],
            name="paymentallocation_tenant_id_invoice_id_fkey",
        ),
        CheckConstraint("(amount > (0)::numeric)", name="paymentallocation_amount_check"),
        MIGRATION_ONLY,
    )

    payment_id: UUID = Field(sa_type=Uuid)
    invoice_id: UUID = Field(sa_type=Uuid)
    amount: Decimal = Field(max_digits=18, decimal_places=2)
    allocated_at: dt.datetime = utc_datetime_field(
        nullable=False, default_now=True, server_default_now=True
    )  # type: ignore[assignment]
    allocated_by: str | None = Field(default=None, sa_type=Text)


class PaymentAllocationCreate(SQLModel):
    """Fields accepted when creating a PaymentAllocation."""

    payment_id: UUID
    invoice_id: UUID
    amount: Decimal = Field(max_digits=18, decimal_places=2, gt=0)
    allocated_at: dt.datetime = Field(default_factory=lambda: dt.datetime.now(dt.UTC))
    allocated_by: str | None = None


class PaymentAllocationUpdate(SQLModel):
    """Fields accepted when patching a PaymentAllocation (all optional)."""

    payment_id: UUID | None = None
    invoice_id: UUID | None = None
    amount: Decimal | None = Field(default=None, max_digits=18, decimal_places=2, gt=0)
    allocated_at: dt.datetime | None = None
    allocated_by: str | None = None


class PaymentAllocationRead(SQLModel):
    """Fields returned when reading a PaymentAllocation."""

    id: UUID
    tenant_id: UUID
    payment_id: UUID
    invoice_id: UUID
    amount: Decimal
    allocated_at: dt.datetime
    allocated_by: str | None
