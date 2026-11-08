"""ManagementAgreement entity — table ``managementagreement``.

Tenant database, N. Owners.

Owners, shares, agreements.

Mirrors .ttest/contexts/schema-tenant.sql; the Alembic migration creates the table.
"""

import datetime as dt
from typing import Any, Literal
from uuid import UUID

from sqlalchemy import CheckConstraint, ForeignKeyConstraint, Text, UniqueConstraint, Uuid, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel

from app.crud.base_model import MIGRATION_ONLY, TenantEntity

ManagementAgreementModel = Literal[
    "commission",
    "fixed_fee",
    "revenue_share",
    "rental_pool",
    "guaranteed_rent",
]
ManagementAgreementStatus = Literal[
    "draft",
    "active",
    "ended",
]


class ManagementAgreement(TenantEntity, table=True):
    """Owners, shares, agreements."""

    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="managementagreement_tenant_id_id_key"),
        ForeignKeyConstraint(
            ["tenant_id", "owner_id"],
            ["owner.tenant_id", "owner.id"],
            name="managementagreement_tenant_id_owner_id_fkey",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "property_id"],
            ["property.tenant_id", "property.id"],
            name="managementagreement_tenant_id_property_id_fkey",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "contract_document_id"],
            ["document.tenant_id", "document.id"],
            name="managementagreement_tenant_id_contract_document_id_fkey",
            ondelete="SET NULL (contract_document_id)",
        ),
        CheckConstraint(
            (
                "model IN ('commission', 'fixed_fee', 'revenue_share', 'rental_pool', "
                "'guaranteed_rent')"
            ),
            name="managementagreement_model_check",
        ),
        CheckConstraint(
            "status IN ('draft', 'active', 'ended')", name="managementagreement_status_check"
        ),
        MIGRATION_ONLY,
    )

    owner_id: UUID = Field(sa_type=Uuid)
    property_id: UUID = Field(sa_type=Uuid)
    model: str = Field(sa_type=Text)
    terms: dict[str, Any] = Field(
        default_factory=dict,
        sa_type=JSONB,
        sa_column_kwargs={"server_default": text("'{}'::jsonb")},
        description='{"commission_pct":20,"deduct":["ota_commission","cleaning"]}',
    )
    owner_stay_nights_per_year: int | None = Field(default=None)
    valid_from: dt.date = Field()
    valid_to: dt.date | None = Field(default=None)
    contract_document_id: UUID | None = Field(default=None, sa_type=Uuid)
    status: str = Field(
        default="active", sa_type=Text, sa_column_kwargs={"server_default": text("'active'::text")}
    )


class ManagementAgreementCreate(SQLModel):
    """Fields accepted when creating a ManagementAgreement."""

    owner_id: UUID
    property_id: UUID
    model: ManagementAgreementModel
    terms: dict[str, Any] = Field(default_factory=dict)
    owner_stay_nights_per_year: int | None = None
    valid_from: dt.date
    valid_to: dt.date | None = None
    contract_document_id: UUID | None = None
    status: ManagementAgreementStatus = "active"


class ManagementAgreementUpdate(SQLModel):
    """Fields accepted when patching a ManagementAgreement (all optional)."""

    owner_id: UUID | None = None
    property_id: UUID | None = None
    model: ManagementAgreementModel | None = None
    terms: dict[str, Any] | None = None
    owner_stay_nights_per_year: int | None = None
    valid_from: dt.date | None = None
    valid_to: dt.date | None = None
    contract_document_id: UUID | None = None
    status: ManagementAgreementStatus | None = None


class ManagementAgreementRead(SQLModel):
    """Fields returned when reading a ManagementAgreement."""

    id: UUID
    tenant_id: UUID
    owner_id: UUID
    property_id: UUID
    model: str
    terms: dict[str, Any]
    owner_stay_nights_per_year: int | None
    valid_from: dt.date
    valid_to: dt.date | None
    contract_document_id: UUID | None
    status: str
    created_at: dt.datetime
    updated_at: dt.datetime
    created_by: str | None
    updated_by: str | None
