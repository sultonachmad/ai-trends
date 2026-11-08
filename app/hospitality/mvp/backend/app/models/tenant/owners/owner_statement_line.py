"""OwnerStatementLine entity — table ``ownerstatementline``.

Tenant database, N. Owners.

Owner accounting.

Mirrors .ttest/contexts/schema-tenant.sql; the Alembic migration creates the table.
"""

from decimal import Decimal
from typing import Literal
from uuid import UUID

from sqlalchemy import CheckConstraint, ForeignKeyConstraint, Text, UniqueConstraint, Uuid
from sqlmodel import Field, SQLModel

from app.crud.base_model import MIGRATION_ONLY, TenantRecord

OwnerStatementLineLineKind = Literal[
    "revenue",
    "commission",
    "ota_commission",
    "cleaning",
    "maintenance",
    "utility",
    "expense",
    "adjustment",
    "owner_stay",
    "withholding_tax",
]


class OwnerStatementLine(TenantRecord, table=True):
    """Owner accounting."""

    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="ownerstatementline_tenant_id_id_key"),
        ForeignKeyConstraint(
            ["tenant_id", "statement_id"],
            ["ownerstatement.tenant_id", "ownerstatement.id"],
            name="ownerstatementline_tenant_id_statement_id_fkey",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "unit_id"],
            ["unit.tenant_id", "unit.id"],
            name="ownerstatementline_tenant_id_unit_id_fkey",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "reservation_id"],
            ["reservation.tenant_id", "reservation.id"],
            name="ownerstatementline_tenant_id_reservation_id_fkey",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "work_order_id"],
            ["workorder.tenant_id", "workorder.id"],
            name="ownerstatementline_tenant_id_work_order_id_fkey",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "receipt_document_id"],
            ["document.tenant_id", "document.id"],
            name="ownerstatementline_tenant_id_receipt_document_id_fkey",
            ondelete="SET NULL (receipt_document_id)",
        ),
        CheckConstraint(
            (
                "line_kind IN ('revenue', 'commission', 'ota_commission', 'cleaning', "
                "'maintenance', 'utility', 'expense', 'adjustment', 'owner_stay', "
                "'withholding_tax')"
            ),
            name="ownerstatementline_line_kind_check",
        ),
        MIGRATION_ONLY,
    )

    statement_id: UUID = Field(sa_type=Uuid)
    line_kind: str = Field(sa_type=Text)
    unit_id: UUID | None = Field(default=None, sa_type=Uuid)
    reservation_id: UUID | None = Field(default=None, sa_type=Uuid)
    work_order_id: UUID | None = Field(default=None, sa_type=Uuid)
    description: str = Field(sa_type=Text)
    amount: Decimal = Field(
        max_digits=18, decimal_places=2, description="signed: revenue +, deductions −"
    )
    receipt_document_id: UUID | None = Field(default=None, sa_type=Uuid)


class OwnerStatementLineCreate(SQLModel):
    """Fields accepted when creating a OwnerStatementLine."""

    statement_id: UUID
    line_kind: OwnerStatementLineLineKind
    unit_id: UUID | None = None
    reservation_id: UUID | None = None
    work_order_id: UUID | None = None
    description: str
    amount: Decimal = Field(max_digits=18, decimal_places=2)
    receipt_document_id: UUID | None = None


class OwnerStatementLineUpdate(SQLModel):
    """Fields accepted when patching a OwnerStatementLine (all optional)."""

    statement_id: UUID | None = None
    line_kind: OwnerStatementLineLineKind | None = None
    unit_id: UUID | None = None
    reservation_id: UUID | None = None
    work_order_id: UUID | None = None
    description: str | None = None
    amount: Decimal | None = Field(default=None, max_digits=18, decimal_places=2)
    receipt_document_id: UUID | None = None


class OwnerStatementLineRead(SQLModel):
    """Fields returned when reading a OwnerStatementLine."""

    id: UUID
    tenant_id: UUID
    statement_id: UUID
    line_kind: str
    unit_id: UUID | None
    reservation_id: UUID | None
    work_order_id: UUID | None
    description: str
    amount: Decimal
    receipt_document_id: UUID | None
