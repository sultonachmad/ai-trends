"""LegalEntity entity — table ``legalentity``.

Tenant database, A. Organisation & property.

Legal/fiscal entity that issues invoices (PT / CV / individual operator).

Mirrors .ttest/contexts/schema-tenant.sql; the Alembic migration creates the table.
"""

import datetime as dt
from typing import Any, Literal
from uuid import UUID

from sqlalchemy import (
    CHAR,
    CheckConstraint,
    ForeignKeyConstraint,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel

from app.crud.base_model import MIGRATION_ONLY, TenantEntity

LegalEntityKind = Literal[
    "company",
    "individual",
    "cooperative",
    "government",
]


class LegalEntity(TenantEntity, table=True):
    """Legal/fiscal entity that issues invoices (PT / CV / individual operator)."""

    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="legalentity_tenant_id_id_key"),
        ForeignKeyConstraint(
            ["tenant_id"], ["tenantprofile.id"], name="legalentity_tenant_id_fkey"
        ),
        CheckConstraint(
            "kind IN ('company', 'individual', 'cooperative', 'government')",
            name="legalentity_kind_check",
        ),
        MIGRATION_ONLY,
    )

    name: str = Field(sa_type=Text)
    kind: str = Field(
        default="company",
        sa_type=Text,
        sa_column_kwargs={"server_default": text("'company'::text")},
    )
    tax_id: str | None = Field(default=None, sa_type=Text, description="NPWP in Indonesia")
    business_id: str | None = Field(
        default=None, sa_type=Text, description="NIB (OSS) in Indonesia"
    )
    country_code: str = Field(
        default="ID", sa_type=CHAR(2), sa_column_kwargs={"server_default": text("'ID'::bpchar")}
    )
    currency: str = Field(
        default="IDR", sa_type=CHAR(3), sa_column_kwargs={"server_default": text("'IDR'::bpchar")}
    )
    address: dict[str, Any] = Field(
        default_factory=dict,
        sa_type=JSONB,
        sa_column_kwargs={"server_default": text("'{}'::jsonb")},
    )
    is_vat_registered: bool = Field(
        default=False, sa_column_kwargs={"server_default": text("false")}, description="PKP"
    )
    is_active: bool = Field(default=True, sa_column_kwargs={"server_default": text("true")})


class LegalEntityCreate(SQLModel):
    """Fields accepted when creating a LegalEntity."""

    name: str
    kind: LegalEntityKind = "company"
    tax_id: str | None = None
    business_id: str | None = None
    country_code: str = Field(default="ID", min_length=2, max_length=2)
    currency: str = Field(default="IDR", min_length=3, max_length=3)
    address: dict[str, Any] = Field(default_factory=dict)
    is_vat_registered: bool = False
    is_active: bool = True


class LegalEntityUpdate(SQLModel):
    """Fields accepted when patching a LegalEntity (all optional)."""

    name: str | None = None
    kind: LegalEntityKind | None = None
    tax_id: str | None = None
    business_id: str | None = None
    country_code: str | None = Field(default=None, min_length=2, max_length=2)
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    address: dict[str, Any] | None = None
    is_vat_registered: bool | None = None
    is_active: bool | None = None


class LegalEntityRead(SQLModel):
    """Fields returned when reading a LegalEntity."""

    id: UUID
    tenant_id: UUID
    name: str
    kind: str
    tax_id: str | None
    business_id: str | None
    country_code: str
    currency: str
    address: dict[str, Any]
    is_vat_registered: bool
    is_active: bool
    created_at: dt.datetime
    updated_at: dt.datetime
    created_by: str | None
    updated_by: str | None
