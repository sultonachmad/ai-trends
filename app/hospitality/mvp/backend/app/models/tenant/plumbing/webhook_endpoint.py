"""WebhookEndpoint entity — table ``webhookendpoint``.

Tenant database, T. Platform plumbing.

Events and outbound webhooks.

Mirrors .ttest/contexts/schema-tenant.sql; the Alembic migration creates the table.
"""

import datetime as dt
from uuid import UUID

from sqlalchemy import Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlmodel import Field, SQLModel

from app.crud.base_model import MIGRATION_ONLY, TenantEntity


class WebhookEndpoint(TenantEntity, table=True):
    """Events and outbound webhooks."""

    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="webhookendpoint_tenant_id_id_key"),
        MIGRATION_ONLY,
    )

    url: str = Field(sa_type=Text)
    secret_ref: str = Field(sa_type=Text)
    event_types: list[str] = Field(
        default_factory=list,
        sa_type=ARRAY(Text),
        sa_column_kwargs={"server_default": text("'{}'::text[]")},
    )
    is_active: bool = Field(default=True, sa_column_kwargs={"server_default": text("true")})


class WebhookEndpointCreate(SQLModel):
    """Fields accepted when creating a WebhookEndpoint."""

    url: str
    secret_ref: str
    event_types: list[str] = Field(default_factory=list)
    is_active: bool = True


class WebhookEndpointUpdate(SQLModel):
    """Fields accepted when patching a WebhookEndpoint (all optional)."""

    url: str | None = None
    secret_ref: str | None = None
    event_types: list[str] | None = None
    is_active: bool | None = None


class WebhookEndpointRead(SQLModel):
    """Fields returned when reading a WebhookEndpoint."""

    id: UUID
    tenant_id: UUID
    url: str
    secret_ref: str
    event_types: list[str]
    is_active: bool
    created_at: dt.datetime
    updated_at: dt.datetime
    created_by: str | None
    updated_by: str | None
