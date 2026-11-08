"""GuestPreference entity — table ``guestpreference``.

Tenant database, F. Accounts & guests.

Preferences; consent per purpose and channel (PDP Law).

Mirrors .ttest/contexts/schema-tenant.sql; the Alembic migration creates the table.
"""

import datetime as dt
from typing import Literal
from uuid import UUID

from sqlalchemy import CheckConstraint, ForeignKeyConstraint, Text, UniqueConstraint, Uuid
from sqlmodel import Field, SQLModel

from app.crud.base_model import MIGRATION_ONLY, TenantEntity

GuestPreferenceCategory = Literal[
    "unit",
    "bed",
    "pillow",
    "diet",
    "allergy",
    "accessibility",
    "floor",
    "view",
    "communication",
    "other",
]


class GuestPreference(TenantEntity, table=True):
    """Preferences; consent per purpose and channel (PDP Law)."""

    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="guestpreference_tenant_id_id_key"),
        ForeignKeyConstraint(
            ["tenant_id", "guest_id"],
            ["guest.tenant_id", "guest.id"],
            name="guestpreference_tenant_id_guest_id_fkey",
            ondelete="CASCADE",
        ),
        CheckConstraint(
            (
                "category IN ('unit', 'bed', 'pillow', 'diet', 'allergy', "
                "'accessibility', 'floor', 'view', 'communication', 'other')"
            ),
            name="guestpreference_category_check",
        ),
        MIGRATION_ONLY,
    )

    guest_id: UUID = Field(sa_type=Uuid)
    category: str = Field(sa_type=Text)
    value: str = Field(sa_type=Text)
    note: str | None = Field(default=None, sa_type=Text)


class GuestPreferenceCreate(SQLModel):
    """Fields accepted when creating a GuestPreference."""

    guest_id: UUID
    category: GuestPreferenceCategory
    value: str
    note: str | None = None


class GuestPreferenceUpdate(SQLModel):
    """Fields accepted when patching a GuestPreference (all optional)."""

    guest_id: UUID | None = None
    category: GuestPreferenceCategory | None = None
    value: str | None = None
    note: str | None = None


class GuestPreferenceRead(SQLModel):
    """Fields returned when reading a GuestPreference."""

    id: UUID
    tenant_id: UUID
    guest_id: UUID
    category: str
    value: str
    note: str | None
    created_at: dt.datetime
    updated_at: dt.datetime
    created_by: str | None
    updated_by: str | None
