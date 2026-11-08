"""TenantInvitation entity — table ``tenantinvitation``.

Control-plane database, Control plane.

Pending staff invitations (hashed token).

Mirrors .ttest/contexts/schema-control-plane.sql; the Alembic migration creates the table.
"""

import datetime as dt
from uuid import UUID

from sqlalchemy import ForeignKeyConstraint, Index, Text, UniqueConstraint, Uuid, text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlmodel import Field, SQLModel

from app.crud.base_model import MIGRATION_ONLY, UUIDEntity, utc_datetime_field


class TenantInvitation(UUIDEntity, table=True):
    """Pending staff invitations (hashed token)."""

    __table_args__ = (
        UniqueConstraint("token_hash", name="tenantinvitation_token_hash_key"),
        ForeignKeyConstraint(
            ["tenant_id"], ["tenant.id"], name="tenantinvitation_tenant_id_fkey", ondelete="CASCADE"
        ),
        ForeignKeyConstraint(
            ["invited_by_user_id"],
            ["user.id"],
            name="tenantinvitation_invited_by_user_id_fkey",
            ondelete="SET NULL",
        ),
        Index("ix_tenantinvitation_email", text("lower(email)")),
        MIGRATION_ONLY,
    )

    tenant_id: UUID = Field(sa_type=Uuid)
    email: str = Field(sa_type=Text)
    token_hash: str = Field(sa_type=Text, description="store hash only; token goes in the URL path")
    role_codes: list[str] = Field(
        default_factory=list,
        sa_type=ARRAY(Text),
        sa_column_kwargs={"server_default": text("'{}'::text[]")},
    )
    property_ids: list[UUID] = Field(
        default_factory=list,
        sa_type=ARRAY(Uuid),
        sa_column_kwargs={"server_default": text("'{}'::uuid[]")},
    )
    invited_by_user_id: int | None = Field(default=None)
    expires_at: dt.datetime = utc_datetime_field(nullable=False)  # type: ignore[assignment]
    accepted_at: dt.datetime | None = utc_datetime_field(nullable=True)  # type: ignore[assignment]
    revoked_at: dt.datetime | None = utc_datetime_field(nullable=True)  # type: ignore[assignment]


class TenantInvitationCreate(SQLModel):
    """Fields accepted when creating a TenantInvitation."""

    tenant_id: UUID
    email: str
    role_codes: list[str] = Field(default_factory=list)
    property_ids: list[UUID] = Field(default_factory=list)
    invited_by_user_id: int | None = None
    expires_at: dt.datetime
    accepted_at: dt.datetime | None = None
    revoked_at: dt.datetime | None = None


class TenantInvitationUpdate(SQLModel):
    """Fields accepted when patching a TenantInvitation (all optional)."""

    tenant_id: UUID | None = None
    email: str | None = None
    role_codes: list[str] | None = None
    property_ids: list[UUID] | None = None
    invited_by_user_id: int | None = None
    expires_at: dt.datetime | None = None
    accepted_at: dt.datetime | None = None
    revoked_at: dt.datetime | None = None


class TenantInvitationRead(SQLModel):
    """Fields returned when reading a TenantInvitation (never returns: token_hash)."""

    id: UUID
    tenant_id: UUID
    email: str
    role_codes: list[str]
    property_ids: list[UUID]
    invited_by_user_id: int | None
    expires_at: dt.datetime
    accepted_at: dt.datetime | None
    revoked_at: dt.datetime | None
    created_at: dt.datetime
    updated_at: dt.datetime
    created_by: str | None
    updated_by: str | None
