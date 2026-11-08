"""Reservation entity — table ``reservation``.

Tenant database, G. Groups & reservations.

Booking header: status, channel, totals, policy snapshots.

Mirrors .ttest/contexts/schema-tenant.sql; the Alembic migration creates the table.
"""

import datetime as dt
from decimal import Decimal
from typing import Any, Literal
from uuid import UUID

from sqlalchemy import (
    CHAR,
    CheckConstraint,
    ForeignKeyConstraint,
    Index,
    Text,
    UniqueConstraint,
    Uuid,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel

from app.crud.base_model import MIGRATION_ONLY, TenantEntity, utc_datetime_field

ReservationStatus = Literal[
    "quote",
    "tentative",
    "waitlisted",
    "confirmed",
    "guaranteed",
    "in_house",
    "checked_out",
    "cancelled",
    "no_show",
    "expired",
]
ReservationPaymentCollectModel = Literal[
    "property",
    "channel",
    "mixed",
]
ReservationGuaranteeKind = Literal[
    "none",
    "card",
    "deposit",
    "full_prepay",
    "company",
    "voucher",
    "ota",
]


class Reservation(TenantEntity, table=True):
    """Booking header: status, channel, totals, policy snapshots."""

    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="reservation_tenant_id_id_key"),
        UniqueConstraint(
            "tenant_id", "confirmation_no", name="reservation_tenant_id_confirmation_no_key"
        ),
        ForeignKeyConstraint(
            ["tenant_id", "property_id"],
            ["property.tenant_id", "property.id"],
            name="reservation_tenant_id_property_id_fkey",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "booker_guest_id"],
            ["guest.tenant_id", "guest.id"],
            name="reservation_tenant_id_booker_guest_id_fkey",
            ondelete="SET NULL (booker_guest_id)",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "company_account_id"],
            ["account.tenant_id", "account.id"],
            name="reservation_tenant_id_company_account_id_fkey",
            ondelete="SET NULL (company_account_id)",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "agent_account_id"],
            ["account.tenant_id", "account.id"],
            name="reservation_tenant_id_agent_account_id_fkey",
            ondelete="SET NULL (agent_account_id)",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "group_block_id"],
            ["groupblock.tenant_id", "groupblock.id"],
            name="reservation_tenant_id_group_block_id_fkey",
            ondelete="SET NULL (group_block_id)",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "channel_id"],
            ["channel.tenant_id", "channel.id"],
            name="reservation_tenant_id_channel_id_fkey",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "market_segment_id"],
            ["marketsegment.tenant_id", "marketsegment.id"],
            name="reservation_tenant_id_market_segment_id_fkey",
            ondelete="SET NULL (market_segment_id)",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "promotion_id"],
            ["promotion.tenant_id", "promotion.id"],
            name="reservation_tenant_id_promotion_id_fkey",
            ondelete="SET NULL (promotion_id)",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "cancel_reason_id"],
            ["reasoncode.tenant_id", "reasoncode.id"],
            name="reservation_tenant_id_cancel_reason_id_fkey",
            ondelete="SET NULL (cancel_reason_id)",
        ),
        CheckConstraint(
            (
                "status IN ('quote', 'tentative', 'waitlisted', 'confirmed', "
                "'guaranteed', 'in_house', 'checked_out', 'cancelled', 'no_show', "
                "'expired')"
            ),
            name="reservation_status_check",
        ),
        CheckConstraint("(adults >= 0)", name="reservation_adults_check"),
        CheckConstraint("(children >= 0)", name="reservation_children_check"),
        CheckConstraint(
            "payment_collect_model IN ('property', 'channel', 'mixed')",
            name="reservation_payment_collect_model_check",
        ),
        CheckConstraint(
            (
                "guarantee_kind IN ('none', 'card', 'deposit', 'full_prepay', 'company', "
                "'voucher', 'ota')"
            ),
            name="reservation_guarantee_kind_check",
        ),
        CheckConstraint("(departure_date >= arrival_date)", name="reservation_check"),
        Index("ix_reservation_dates", "tenant_id", "property_id", "arrival_date", "departure_date"),
        Index("ix_reservation_status", "tenant_id", "property_id", "status"),
        Index(
            "ux_reservation_channel_ref",
            "tenant_id",
            "channel_id",
            "channel_reference",
            unique=True,
            postgresql_where=text("channel_reference IS NOT NULL"),
        ),
        MIGRATION_ONLY,
    )

    property_id: UUID = Field(sa_type=Uuid)
    confirmation_no: str = Field(sa_type=Text)
    status: str = Field(
        default="confirmed",
        sa_type=Text,
        sa_column_kwargs={"server_default": text("'confirmed'::text")},
    )
    option_expires_at: dt.datetime | None = utc_datetime_field(
        nullable=True, description="quote / tentative / unpaid-DP hold"
    )  # type: ignore[assignment]
    booker_guest_id: UUID | None = Field(default=None, sa_type=Uuid)
    company_account_id: UUID | None = Field(default=None, sa_type=Uuid)
    agent_account_id: UUID | None = Field(default=None, sa_type=Uuid)
    group_block_id: UUID | None = Field(default=None, sa_type=Uuid)
    channel_id: UUID = Field(sa_type=Uuid)
    channel_reference: str | None = Field(default=None, sa_type=Text, description="OTA booking id")
    market_segment_id: UUID | None = Field(default=None, sa_type=Uuid)
    source_detail: dict[str, Any] = Field(
        default_factory=dict,
        sa_type=JSONB,
        sa_column_kwargs={"server_default": text("'{}'::jsonb")},
        description='{"utm_source":"google","landing":"free_booking_link"}',
    )
    arrival_date: dt.date = Field(description="min over reservation units")
    departure_date: dt.date = Field(description="max over reservation units")
    adults: int = Field(default=1, sa_column_kwargs={"server_default": text("1")})
    children: int = Field(default=0, sa_column_kwargs={"server_default": text("0")})
    currency: str = Field(
        default="IDR", sa_type=CHAR(3), sa_column_kwargs={"server_default": text("'IDR'::bpchar")}
    )
    total_amount: Decimal = Field(
        default=Decimal("0"),
        max_digits=18,
        decimal_places=2,
        sa_column_kwargs={"server_default": text("0")},
    )
    total_tax: Decimal = Field(
        default=Decimal("0"),
        max_digits=18,
        decimal_places=2,
        sa_column_kwargs={"server_default": text("0")},
    )
    paid_amount: Decimal = Field(
        default=Decimal("0"),
        max_digits=18,
        decimal_places=2,
        sa_column_kwargs={"server_default": text("0")},
    )
    balance_due: Decimal = Field(
        default=Decimal("0"),
        max_digits=18,
        decimal_places=2,
        sa_column_kwargs={"server_default": text("0")},
    )
    commission_amount: Decimal | None = Field(default=None, max_digits=18, decimal_places=2)
    payment_collect_model: str = Field(
        default="property",
        sa_type=Text,
        sa_column_kwargs={"server_default": text("'property'::text")},
    )
    guarantee_kind: str = Field(
        default="none", sa_type=Text, sa_column_kwargs={"server_default": text("'none'::text")}
    )
    cancellation_policy_snapshot: dict[str, Any] = Field(
        default_factory=dict,
        sa_type=JSONB,
        sa_column_kwargs={"server_default": text("'{}'::jsonb")},
        description="policy as booked (BR-06)",
    )
    payment_policy_snapshot: dict[str, Any] = Field(
        default_factory=dict,
        sa_type=JSONB,
        sa_column_kwargs={"server_default": text("'{}'::jsonb")},
    )
    promotion_id: UUID | None = Field(default=None, sa_type=Uuid)
    eta: dt.time | None = Field(default=None)
    transport: dict[str, Any] = Field(
        default_factory=dict,
        sa_type=JSONB,
        sa_column_kwargs={"server_default": text("'{}'::jsonb")},
        description="flight, vehicle plate, RV length",
    )
    special_requests: str | None = Field(default=None, sa_type=Text)
    internal_notes: str | None = Field(default=None, sa_type=Text)
    language: str | None = Field(default=None, sa_type=Text)
    booked_at: dt.datetime = utc_datetime_field(
        nullable=False, default_now=True, server_default_now=True
    )  # type: ignore[assignment]
    booked_by: str | None = Field(default=None, sa_type=Text)
    cancelled_at: dt.datetime | None = utc_datetime_field(nullable=True)  # type: ignore[assignment]
    cancel_reason_id: UUID | None = Field(default=None, sa_type=Uuid)
    cancellation_fee: Decimal | None = Field(default=None, max_digits=18, decimal_places=2)
    is_complimentary: bool = Field(
        default=False, sa_column_kwargs={"server_default": text("false")}
    )
    is_house_use: bool = Field(default=False, sa_column_kwargs={"server_default": text("false")})
    is_owner_stay: bool = Field(default=False, sa_column_kwargs={"server_default": text("false")})
    version: int = Field(default=1, sa_column_kwargs={"server_default": text("1")})


class ReservationCreate(SQLModel):
    """Fields accepted when creating a Reservation."""

    property_id: UUID
    confirmation_no: str
    status: ReservationStatus = "confirmed"
    option_expires_at: dt.datetime | None = None
    booker_guest_id: UUID | None = None
    company_account_id: UUID | None = None
    agent_account_id: UUID | None = None
    group_block_id: UUID | None = None
    channel_id: UUID
    channel_reference: str | None = None
    market_segment_id: UUID | None = None
    source_detail: dict[str, Any] = Field(default_factory=dict)
    arrival_date: dt.date
    departure_date: dt.date
    adults: int = Field(default=1, ge=0)
    children: int = Field(default=0, ge=0)
    currency: str = Field(default="IDR", min_length=3, max_length=3)
    total_amount: Decimal = Field(default=Decimal("0"), max_digits=18, decimal_places=2)
    total_tax: Decimal = Field(default=Decimal("0"), max_digits=18, decimal_places=2)
    paid_amount: Decimal = Field(default=Decimal("0"), max_digits=18, decimal_places=2)
    balance_due: Decimal = Field(default=Decimal("0"), max_digits=18, decimal_places=2)
    commission_amount: Decimal | None = Field(default=None, max_digits=18, decimal_places=2)
    payment_collect_model: ReservationPaymentCollectModel = "property"
    guarantee_kind: ReservationGuaranteeKind = "none"
    cancellation_policy_snapshot: dict[str, Any] = Field(default_factory=dict)
    payment_policy_snapshot: dict[str, Any] = Field(default_factory=dict)
    promotion_id: UUID | None = None
    eta: dt.time | None = None
    transport: dict[str, Any] = Field(default_factory=dict)
    special_requests: str | None = None
    internal_notes: str | None = None
    language: str | None = None
    booked_at: dt.datetime = Field(default_factory=lambda: dt.datetime.now(dt.UTC))
    booked_by: str | None = None
    cancelled_at: dt.datetime | None = None
    cancel_reason_id: UUID | None = None
    cancellation_fee: Decimal | None = Field(default=None, max_digits=18, decimal_places=2)
    is_complimentary: bool = False
    is_house_use: bool = False
    is_owner_stay: bool = False


class ReservationUpdate(SQLModel):
    """Fields accepted when patching a Reservation (all optional)."""

    property_id: UUID | None = None
    confirmation_no: str | None = None
    status: ReservationStatus | None = None
    option_expires_at: dt.datetime | None = None
    booker_guest_id: UUID | None = None
    company_account_id: UUID | None = None
    agent_account_id: UUID | None = None
    group_block_id: UUID | None = None
    channel_id: UUID | None = None
    channel_reference: str | None = None
    market_segment_id: UUID | None = None
    source_detail: dict[str, Any] | None = None
    arrival_date: dt.date | None = None
    departure_date: dt.date | None = None
    adults: int | None = Field(default=None, ge=0)
    children: int | None = Field(default=None, ge=0)
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    total_amount: Decimal | None = Field(default=None, max_digits=18, decimal_places=2)
    total_tax: Decimal | None = Field(default=None, max_digits=18, decimal_places=2)
    paid_amount: Decimal | None = Field(default=None, max_digits=18, decimal_places=2)
    balance_due: Decimal | None = Field(default=None, max_digits=18, decimal_places=2)
    commission_amount: Decimal | None = Field(default=None, max_digits=18, decimal_places=2)
    payment_collect_model: ReservationPaymentCollectModel | None = None
    guarantee_kind: ReservationGuaranteeKind | None = None
    cancellation_policy_snapshot: dict[str, Any] | None = None
    payment_policy_snapshot: dict[str, Any] | None = None
    promotion_id: UUID | None = None
    eta: dt.time | None = None
    transport: dict[str, Any] | None = None
    special_requests: str | None = None
    internal_notes: str | None = None
    language: str | None = None
    booked_at: dt.datetime | None = None
    booked_by: str | None = None
    cancelled_at: dt.datetime | None = None
    cancel_reason_id: UUID | None = None
    cancellation_fee: Decimal | None = Field(default=None, max_digits=18, decimal_places=2)
    is_complimentary: bool | None = None
    is_house_use: bool | None = None
    is_owner_stay: bool | None = None


class ReservationRead(SQLModel):
    """Fields returned when reading a Reservation."""

    id: UUID
    tenant_id: UUID
    property_id: UUID
    confirmation_no: str
    status: str
    option_expires_at: dt.datetime | None
    booker_guest_id: UUID | None
    company_account_id: UUID | None
    agent_account_id: UUID | None
    group_block_id: UUID | None
    channel_id: UUID
    channel_reference: str | None
    market_segment_id: UUID | None
    source_detail: dict[str, Any]
    arrival_date: dt.date
    departure_date: dt.date
    adults: int
    children: int
    currency: str
    total_amount: Decimal
    total_tax: Decimal
    paid_amount: Decimal
    balance_due: Decimal
    commission_amount: Decimal | None
    payment_collect_model: str
    guarantee_kind: str
    cancellation_policy_snapshot: dict[str, Any]
    payment_policy_snapshot: dict[str, Any]
    promotion_id: UUID | None
    eta: dt.time | None
    transport: dict[str, Any]
    special_requests: str | None
    internal_notes: str | None
    language: str | None
    booked_at: dt.datetime
    booked_by: str | None
    cancelled_at: dt.datetime | None
    cancel_reason_id: UUID | None
    cancellation_fee: Decimal | None
    is_complimentary: bool
    is_house_use: bool
    is_owner_stay: bool
    version: int
    created_at: dt.datetime
    updated_at: dt.datetime
    created_by: str | None
    updated_by: str | None
