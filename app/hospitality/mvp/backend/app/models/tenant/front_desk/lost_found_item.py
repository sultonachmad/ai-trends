"""LostFoundItem entity — table ``lostfounditem``.

Tenant database, J. Front desk extras.

Lost & found.

Mirrors .ttest/contexts/schema-tenant.sql; the Alembic migration creates the table.
"""

import datetime as dt
from typing import Literal
from uuid import UUID

from sqlalchemy import CheckConstraint, ForeignKeyConstraint, Text, UniqueConstraint, Uuid, text
from sqlmodel import Field, SQLModel

from app.crud.base_model import MIGRATION_ONLY, TenantEntity, utc_datetime_field

LostFoundItemStatus = Literal[
    "stored",
    "guest_contacted",
    "returned",
    "shipped",
    "disposed",
    "donated",
]


class LostFoundItem(TenantEntity, table=True):
    """Lost & found."""

    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="lostfounditem_tenant_id_id_key"),
        ForeignKeyConstraint(
            ["tenant_id", "property_id"],
            ["property.tenant_id", "property.id"],
            name="lostfounditem_tenant_id_property_id_fkey",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "unit_id"],
            ["unit.tenant_id", "unit.id"],
            name="lostfounditem_tenant_id_unit_id_fkey",
            ondelete="SET NULL (unit_id)",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "found_by_staff_id"],
            ["staffmember.tenant_id", "staffmember.id"],
            name="lostfounditem_tenant_id_found_by_staff_id_fkey",
            ondelete="SET NULL (found_by_staff_id)",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "photo_document_id"],
            ["document.tenant_id", "document.id"],
            name="lostfounditem_tenant_id_photo_document_id_fkey",
            ondelete="SET NULL (photo_document_id)",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "guest_id"],
            ["guest.tenant_id", "guest.id"],
            name="lostfounditem_tenant_id_guest_id_fkey",
            ondelete="SET NULL (guest_id)",
        ),
        CheckConstraint(
            (
                "status IN ('stored', 'guest_contacted', 'returned', 'shipped', "
                "'disposed', 'donated')"
            ),
            name="lostfounditem_status_check",
        ),
        MIGRATION_ONLY,
    )

    property_id: UUID = Field(sa_type=Uuid)
    unit_id: UUID | None = Field(default=None, sa_type=Uuid)
    found_at: dt.datetime = utc_datetime_field(
        nullable=False, default_now=True, server_default_now=True
    )  # type: ignore[assignment]
    found_by_staff_id: UUID | None = Field(default=None, sa_type=Uuid)
    description: str = Field(sa_type=Text)
    storage_location: str | None = Field(default=None, sa_type=Text)
    photo_document_id: UUID | None = Field(default=None, sa_type=Uuid)
    guest_id: UUID | None = Field(default=None, sa_type=Uuid)
    status: str = Field(
        default="stored", sa_type=Text, sa_column_kwargs={"server_default": text("'stored'::text")}
    )
    resolved_at: dt.datetime | None = utc_datetime_field(nullable=True)  # type: ignore[assignment]


class LostFoundItemCreate(SQLModel):
    """Fields accepted when creating a LostFoundItem."""

    property_id: UUID
    unit_id: UUID | None = None
    found_at: dt.datetime = Field(default_factory=lambda: dt.datetime.now(dt.UTC))
    found_by_staff_id: UUID | None = None
    description: str
    storage_location: str | None = None
    photo_document_id: UUID | None = None
    guest_id: UUID | None = None
    status: LostFoundItemStatus = "stored"
    resolved_at: dt.datetime | None = None


class LostFoundItemUpdate(SQLModel):
    """Fields accepted when patching a LostFoundItem (all optional)."""

    property_id: UUID | None = None
    unit_id: UUID | None = None
    found_at: dt.datetime | None = None
    found_by_staff_id: UUID | None = None
    description: str | None = None
    storage_location: str | None = None
    photo_document_id: UUID | None = None
    guest_id: UUID | None = None
    status: LostFoundItemStatus | None = None
    resolved_at: dt.datetime | None = None


class LostFoundItemRead(SQLModel):
    """Fields returned when reading a LostFoundItem."""

    id: UUID
    tenant_id: UUID
    property_id: UUID
    unit_id: UUID | None
    found_at: dt.datetime
    found_by_staff_id: UUID | None
    description: str
    storage_location: str | None
    photo_document_id: UUID | None
    guest_id: UUID | None
    status: str
    resolved_at: dt.datetime | None
    created_at: dt.datetime
    updated_at: dt.datetime
    created_by: str | None
    updated_by: str | None
