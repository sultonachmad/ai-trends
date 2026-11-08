"""MessageTemplate entity — table ``messagetemplate``.

Tenant database, L. CRM, messaging & reputation.

Multilingual templates incl. WhatsApp approval status.

Mirrors .ttest/contexts/schema-tenant.sql; the Alembic migration creates the table.
"""

import datetime as dt
from typing import Literal
from uuid import UUID

from sqlalchemy import CheckConstraint, ForeignKeyConstraint, Text, UniqueConstraint, Uuid, text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlmodel import Field, SQLModel

from app.crud.base_model import MIGRATION_ONLY, TenantEntity

MessageTemplateChannelKind = Literal[
    "whatsapp",
    "sms",
    "email",
    "instagram",
    "google_business",
    "ota",
    "web_chat",
]
MessageTemplateCategory = Literal[
    "transactional",
    "utility",
    "marketing",
    "authentication",
]
MessageTemplateProviderStatus = Literal[
    "not_required",
    "pending",
    "approved",
    "rejected",
    "paused",
]


class MessageTemplate(TenantEntity, table=True):
    """Multilingual templates incl. WhatsApp approval status."""

    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="messagetemplate_tenant_id_id_key"),
        UniqueConstraint(
            "tenant_id",
            "property_id",
            "code",
            "channel_kind",
            "locale",
            name="messagetemplate_tenant_id_property_id_code_channel_kind_loc_key",
            postgresql_nulls_not_distinct=True,
        ),
        ForeignKeyConstraint(
            ["tenant_id", "property_id"],
            ["property.tenant_id", "property.id"],
            name="messagetemplate_tenant_id_property_id_fkey",
            ondelete="CASCADE",
        ),
        CheckConstraint(
            (
                "channel_kind IN ('whatsapp', 'sms', 'email', 'instagram', "
                "'google_business', 'ota', 'web_chat')"
            ),
            name="messagetemplate_channel_kind_check",
        ),
        CheckConstraint(
            "category IN ('transactional', 'utility', 'marketing', 'authentication')",
            name="messagetemplate_category_check",
        ),
        CheckConstraint(
            ("provider_status IN ('not_required', 'pending', 'approved', 'rejected', 'paused')"),
            name="messagetemplate_provider_status_check",
        ),
        MIGRATION_ONLY,
    )

    property_id: UUID | None = Field(default=None, sa_type=Uuid)
    code: str = Field(
        sa_type=Text, description="'booking_confirmation','pre_arrival','payment_link'"
    )
    channel_kind: str = Field(sa_type=Text)
    locale: str = Field(sa_type=Text)
    category: str = Field(sa_type=Text)
    subject: str | None = Field(default=None, sa_type=Text)
    body: str = Field(sa_type=Text)
    variables: list[str] = Field(
        default_factory=list,
        sa_type=ARRAY(Text),
        sa_column_kwargs={"server_default": text("'{}'::text[]")},
    )
    provider_template_name: str | None = Field(
        default=None, sa_type=Text, description="WhatsApp approved template name"
    )
    provider_status: str = Field(
        default="not_required",
        sa_type=Text,
        sa_column_kwargs={"server_default": text("'not_required'::text")},
    )
    is_active: bool = Field(default=True, sa_column_kwargs={"server_default": text("true")})


class MessageTemplateCreate(SQLModel):
    """Fields accepted when creating a MessageTemplate."""

    property_id: UUID | None = None
    code: str
    channel_kind: MessageTemplateChannelKind
    locale: str
    category: MessageTemplateCategory
    subject: str | None = None
    body: str
    variables: list[str] = Field(default_factory=list)
    provider_template_name: str | None = None
    provider_status: MessageTemplateProviderStatus = "not_required"
    is_active: bool = True


class MessageTemplateUpdate(SQLModel):
    """Fields accepted when patching a MessageTemplate (all optional)."""

    property_id: UUID | None = None
    code: str | None = None
    channel_kind: MessageTemplateChannelKind | None = None
    locale: str | None = None
    category: MessageTemplateCategory | None = None
    subject: str | None = None
    body: str | None = None
    variables: list[str] | None = None
    provider_template_name: str | None = None
    provider_status: MessageTemplateProviderStatus | None = None
    is_active: bool | None = None


class MessageTemplateRead(SQLModel):
    """Fields returned when reading a MessageTemplate."""

    id: UUID
    tenant_id: UUID
    property_id: UUID | None
    code: str
    channel_kind: str
    locale: str
    category: str
    subject: str | None
    body: str
    variables: list[str]
    provider_template_name: str | None
    provider_status: str
    is_active: bool
    created_at: dt.datetime
    updated_at: dt.datetime
    created_by: str | None
    updated_by: str | None
