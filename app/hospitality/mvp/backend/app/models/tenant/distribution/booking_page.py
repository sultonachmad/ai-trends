"""BookingPage and GuestBookingLink entities — the public direct-booking surface.

Tenant database, K. Distribution. `bookingpage.slug` is unique across the product and is
resolved without sign-in by `resolve_booking_page`. `guestbookinglink` holds the guest's
private link to one booking: only a hash is looked up.
"""

import datetime as dt
from uuid import UUID

from sqlalchemy import CheckConstraint, ForeignKeyConstraint, Text, UniqueConstraint, Uuid, text
from sqlmodel import Field, SQLModel

from app.crud.base_model import MIGRATION_ONLY, TenantEntity, TenantRecord, utc_datetime_field


class BookingPage(TenantEntity, table=True):
    """A property's public booking page."""

    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="bookingpage_tenant_id_id_key"),
        UniqueConstraint("tenant_id", "property_id", name="bookingpage_property_key"),
        UniqueConstraint("slug", name="bookingpage_slug_key"),
        CheckConstraint(
            "slug ~ '^[a-z0-9][a-z0-9-]{1,38}[a-z0-9]$'", name="bookingpage_slug_check"
        ),
        ForeignKeyConstraint(
            ["tenant_id", "property_id"],
            ["property.tenant_id", "property.id"],
            name="bookingpage_tenant_id_property_id_fkey",
            ondelete="CASCADE",
        ),
        MIGRATION_ONLY,
    )

    property_id: UUID = Field(sa_type=Uuid)
    slug: str = Field(sa_type=Text)
    is_published: bool = Field(default=False, sa_column_kwargs={"server_default": text("false")})


class BookingPageCreate(SQLModel):
    """Fields accepted when creating a BookingPage."""

    property_id: UUID
    slug: str
    is_published: bool = False


class BookingPageUpdate(SQLModel):
    """Fields accepted when patching a BookingPage (all optional)."""

    slug: str | None = None
    is_published: bool | None = None


class BookingPageRead(SQLModel):
    """Fields returned when reading a BookingPage."""

    id: UUID
    tenant_id: UUID
    property_id: UUID
    slug: str
    is_published: bool
    created_at: dt.datetime
    updated_at: dt.datetime
    created_by: str | None
    updated_by: str | None


class GuestBookingLink(TenantRecord, table=True):
    """The guest's private link to a booking."""

    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="guestbookinglink_tenant_id_id_key"),
        UniqueConstraint("tenant_id", "reservation_id", name="guestbookinglink_reservation_key"),
        UniqueConstraint("token_hash", name="guestbookinglink_token_hash_key"),
        ForeignKeyConstraint(
            ["tenant_id", "reservation_id"],
            ["reservation.tenant_id", "reservation.id"],
            name="guestbookinglink_tenant_id_reservation_id_fkey",
            ondelete="CASCADE",
        ),
        MIGRATION_ONLY,
    )

    reservation_id: UUID = Field(sa_type=Uuid)
    token_hash: str = Field(sa_type=Text)
    token_seed: str = Field(sa_type=Text, description="with the app secret, derives the tokens")
    created_at: dt.datetime = utc_datetime_field(
        nullable=False, default_now=True, server_default_now=True
    )  # type: ignore[assignment]


class GuestBookingLinkCreate(SQLModel):
    """Fields accepted when creating a GuestBookingLink."""

    reservation_id: UUID


class GuestBookingLinkUpdate(SQLModel):
    """Guest links are never edited."""


class GuestBookingLinkRead(SQLModel):
    """Fields returned when reading a GuestBookingLink (never the hash or seed)."""

    id: UUID
    tenant_id: UUID
    reservation_id: UUID
    created_at: dt.datetime
