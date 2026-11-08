"""TransactionCode entity — table ``transactioncode``.

Tenant database, D. Finance configuration.

Posting codes → department, GL, taxes.

Mirrors .ttest/contexts/schema-tenant.sql; the Alembic migration creates the table.
"""

import datetime as dt
from typing import Literal
from uuid import UUID

from sqlalchemy import CheckConstraint, ForeignKeyConstraint, Text, UniqueConstraint, Uuid, text
from sqlmodel import Field, SQLModel

from app.crud.base_model import MIGRATION_ONLY, TenantEntity

TransactionCodeKind = Literal[
    "charge",
    "payment",
    "tax",
    "fee",
    "deposit",
    "adjustment",
    "transfer",
    "commission",
]
TransactionCodeDepartment = Literal[
    "rooms",
    "fnb",
    "spa",
    "activities",
    "retail",
    "parking",
    "utilities",
    "other",
]


class TransactionCode(TenantEntity, table=True):
    """Posting codes → department, GL, taxes."""

    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="transactioncode_tenant_id_id_key"),
        UniqueConstraint(
            "tenant_id",
            "property_id",
            "code",
            name="transactioncode_tenant_id_property_id_code_key",
            postgresql_nulls_not_distinct=True,
        ),
        ForeignKeyConstraint(
            ["tenant_id", "property_id"],
            ["property.tenant_id", "property.id"],
            name="transactioncode_tenant_id_property_id_fkey",
            ondelete="CASCADE",
        ),
        CheckConstraint(
            (
                "kind IN ('charge', 'payment', 'tax', 'fee', 'deposit', 'adjustment', "
                "'transfer', 'commission')"
            ),
            name="transactioncode_kind_check",
        ),
        CheckConstraint(
            (
                "department IN ('rooms', 'fnb', 'spa', 'activities', 'retail', "
                "'parking', 'utilities', 'other')"
            ),
            name="transactioncode_department_check",
        ),
        MIGRATION_ONLY,
    )

    property_id: UUID | None = Field(default=None, sa_type=Uuid, description="NULL = tenant-wide")
    code: str = Field(sa_type=Text)
    name: str = Field(sa_type=Text)
    kind: str = Field(sa_type=Text)
    department: str = Field(
        default="rooms", sa_type=Text, sa_column_kwargs={"server_default": text("'rooms'::text")}
    )
    revenue_category: str | None = Field(default=None, sa_type=Text)
    gl_account: str | None = Field(default=None, sa_type=Text)
    allow_manual_post: bool = Field(default=True, sa_column_kwargs={"server_default": text("true")})
    is_active: bool = Field(default=True, sa_column_kwargs={"server_default": text("true")})


class TransactionCodeCreate(SQLModel):
    """Fields accepted when creating a TransactionCode."""

    property_id: UUID | None = None
    code: str
    name: str
    kind: TransactionCodeKind
    department: TransactionCodeDepartment = "rooms"
    revenue_category: str | None = None
    gl_account: str | None = None
    allow_manual_post: bool = True
    is_active: bool = True


class TransactionCodeUpdate(SQLModel):
    """Fields accepted when patching a TransactionCode (all optional)."""

    property_id: UUID | None = None
    code: str | None = None
    name: str | None = None
    kind: TransactionCodeKind | None = None
    department: TransactionCodeDepartment | None = None
    revenue_category: str | None = None
    gl_account: str | None = None
    allow_manual_post: bool | None = None
    is_active: bool | None = None


class TransactionCodeRead(SQLModel):
    """Fields returned when reading a TransactionCode."""

    id: UUID
    tenant_id: UUID
    property_id: UUID | None
    code: str
    name: str
    kind: str
    department: str
    revenue_category: str | None
    gl_account: str | None
    allow_manual_post: bool
    is_active: bool
    created_at: dt.datetime
    updated_at: dt.datetime
    created_by: str | None
    updated_by: str | None
