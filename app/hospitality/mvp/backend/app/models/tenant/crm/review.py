"""Review entity — table ``review``.

Tenant database, L. CRM, messaging & reputation.

Reputation, surveys, complaints.

Mirrors .ttest/contexts/schema-tenant.sql; the Alembic migration creates the table.
"""

import datetime as dt
from decimal import Decimal
from typing import Literal
from uuid import UUID

from sqlalchemy import CheckConstraint, ForeignKeyConstraint, Text, UniqueConstraint, Uuid, text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlmodel import Field, SQLModel

from app.crud.base_model import MIGRATION_ONLY, TenantEntity, utc_datetime_field

ReviewSource = Literal[
    "google",
    "traveloka",
    "tiket",
    "agoda",
    "booking_com",
    "airbnb",
    "expedia",
    "trip_com",
    "tripadvisor",
    "internal",
]
ReviewSentiment = Literal[
    "positive",
    "neutral",
    "negative",
    "mixed",
]
ReviewResponseStatus = Literal[
    "none",
    "draft",
    "awaiting_approval",
    "published",
    "failed",
]


class Review(TenantEntity, table=True):
    """Reputation, surveys, complaints."""

    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="review_tenant_id_id_key"),
        UniqueConstraint(
            "tenant_id", "source", "external_id", name="review_tenant_id_source_external_id_key"
        ),
        ForeignKeyConstraint(
            ["tenant_id", "property_id"],
            ["property.tenant_id", "property.id"],
            name="review_tenant_id_property_id_fkey",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "reservation_id"],
            ["reservation.tenant_id", "reservation.id"],
            name="review_tenant_id_reservation_id_fkey",
            ondelete="SET NULL (reservation_id)",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "guest_id"],
            ["guest.tenant_id", "guest.id"],
            name="review_tenant_id_guest_id_fkey",
            ondelete="SET NULL (guest_id)",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "unit_id"],
            ["unit.tenant_id", "unit.id"],
            name="review_tenant_id_unit_id_fkey",
            ondelete="SET NULL (unit_id)",
        ),
        CheckConstraint(
            (
                "source IN ('google', 'traveloka', 'tiket', 'agoda', 'booking_com', "
                "'airbnb', 'expedia', 'trip_com', 'tripadvisor', 'internal')"
            ),
            name="review_source_check",
        ),
        CheckConstraint(
            "sentiment IN ('positive', 'neutral', 'negative', 'mixed')",
            name="review_sentiment_check",
        ),
        CheckConstraint(
            ("response_status IN ('none', 'draft', 'awaiting_approval', 'published', 'failed')"),
            name="review_response_status_check",
        ),
        MIGRATION_ONLY,
    )

    property_id: UUID = Field(sa_type=Uuid)
    source: str = Field(sa_type=Text)
    external_id: str = Field(sa_type=Text)
    reservation_id: UUID | None = Field(default=None, sa_type=Uuid)
    guest_id: UUID | None = Field(default=None, sa_type=Uuid)
    unit_id: UUID | None = Field(default=None, sa_type=Uuid)
    author_name: str | None = Field(default=None, sa_type=Text)
    rating: Decimal | None = Field(default=None, max_digits=4, decimal_places=2)
    rating_scale: Decimal = Field(
        default=Decimal("5"),
        max_digits=4,
        decimal_places=1,
        sa_column_kwargs={"server_default": text("5")},
    )
    title: str | None = Field(default=None, sa_type=Text)
    body: str | None = Field(default=None, sa_type=Text)
    language: str | None = Field(default=None, sa_type=Text)
    published_at: dt.datetime | None = utc_datetime_field(nullable=True)  # type: ignore[assignment]
    themes: list[str] = Field(
        default_factory=list,
        sa_type=ARRAY(Text),
        sa_column_kwargs={"server_default": text("'{}'::text[]")},
        description="AI-tagged: cleanliness, staff, noise …",
    )
    sentiment: str | None = Field(default=None, sa_type=Text)
    response_body: str | None = Field(default=None, sa_type=Text)
    response_status: str = Field(
        default="none", sa_type=Text, sa_column_kwargs={"server_default": text("'none'::text")}
    )
    responded_at: dt.datetime | None = utc_datetime_field(nullable=True)  # type: ignore[assignment]
    responded_by: str | None = Field(default=None, sa_type=Text)


class ReviewCreate(SQLModel):
    """Fields accepted when creating a Review."""

    property_id: UUID
    source: ReviewSource
    external_id: str
    reservation_id: UUID | None = None
    guest_id: UUID | None = None
    unit_id: UUID | None = None
    author_name: str | None = None
    rating: Decimal | None = Field(default=None, max_digits=4, decimal_places=2)
    rating_scale: Decimal = Field(default=Decimal("5"), max_digits=4, decimal_places=1)
    title: str | None = None
    body: str | None = None
    language: str | None = None
    published_at: dt.datetime | None = None
    themes: list[str] = Field(default_factory=list)
    sentiment: ReviewSentiment | None = None
    response_body: str | None = None
    response_status: ReviewResponseStatus = "none"
    responded_at: dt.datetime | None = None
    responded_by: str | None = None


class ReviewUpdate(SQLModel):
    """Fields accepted when patching a Review (all optional)."""

    property_id: UUID | None = None
    source: ReviewSource | None = None
    external_id: str | None = None
    reservation_id: UUID | None = None
    guest_id: UUID | None = None
    unit_id: UUID | None = None
    author_name: str | None = None
    rating: Decimal | None = Field(default=None, max_digits=4, decimal_places=2)
    rating_scale: Decimal | None = Field(default=None, max_digits=4, decimal_places=1)
    title: str | None = None
    body: str | None = None
    language: str | None = None
    published_at: dt.datetime | None = None
    themes: list[str] | None = None
    sentiment: ReviewSentiment | None = None
    response_body: str | None = None
    response_status: ReviewResponseStatus | None = None
    responded_at: dt.datetime | None = None
    responded_by: str | None = None


class ReviewRead(SQLModel):
    """Fields returned when reading a Review."""

    id: UUID
    tenant_id: UUID
    property_id: UUID
    source: str
    external_id: str
    reservation_id: UUID | None
    guest_id: UUID | None
    unit_id: UUID | None
    author_name: str | None
    rating: Decimal | None
    rating_scale: Decimal
    title: str | None
    body: str | None
    language: str | None
    published_at: dt.datetime | None
    themes: list[str]
    sentiment: str | None
    response_body: str | None
    response_status: str
    responded_at: dt.datetime | None
    responded_by: str | None
    created_at: dt.datetime
    updated_at: dt.datetime
    created_by: str | None
    updated_by: str | None
