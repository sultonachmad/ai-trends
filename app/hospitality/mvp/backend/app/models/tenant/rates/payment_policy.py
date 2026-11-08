"""PaymentPolicy entity — table ``paymentpolicy``.

Tenant database, E. Rates, policies, products & restrictions.

Rules (incl. DP schedules).

Mirrors .ttest/contexts/schema-tenant.sql; the Alembic migration creates the table.
"""

import datetime as dt
from typing import Any, Literal
from uuid import UUID

from sqlalchemy import CheckConstraint, ForeignKeyConstraint, Text, UniqueConstraint, Uuid, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel

from app.crud.base_model import MIGRATION_ONLY, TenantEntity

PaymentPolicyGuaranteeKind = Literal[
    "none",
    "card",
    "deposit",
    "full_prepay",
    "company",
    "voucher",
]


class PaymentPolicy(TenantEntity, table=True):
    """Rules (incl. DP schedules)."""

    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="paymentpolicy_tenant_id_id_key"),
        UniqueConstraint(
            "tenant_id",
            "property_id",
            "code",
            name="paymentpolicy_tenant_id_property_id_code_key",
            postgresql_nulls_not_distinct=True,
        ),
        ForeignKeyConstraint(
            ["tenant_id", "property_id"],
            ["property.tenant_id", "property.id"],
            name="paymentpolicy_tenant_id_property_id_fkey",
            ondelete="CASCADE",
        ),
        CheckConstraint(
            ("guarantee_kind IN ('none', 'card', 'deposit', 'full_prepay', 'company', 'voucher')"),
            name="paymentpolicy_guarantee_kind_check",
        ),
        MIGRATION_ONLY,
    )

    property_id: UUID | None = Field(default=None, sa_type=Uuid)
    code: str = Field(sa_type=Text)
    name: str = Field(sa_type=Text)
    guarantee_kind: str = Field(sa_type=Text)
    schedule: list[Any] = Field(
        default_factory=list,
        sa_type=JSONB,
        sa_column_kwargs={"server_default": text("'[]'::jsonb")},
    )
    auto_cancel_unpaid_after_hours: int | None = Field(
        default=None, description="release unpaid DP holds"
    )
    description_i18n: dict[str, Any] = Field(
        default_factory=dict,
        sa_type=JSONB,
        sa_column_kwargs={"server_default": text("'{}'::jsonb")},
    )
    is_active: bool = Field(default=True, sa_column_kwargs={"server_default": text("true")})


class PaymentPolicyCreate(SQLModel):
    """Fields accepted when creating a PaymentPolicy."""

    property_id: UUID | None = None
    code: str
    name: str
    guarantee_kind: PaymentPolicyGuaranteeKind
    schedule: list[Any] = Field(default_factory=list)
    auto_cancel_unpaid_after_hours: int | None = None
    description_i18n: dict[str, Any] = Field(default_factory=dict)
    is_active: bool = True


class PaymentPolicyUpdate(SQLModel):
    """Fields accepted when patching a PaymentPolicy (all optional)."""

    property_id: UUID | None = None
    code: str | None = None
    name: str | None = None
    guarantee_kind: PaymentPolicyGuaranteeKind | None = None
    schedule: list[Any] | None = None
    auto_cancel_unpaid_after_hours: int | None = None
    description_i18n: dict[str, Any] | None = None
    is_active: bool | None = None


class PaymentPolicyRead(SQLModel):
    """Fields returned when reading a PaymentPolicy."""

    id: UUID
    tenant_id: UUID
    property_id: UUID | None
    code: str
    name: str
    guarantee_kind: str
    schedule: list[Any]
    auto_cancel_unpaid_after_hours: int | None
    description_i18n: dict[str, Any]
    is_active: bool
    created_at: dt.datetime
    updated_at: dt.datetime
    created_by: str | None
    updated_by: str | None
