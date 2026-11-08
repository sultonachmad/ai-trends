"""Vendor entity — table ``vendor``.

Tenant database, B. Staff, vendors & tenant-scoped roles.

External cleaners, technicians, laundry.

Mirrors .ttest/contexts/schema-tenant.sql; the Alembic migration creates the table.
"""

import datetime as dt
from typing import Any, Literal
from uuid import UUID

from sqlalchemy import CheckConstraint, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel

from app.crud.base_model import MIGRATION_ONLY, TenantEntity

VendorKind = Literal[
    "cleaning",
    "maintenance",
    "laundry",
    "transport",
    "supplies",
    "activity",
    "other",
]


class Vendor(TenantEntity, table=True):
    """External cleaners, technicians, laundry."""

    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="vendor_tenant_id_id_key"),
        CheckConstraint(
            (
                "kind IN ('cleaning', 'maintenance', 'laundry', 'transport', 'supplies', "
                "'activity', 'other')"
            ),
            name="vendor_kind_check",
        ),
        MIGRATION_ONLY,
    )

    name: str = Field(sa_type=Text)
    kind: str = Field(sa_type=Text)
    phone: str | None = Field(default=None, sa_type=Text)
    email: str | None = Field(default=None, sa_type=Text)
    tax_id: str | None = Field(default=None, sa_type=Text)
    payment_terms_days: int | None = Field(default=None)
    bank_details: dict[str, Any] = Field(
        default_factory=dict,
        sa_type=JSONB,
        sa_column_kwargs={"server_default": text("'{}'::jsonb")},
        description="masked; full numbers in secret store",
    )
    is_active: bool = Field(default=True, sa_column_kwargs={"server_default": text("true")})


class VendorCreate(SQLModel):
    """Fields accepted when creating a Vendor."""

    name: str
    kind: VendorKind
    phone: str | None = None
    email: str | None = None
    tax_id: str | None = None
    payment_terms_days: int | None = None
    bank_details: dict[str, Any] = Field(default_factory=dict)
    is_active: bool = True


class VendorUpdate(SQLModel):
    """Fields accepted when patching a Vendor (all optional)."""

    name: str | None = None
    kind: VendorKind | None = None
    phone: str | None = None
    email: str | None = None
    tax_id: str | None = None
    payment_terms_days: int | None = None
    bank_details: dict[str, Any] | None = None
    is_active: bool | None = None


class VendorRead(SQLModel):
    """Fields returned when reading a Vendor."""

    id: UUID
    tenant_id: UUID
    name: str
    kind: str
    phone: str | None
    email: str | None
    tax_id: str | None
    payment_terms_days: int | None
    bank_details: dict[str, Any]
    is_active: bool
    created_at: dt.datetime
    updated_at: dt.datetime
    created_by: str | None
    updated_by: str | None
