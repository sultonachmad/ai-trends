"""AiFeatureSetting entity — table ``aifeaturesetting``.

Tenant database, S. AI assistant layer.

Enablement, autonomy, monthly cap.

Mirrors .ttest/contexts/schema-tenant.sql; the Alembic migration creates the table.
"""

import datetime as dt
from typing import Any, Literal
from uuid import UUID

from sqlalchemy import CheckConstraint, ForeignKeyConstraint, Text, UniqueConstraint, Uuid, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel

from app.crud.base_model import MIGRATION_ONLY, TenantEntity

AiFeatureSettingAutonomy = Literal[
    "off",
    "suggest",
    "auto_allowlist",
]
AiFeatureSettingModelTier = Literal[
    "small",
    "medium",
    "large",
]


class AiFeatureSetting(TenantEntity, table=True):
    """Enablement, autonomy, monthly cap."""

    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="aifeaturesetting_tenant_id_id_key"),
        UniqueConstraint(
            "tenant_id",
            "property_id",
            "feature",
            name="aifeaturesetting_tenant_id_property_id_feature_key",
            postgresql_nulls_not_distinct=True,
        ),
        ForeignKeyConstraint(
            ["tenant_id", "property_id"],
            ["property.tenant_id", "property.id"],
            name="aifeaturesetting_tenant_id_property_id_fkey",
            ondelete="CASCADE",
        ),
        CheckConstraint(
            "autonomy IN ('off', 'suggest', 'auto_allowlist')",
            name="aifeaturesetting_autonomy_check",
        ),
        CheckConstraint(
            "model_tier IN ('small', 'medium', 'large')", name="aifeaturesetting_model_tier_check"
        ),
        MIGRATION_ONLY,
    )

    property_id: UUID | None = Field(
        default=None, sa_type=Uuid, description="NULL = tenant default"
    )
    feature: str = Field(
        sa_type=Text,
        description="'message_reply','faq_autoreply','review_reply','transfer_proof',…",
    )
    enabled: bool = Field(default=False, sa_column_kwargs={"server_default": text("false")})
    autonomy: str = Field(
        default="suggest",
        sa_type=Text,
        sa_column_kwargs={"server_default": text("'suggest'::text")},
    )
    model_tier: str = Field(
        default="small", sa_type=Text, sa_column_kwargs={"server_default": text("'small'::text")}
    )
    config: dict[str, Any] = Field(
        default_factory=dict,
        sa_type=JSONB,
        sa_column_kwargs={"server_default": text("'{}'::jsonb")},
        description="tone, allow-listed intents, language prefs",
    )


class AiFeatureSettingCreate(SQLModel):
    """Fields accepted when creating a AiFeatureSetting."""

    property_id: UUID | None = None
    feature: str
    enabled: bool = False
    autonomy: AiFeatureSettingAutonomy = "suggest"
    model_tier: AiFeatureSettingModelTier = "small"
    config: dict[str, Any] = Field(default_factory=dict)


class AiFeatureSettingUpdate(SQLModel):
    """Fields accepted when patching a AiFeatureSetting (all optional)."""

    property_id: UUID | None = None
    feature: str | None = None
    enabled: bool | None = None
    autonomy: AiFeatureSettingAutonomy | None = None
    model_tier: AiFeatureSettingModelTier | None = None
    config: dict[str, Any] | None = None


class AiFeatureSettingRead(SQLModel):
    """Fields returned when reading a AiFeatureSetting."""

    id: UUID
    tenant_id: UUID
    property_id: UUID | None
    feature: str
    enabled: bool
    autonomy: str
    model_tier: str
    config: dict[str, Any]
    created_at: dt.datetime
    updated_at: dt.datetime
    created_by: str | None
    updated_by: str | None
