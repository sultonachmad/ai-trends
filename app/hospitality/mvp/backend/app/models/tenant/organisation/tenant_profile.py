"""TenantProfile entity — table ``tenantprofile``.

Tenant database, A. Organisation & property.

Local mirror of the control-plane tenant (one row per tenant in this DB).

Mirrors .ttest/contexts/schema-tenant.sql; the Alembic migration creates the table.
"""

import datetime as dt
from typing import Any
from uuid import UUID

from sqlalchemy import CHAR, CheckConstraint, Text, UniqueConstraint, Uuid, text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlmodel import Field, SQLModel

from app.crud.base_model import MIGRATION_ONLY, ServerAuditMixin


class TenantProfile(ServerAuditMixin, table=True):
    """Local mirror of the control-plane tenant (one row per tenant in this DB)."""

    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="tenantprofile_tenant_id_id_key"),
        CheckConstraint("(tenant_id = id)", name="tenantprofile_check"),
        MIGRATION_ONLY,
    )

    id: UUID = Field(primary_key=True, sa_type=Uuid, description="== control plane tenant.id")
    tenant_id: UUID = Field(sa_type=Uuid)
    code: str = Field(sa_type=Text)
    name: str = Field(sa_type=Text)
    default_locale: str = Field(
        default="id-ID", sa_type=Text, sa_column_kwargs={"server_default": text("'id-ID'::text")}
    )
    default_currency: str = Field(
        default="IDR", sa_type=CHAR(3), sa_column_kwargs={"server_default": text("'IDR'::bpchar")}
    )
    default_timezone: str = Field(
        default="Asia/Jakarta",
        sa_type=Text,
        sa_column_kwargs={"server_default": text("'Asia/Jakarta'::text")},
    )
    enabled_modules: list[str] = Field(
        default_factory=list,
        sa_type=ARRAY(Text),
        sa_column_kwargs={"server_default": text("'{}'::text[]")},
        description="cached entitlements; control plane is the truth",
    )
    settings: dict[str, Any] = Field(
        default_factory=dict,
        sa_type=JSONB,
        sa_column_kwargs={"server_default": text("'{}'::jsonb")},
    )


class TenantProfileCreate(SQLModel):
    """Fields accepted when creating a TenantProfile."""

    id: UUID
    code: str
    name: str
    default_locale: str = "id-ID"
    default_currency: str = Field(default="IDR", min_length=3, max_length=3)
    default_timezone: str = "Asia/Jakarta"
    enabled_modules: list[str] = Field(default_factory=list)
    settings: dict[str, Any] = Field(default_factory=dict)


class TenantProfileUpdate(SQLModel):
    """Fields accepted when patching a TenantProfile (all optional)."""

    code: str | None = None
    name: str | None = None
    default_locale: str | None = None
    default_currency: str | None = Field(default=None, min_length=3, max_length=3)
    default_timezone: str | None = None
    enabled_modules: list[str] | None = None
    settings: dict[str, Any] | None = None


class TenantProfileRead(SQLModel):
    """Fields returned when reading a TenantProfile."""

    id: UUID
    tenant_id: UUID
    code: str
    name: str
    default_locale: str
    default_currency: str
    default_timezone: str
    enabled_modules: list[str]
    settings: dict[str, Any]
    created_at: dt.datetime
    updated_at: dt.datetime
    created_by: str | None
    updated_by: str | None
