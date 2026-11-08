"""GuestConsent entity — table ``guestconsent``.

Tenant database, F. Accounts & guests.

Consent per purpose and channel (PDP Law / GDPR).

Mirrors .ttest/contexts/schema-tenant.sql; the Alembic migration creates the table.
"""

import datetime as dt
from typing import Literal
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    ForeignKeyConstraint,
    Index,
    Text,
    UniqueConstraint,
    Uuid,
    text,
)
from sqlmodel import Field, SQLModel

from app.crud.base_model import MIGRATION_ONLY, TenantEntity, utc_datetime_field

GuestConsentPurpose = Literal[
    "marketing",
    "survey",
    "profiling",
    "ai_processing",
    "cross_border_transfer",
    "data_sharing",
]
GuestConsentChannel = Literal[
    "any",
    "email",
    "sms",
    "whatsapp",
    "phone",
    "push",
]


class GuestConsent(TenantEntity, table=True):
    """Consent per purpose and channel (PDP Law / GDPR)."""

    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="guestconsent_tenant_id_id_key"),
        ForeignKeyConstraint(
            ["tenant_id", "guest_id"],
            ["guest.tenant_id", "guest.id"],
            name="guestconsent_tenant_id_guest_id_fkey",
            ondelete="CASCADE",
        ),
        CheckConstraint(
            (
                "purpose IN ('marketing', 'survey', 'profiling', 'ai_processing', "
                "'cross_border_transfer', 'data_sharing')"
            ),
            name="guestconsent_purpose_check",
        ),
        CheckConstraint(
            "channel IN ('any', 'email', 'sms', 'whatsapp', 'phone', 'push')",
            name="guestconsent_channel_check",
        ),
        Index("ix_guestconsent_guest", "tenant_id", "guest_id", "purpose", "channel"),
        MIGRATION_ONLY,
    )

    guest_id: UUID = Field(sa_type=Uuid)
    purpose: str = Field(sa_type=Text)
    channel: str = Field(
        default="any", sa_type=Text, sa_column_kwargs={"server_default": text("'any'::text")}
    )
    granted: bool = Field()
    wording_version: str = Field(sa_type=Text)
    source: str = Field(
        sa_type=Text, description="'booking_engine','portal','front_desk','whatsapp_optin'"
    )
    captured_at: dt.datetime = utc_datetime_field(
        nullable=False, default_now=True, server_default_now=True
    )  # type: ignore[assignment]
    withdrawn_at: dt.datetime | None = utc_datetime_field(nullable=True)  # type: ignore[assignment]


class GuestConsentCreate(SQLModel):
    """Fields accepted when creating a GuestConsent."""

    guest_id: UUID
    purpose: GuestConsentPurpose
    channel: GuestConsentChannel = "any"
    granted: bool
    wording_version: str
    source: str
    captured_at: dt.datetime = Field(default_factory=lambda: dt.datetime.now(dt.UTC))
    withdrawn_at: dt.datetime | None = None


class GuestConsentUpdate(SQLModel):
    """Fields accepted when patching a GuestConsent (all optional)."""

    guest_id: UUID | None = None
    purpose: GuestConsentPurpose | None = None
    channel: GuestConsentChannel | None = None
    granted: bool | None = None
    wording_version: str | None = None
    source: str | None = None
    captured_at: dt.datetime | None = None
    withdrawn_at: dt.datetime | None = None


class GuestConsentRead(SQLModel):
    """Fields returned when reading a GuestConsent."""

    id: UUID
    tenant_id: UUID
    guest_id: UUID
    purpose: str
    channel: str
    granted: bool
    wording_version: str
    source: str
    captured_at: dt.datetime
    withdrawn_at: dt.datetime | None
    created_at: dt.datetime
    updated_at: dt.datetime
    created_by: str | None
    updated_by: str | None
