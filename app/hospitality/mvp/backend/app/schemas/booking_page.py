"""Requests and answers for the direct booking page. Guest answers carry no internal ids
beyond the room and plan the guest is choosing."""

import datetime as dt
from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.schemas.bookings import GuestNameText

Slug = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True, to_lower=True, pattern=r"^[a-z0-9][a-z0-9-]{1,38}[a-z0-9]$"
    ),
]
GuestPhone = Annotated[str, StringConstraints(strip_whitespace=True, min_length=8, max_length=24)]
IdempotencyKey = Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9_-]{16,64}$")]
PayChoice = Literal["deposit", "full"]
GuestLanguage = Literal["id", "en"]


class BookingPagePlan(BaseModel):
    id: UUID
    name: str
    sold: bool


class BookingPageSetup(BaseModel):
    slug: str | None
    is_published: bool
    plans: list[BookingPagePlan]


class BookingPageSaveRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    slug: Slug
    is_published: bool
    sold_plan_ids: list[UUID] = Field(default_factory=list, max_length=200)


class PublicRoomChoice(BaseModel):
    id: UUID
    name: str


class PublicPage(BaseModel):
    property_name: str
    city: str | None
    check_in_time: dt.time
    check_out_time: dt.time
    today: dt.date
    last_arrival: dt.date
    max_nights: int
    deposit_percent: int
    hold_minutes: int
    whatsapp_phone: str | None
    rooms: list[PublicRoomChoice]


class PublicDay(BaseModel):
    date: dt.date
    available: bool
    lowest_price: Decimal | None
    min_stay: int | None


class PublicCalendar(BaseModel):
    days: list[PublicDay]


class PublicRateOption(BaseModel):
    rate_plan_id: UUID
    name: str
    total: Decimal
    deposit: Decimal
    non_refundable: bool
    free_cancellation_days: int | None


class PublicRoomResult(BaseModel):
    id: UUID
    name: str
    max_guests: int
    options: list[PublicRateOption]


class PublicAvailability(BaseModel):
    nights: int
    rooms: list[PublicRoomResult]
    unavailable_reason: Literal["sold_out", "closed", "min_stay", "too_many_guests"] | None
    min_stay: int | None = None


class CheckoutRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    idempotency_key: IdempotencyKey
    arrival: dt.date
    departure: dt.date
    room_type_id: UUID
    rate_plan_id: UUID
    adults: int = Field(ge=1, le=50)
    children: int = Field(default=0, ge=0, le=50)
    guest_name: GuestNameText
    guest_phone: GuestPhone
    pay_choice: PayChoice
    expected_total: Decimal = Field(gt=0, max_digits=18, decimal_places=2)
    accepted_terms: bool
    language: GuestLanguage = "id"


class CheckoutResult(BaseModel):
    number: str
    pay_url: str
    booking_path: str
    amount_due: Decimal
    total: Decimal
    hold_expires_at: dt.datetime


class GuestBookingView(BaseModel):
    property_name: str
    property_whatsapp: str | None
    number: str
    status: Literal[
        "awaiting_payment", "confirmed", "cancelled", "in_house", "checked_out", "no_show"
    ]
    arrival: dt.date
    departure: dt.date
    nights: int
    room_name: str
    plan_name: str
    adults: int
    children: int
    guest_name: str
    phone_hint: str | None
    total: Decimal
    paid: Decimal
    balance: Decimal
    non_refundable: bool
    free_cancellation_days: int | None
    hold_expires_at: dt.datetime | None
    pay_url: str | None
    can_cancel: bool
    refund_if_cancelled: bool
    refund_due: bool
    language: str | None


class GuestCancelRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    accept_no_refund: bool = False
