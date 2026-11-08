"""CancellationPolicy entity — table ``cancellationpolicy``.

Tenant database, E. Rates, policies, products & restrictions.

Rules (incl. DP schedules).

Mirrors .ttest/contexts/schema-tenant.sql; the Alembic migration creates the table.
"""

import datetime as dt
from typing import Any
from uuid import UUID

from sqlalchemy import ForeignKeyConstraint, Text, UniqueConstraint, Uuid, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel

from app.crud.base_model import MIGRATION_ONLY, TenantEntity


class CancellationPolicy(TenantEntity, table=True):
    """Rules (incl. DP schedules)."""

    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="cancellationpolicy_tenant_id_id_key"),
        UniqueConstraint(
            "tenant_id",
            "property_id",
            "code",
            name="cancellationpolicy_tenant_id_property_id_code_key",
            postgresql_nulls_not_distinct=True,
        ),
        ForeignKeyConstraint(
            ["tenant_id", "property_id"],
            ["property.tenant_id", "property.id"],
            name="cancellationpolicy_tenant_id_property_id_fkey",
            ondelete="CASCADE",
        ),
        MIGRATION_ONLY,
    )

    property_id: UUID | None = Field(default=None, sa_type=Uuid)
    code: str = Field(sa_type=Text)
    name: str = Field(sa_type=Text)
    rules: list[Any] = Field(
        default_factory=list,
        sa_type=JSONB,
        sa_column_kwargs={"server_default": text("'[]'::jsonb")},
    )
    no_show_rule: dict[str, Any] = Field(
        default_factory=lambda: {"kind": "first_night"},
        sa_type=JSONB,
        sa_column_kwargs={"server_default": text('\'{"kind": "first_night"}\'::jsonb')},
    )
    description_i18n: dict[str, Any] = Field(
        default_factory=dict,
        sa_type=JSONB,
        sa_column_kwargs={"server_default": text("'{}'::jsonb")},
    )
    is_non_refundable: bool = Field(
        default=False, sa_column_kwargs={"server_default": text("false")}
    )
    is_active: bool = Field(default=True, sa_column_kwargs={"server_default": text("true")})


class CancellationPolicyCreate(SQLModel):
    """Fields accepted when creating a CancellationPolicy."""

    property_id: UUID | None = None
    code: str
    name: str
    rules: list[Any] = Field(default_factory=list)
    no_show_rule: dict[str, Any] = Field(default_factory=lambda: {"kind": "first_night"})
    description_i18n: dict[str, Any] = Field(default_factory=dict)
    is_non_refundable: bool = False
    is_active: bool = True


class CancellationPolicyUpdate(SQLModel):
    """Fields accepted when patching a CancellationPolicy (all optional)."""

    property_id: UUID | None = None
    code: str | None = None
    name: str | None = None
    rules: list[Any] | None = None
    no_show_rule: dict[str, Any] | None = None
    description_i18n: dict[str, Any] | None = None
    is_non_refundable: bool | None = None
    is_active: bool | None = None


class CancellationPolicyRead(SQLModel):
    """Fields returned when reading a CancellationPolicy."""

    id: UUID
    tenant_id: UUID
    property_id: UUID | None
    code: str
    name: str
    rules: list[Any]
    no_show_rule: dict[str, Any]
    description_i18n: dict[str, Any]
    is_non_refundable: bool
    is_active: bool
    created_at: dt.datetime
    updated_at: dt.datetime
    created_by: str | None
    updated_by: str | None
