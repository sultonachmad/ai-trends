"""Campaign entity — table ``campaign``.

Tenant database, L. CRM, messaging & reputation.

Segments and campaigns.

Mirrors .ttest/contexts/schema-tenant.sql; the Alembic migration creates the table.
"""

import datetime as dt
from typing import Any, Literal
from uuid import UUID

from sqlalchemy import CheckConstraint, ForeignKeyConstraint, Text, UniqueConstraint, Uuid, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel

from app.crud.base_model import MIGRATION_ONLY, TenantEntity, utc_datetime_field

CampaignStatus = Literal[
    "draft",
    "scheduled",
    "sending",
    "sent",
    "cancelled",
]


class Campaign(TenantEntity, table=True):
    """Segments and campaigns."""

    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="campaign_tenant_id_id_key"),
        ForeignKeyConstraint(
            ["tenant_id", "property_id"],
            ["property.tenant_id", "property.id"],
            name="campaign_tenant_id_property_id_fkey",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "segment_id"],
            ["guestsegment.tenant_id", "guestsegment.id"],
            name="campaign_tenant_id_segment_id_fkey",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "template_id"],
            ["messagetemplate.tenant_id", "messagetemplate.id"],
            name="campaign_tenant_id_template_id_fkey",
        ),
        CheckConstraint(
            "status IN ('draft', 'scheduled', 'sending', 'sent', 'cancelled')",
            name="campaign_status_check",
        ),
        MIGRATION_ONLY,
    )

    property_id: UUID | None = Field(default=None, sa_type=Uuid)
    name: str = Field(sa_type=Text)
    segment_id: UUID = Field(sa_type=Uuid)
    template_id: UUID = Field(sa_type=Uuid)
    scheduled_at: dt.datetime | None = utc_datetime_field(nullable=True)  # type: ignore[assignment]
    status: str = Field(
        default="draft", sa_type=Text, sa_column_kwargs={"server_default": text("'draft'::text")}
    )
    stats: dict[str, Any] = Field(
        default_factory=dict,
        sa_type=JSONB,
        sa_column_kwargs={"server_default": text("'{}'::jsonb")},
    )


class CampaignCreate(SQLModel):
    """Fields accepted when creating a Campaign."""

    property_id: UUID | None = None
    name: str
    segment_id: UUID
    template_id: UUID
    scheduled_at: dt.datetime | None = None
    status: CampaignStatus = "draft"
    stats: dict[str, Any] = Field(default_factory=dict)


class CampaignUpdate(SQLModel):
    """Fields accepted when patching a Campaign (all optional)."""

    property_id: UUID | None = None
    name: str | None = None
    segment_id: UUID | None = None
    template_id: UUID | None = None
    scheduled_at: dt.datetime | None = None
    status: CampaignStatus | None = None
    stats: dict[str, Any] | None = None


class CampaignRead(SQLModel):
    """Fields returned when reading a Campaign."""

    id: UUID
    tenant_id: UUID
    property_id: UUID | None
    name: str
    segment_id: UUID
    template_id: UUID
    scheduled_at: dt.datetime | None
    status: str
    stats: dict[str, Any]
    created_at: dt.datetime
    updated_at: dt.datetime
    created_by: str | None
    updated_by: str | None
