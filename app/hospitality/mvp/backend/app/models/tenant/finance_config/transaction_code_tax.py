"""TransactionCodeTax entity — table ``transactioncodetax``.

Tenant database, D. Finance configuration.

Posting codes → department, GL, taxes.

Mirrors .ttest/contexts/schema-tenant.sql; the Alembic migration creates the table.
"""

from uuid import UUID

from sqlalchemy import ForeignKeyConstraint, Uuid, text
from sqlmodel import Field, SQLModel

from app.crud.base_model import MIGRATION_ONLY


class TransactionCodeTax(SQLModel, table=True):
    """Posting codes → department, GL, taxes."""

    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "transaction_code_id"],
            ["transactioncode.tenant_id", "transactioncode.id"],
            name="transactioncodetax_tenant_id_transaction_code_id_fkey",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "tax_rule_id"],
            ["taxrule.tenant_id", "taxrule.id"],
            name="transactioncodetax_tenant_id_tax_rule_id_fkey",
            ondelete="CASCADE",
        ),
        MIGRATION_ONLY,
    )

    tenant_id: UUID = Field(primary_key=True, sa_type=Uuid)
    transaction_code_id: UUID = Field(primary_key=True, sa_type=Uuid)
    tax_rule_id: UUID = Field(primary_key=True, sa_type=Uuid)
    sequence: int = Field(default=0, sa_column_kwargs={"server_default": text("0")})


class TransactionCodeTaxCreate(SQLModel):
    """Fields accepted when creating a TransactionCodeTax."""

    transaction_code_id: UUID
    tax_rule_id: UUID
    sequence: int = 0


class TransactionCodeTaxUpdate(SQLModel):
    """Fields accepted when patching a TransactionCodeTax (all optional)."""

    sequence: int | None = None


class TransactionCodeTaxRead(SQLModel):
    """Fields returned when reading a TransactionCodeTax."""

    tenant_id: UUID
    transaction_code_id: UUID
    tax_rule_id: UUID
    sequence: int
