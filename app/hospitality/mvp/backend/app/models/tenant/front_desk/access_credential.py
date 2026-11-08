"""AccessCredential entity — table ``accesscredential``.

Tenant database, J. Front desk extras.

Key cards, PIN codes, mobile keys (time-bound).

Mirrors .ttest/contexts/schema-tenant.sql; the Alembic migration creates the table.
"""

import datetime as dt
from typing import Literal
from uuid import UUID

from sqlalchemy import CheckConstraint, ForeignKeyConstraint, Text, UniqueConstraint, Uuid, text
from sqlmodel import Field, SQLModel

from app.crud.base_model import MIGRATION_ONLY, TenantEntity, utc_datetime_field

AccessCredentialHolderKind = Literal[
    "guest",
    "staff",
    "vendor",
]
AccessCredentialKind = Literal[
    "rfid_card",
    "pin_code",
    "mobile_key",
    "physical_key",
]
AccessCredentialStatus = Literal[
    "pending",
    "active",
    "revoked",
    "expired",
    "failed",
]


class AccessCredential(TenantEntity, table=True):
    """Key cards, PIN codes, mobile keys (time-bound)."""

    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="accesscredential_tenant_id_id_key"),
        ForeignKeyConstraint(
            ["tenant_id", "property_id"],
            ["property.tenant_id", "property.id"],
            name="accesscredential_tenant_id_property_id_fkey",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "unit_id"],
            ["unit.tenant_id", "unit.id"],
            name="accesscredential_tenant_id_unit_id_fkey",
            ondelete="SET NULL (unit_id)",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "reservation_unit_id"],
            ["reservationunit.tenant_id", "reservationunit.id"],
            name="accesscredential_tenant_id_reservation_unit_id_fkey",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "holder_staff_id"],
            ["staffmember.tenant_id", "staffmember.id"],
            name="accesscredential_tenant_id_holder_staff_id_fkey",
            ondelete="SET NULL (holder_staff_id)",
        ),
        CheckConstraint(
            "holder_kind IN ('guest', 'staff', 'vendor')", name="accesscredential_holder_kind_check"
        ),
        CheckConstraint(
            "kind IN ('rfid_card', 'pin_code', 'mobile_key', 'physical_key')",
            name="accesscredential_kind_check",
        ),
        CheckConstraint(
            "status IN ('pending', 'active', 'revoked', 'expired', 'failed')",
            name="accesscredential_status_check",
        ),
        CheckConstraint("(valid_to > valid_from)", name="accesscredential_check"),
        MIGRATION_ONLY,
    )

    property_id: UUID = Field(sa_type=Uuid)
    unit_id: UUID | None = Field(default=None, sa_type=Uuid)
    reservation_unit_id: UUID | None = Field(default=None, sa_type=Uuid)
    holder_kind: str = Field(sa_type=Text)
    holder_staff_id: UUID | None = Field(default=None, sa_type=Uuid)
    kind: str = Field(sa_type=Text)
    code_hash: str | None = Field(
        default=None, sa_type=Text, description="PIN stored hashed; delivered once to guest"
    )
    code_hint: str | None = Field(default=None, sa_type=Text, description="e.g. last 2 digits")
    lock_system_ref: str | None = Field(default=None, sa_type=Text)
    valid_from: dt.datetime = utc_datetime_field(nullable=False)  # type: ignore[assignment]
    valid_to: dt.datetime = utc_datetime_field(nullable=False)  # type: ignore[assignment]
    status: str = Field(
        default="active", sa_type=Text, sa_column_kwargs={"server_default": text("'active'::text")}
    )
    issued_by: str | None = Field(default=None, sa_type=Text)
    revoked_at: dt.datetime | None = utc_datetime_field(nullable=True)  # type: ignore[assignment]


class AccessCredentialCreate(SQLModel):
    """Fields accepted when creating a AccessCredential."""

    property_id: UUID
    unit_id: UUID | None = None
    reservation_unit_id: UUID | None = None
    holder_kind: AccessCredentialHolderKind
    holder_staff_id: UUID | None = None
    kind: AccessCredentialKind
    code_hint: str | None = None
    lock_system_ref: str | None = None
    valid_from: dt.datetime
    valid_to: dt.datetime
    status: AccessCredentialStatus = "active"
    issued_by: str | None = None
    revoked_at: dt.datetime | None = None


class AccessCredentialUpdate(SQLModel):
    """Fields accepted when patching a AccessCredential (all optional)."""

    property_id: UUID | None = None
    unit_id: UUID | None = None
    reservation_unit_id: UUID | None = None
    holder_kind: AccessCredentialHolderKind | None = None
    holder_staff_id: UUID | None = None
    kind: AccessCredentialKind | None = None
    code_hint: str | None = None
    lock_system_ref: str | None = None
    valid_from: dt.datetime | None = None
    valid_to: dt.datetime | None = None
    status: AccessCredentialStatus | None = None
    issued_by: str | None = None
    revoked_at: dt.datetime | None = None


class AccessCredentialRead(SQLModel):
    """Fields returned when reading a AccessCredential (never returns: code_hash)."""

    id: UUID
    tenant_id: UUID
    property_id: UUID
    unit_id: UUID | None
    reservation_unit_id: UUID | None
    holder_kind: str
    holder_staff_id: UUID | None
    kind: str
    code_hint: str | None
    lock_system_ref: str | None
    valid_from: dt.datetime
    valid_to: dt.datetime
    status: str
    issued_by: str | None
    revoked_at: dt.datetime | None
    created_at: dt.datetime
    updated_at: dt.datetime
    created_by: str | None
    updated_by: str | None
