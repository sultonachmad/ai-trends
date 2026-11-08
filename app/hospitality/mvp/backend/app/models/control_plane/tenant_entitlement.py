"""TenantEntitlement entity — table ``tenantentitlement``.

Control-plane database, Control plane.

Effective module switches per tenant (plan + add-ons + trials + manual grants).

Mirrors .ttest/contexts/schema-control-plane.sql; the Alembic migration creates the table.
"""

import datetime as dt
from typing import Any, Literal
from uuid import UUID

from sqlalchemy import CheckConstraint, ForeignKeyConstraint, Text, UniqueConstraint, Uuid, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel

from app.crud.base_model import MIGRATION_ONLY, UUIDEntity

TenantEntitlementSource = Literal[
    "plan",
    "addon",
    "trial",
    "manual",
]


class TenantEntitlement(UUIDEntity, table=True):
    """Effective module switches per tenant (plan + add-ons + trials + manual grants)."""

    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "module_code", name="tenantentitlement_tenant_id_module_code_key"
        ),
        ForeignKeyConstraint(
            ["tenant_id"],
            ["tenant.id"],
            name="tenantentitlement_tenant_id_fkey",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["module_code"], ["module.code"], name="tenantentitlement_module_code_fkey"
        ),
        CheckConstraint(
            "source IN ('plan', 'addon', 'trial', 'manual')", name="tenantentitlement_source_check"
        ),
        MIGRATION_ONLY,
    )

    tenant_id: UUID = Field(sa_type=Uuid)
    module_code: str = Field(sa_type=Text)
    enabled: bool = Field(default=True, sa_column_kwargs={"server_default": text("true")})
    source: str = Field(
        default="plan", sa_type=Text, sa_column_kwargs={"server_default": text("'plan'::text")}
    )
    limits: dict[str, Any] = Field(
        default_factory=dict,
        sa_type=JSONB,
        sa_column_kwargs={"server_default": text("'{}'::jsonb")},
    )
    valid_from: dt.date | None = Field(default=None)
    valid_to: dt.date | None = Field(default=None)


class TenantEntitlementCreate(SQLModel):
    """Fields accepted when creating a TenantEntitlement."""

    tenant_id: UUID
    module_code: str
    enabled: bool = True
    source: TenantEntitlementSource = "plan"
    limits: dict[str, Any] = Field(default_factory=dict)
    valid_from: dt.date | None = None
    valid_to: dt.date | None = None


class TenantEntitlementUpdate(SQLModel):
    """Fields accepted when patching a TenantEntitlement (all optional)."""

    tenant_id: UUID | None = None
    module_code: str | None = None
    enabled: bool | None = None
    source: TenantEntitlementSource | None = None
    limits: dict[str, Any] | None = None
    valid_from: dt.date | None = None
    valid_to: dt.date | None = None


class TenantEntitlementRead(SQLModel):
    """Fields returned when reading a TenantEntitlement."""

    id: UUID
    tenant_id: UUID
    module_code: str
    enabled: bool
    source: str
    limits: dict[str, Any]
    valid_from: dt.date | None
    valid_to: dt.date | None
    created_at: dt.datetime
    updated_at: dt.datetime
    created_by: str | None
    updated_by: str | None
