"""Shapes for bookings: the stay, the staff form, the list and the detail view."""

import datetime as dt
from decimal import Decimal
from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from app.schemas.inbox import PhoneInput
from app.schemas.rooms import UNSAFE_IN_NAMES
from app.services.booking_sources import StaffSource

# One line of plain text, safe to show to staff and send in messages.
GuestNameText = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True, min_length=1, max_length=120, pattern=f"^[^{UNSAFE_IN_NAMES}]+$"
    ),
]
# Free text that may have line breaks, but no other control, invisible or
# text-direction characters.
_UNSAFE_IN_NOTES = UNSAFE_IN_NAMES.replace("\x00-\x1f", "\x00-\x09\x0b-\x1f")
NotesText = Annotated[
    str,
    StringConstraints(strip_whitespace=True, max_length=1000, pattern=f"^[^{_UNSAFE_IN_NOTES}]*$"),
]
# Whole rupiah for a booking total or a payment: at most 12 digits, so sums of many of
# them stay far inside the stored precision.
Rupiah = Annotated[Decimal, Field(gt=0, max_digits=12, decimal_places=0)]
ReasonText = Annotated[
    str,
    StringConstraints(strip_whitespace=True, max_length=200, pattern=f"^[^{UNSAFE_IN_NAMES}]*$"),
]
SearchText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)]

BookingTab = Literal["upcoming", "staying", "past", "cancelled"]
BookingStatus = Literal["confirmed", "cancelled"]
PaymentState = Literal["unpaid", "partly_paid", "paid", "overpaid"]
PaymentMethodIn = Literal["cash", "bank_transfer", "other"]
UNITS_CEILING = 100
GUESTS_CEILING = 500


class StayFields(BaseModel):
    """What is booked: dates, room type, how many units, on which rate plan, for whom."""

    model_config = ConfigDict(extra="forbid")

    arrival: dt.date
    departure: dt.date
    room_type_id: UUID
    rate_plan_id: UUID
    units: int = Field(default=1, ge=1, le=UNITS_CEILING)
    adults: int = Field(default=2, ge=1, le=GUESTS_CEILING)
    children: int = Field(default=0, ge=0, le=GUESTS_CEILING)


class BookingQuoteRequest(StayFields):
    """Price and availability for a stay, without saving anything."""

    exclude_booking_id: UUID | None = Field(
        default=None, description="When changing a booking: do not count its own units."
    )


class QuoteNight(BaseModel):
    date: dt.date
    amount: Decimal  # one unit, this night
    available: int  # units left before this booking (may be negative)
    closed: bool


class BookingQuote(BaseModel):
    nights: list[QuoteNight]
    total_amount: Decimal  # every night, every unit
    short_dates: list[dt.date]  # nights without enough units
    closed_dates: list[dt.date]
    min_stay: int | None  # the arrival date's rule, when the stay is shorter than it
    max_guests: int  # for the chosen number of units


class BookingCreateRequest(StayFields):
    guest_name: GuestNameText
    guest_phone: PhoneInput | None = None
    source: StaffSource = "whatsapp"
    total_amount: Rupiah | None = Field(
        default=None, description="Omitted = the calendar price of the stay."
    )
    notes: NotesText | None = None
    allow_overbooking: bool = Field(
        default=False, description="Book even when a night has no unit left."
    )
    conversation_id: UUID | None = Field(
        default=None, description="The chat this booking was made from: its guest is used."
    )


class BookingUpdateRequest(BaseModel):
    """Only the fields sent are changed."""

    model_config = ConfigDict(extra="forbid")

    arrival: dt.date | None = None
    departure: dt.date | None = None
    room_type_id: UUID | None = None
    rate_plan_id: UUID | None = None
    units: int | None = Field(default=None, ge=1, le=UNITS_CEILING)
    adults: int | None = Field(default=None, ge=1, le=GUESTS_CEILING)
    children: int | None = Field(default=None, ge=0, le=GUESTS_CEILING)
    guest_name: GuestNameText | None = None
    guest_phone: PhoneInput | None = None
    source: StaffSource | None = None
    total_amount: Rupiah | None = None
    reset_price: bool = Field(
        default=False, description="Drop a hand-set total and use the calendar price again."
    )
    notes: NotesText | None = None
    allow_overbooking: bool = False

    @model_validator(mode="after")
    def _one_price_instruction(self) -> Self:
        if self.reset_price and self.total_amount is not None:
            raise ValueError("send a total or reset the price, not both")
        return self


class BookingCancelRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: ReasonText | None = None


class PaymentRecordRequest(BaseModel):
    """Money staff received for a booking outside the product."""

    model_config = ConfigDict(extra="forbid")

    amount: Rupiah
    method: PaymentMethodIn
    received_on: dt.date
    note: ReasonText | None = None


class NamedRef(BaseModel):
    id: UUID
    name: str


class BookingGuest(BaseModel):
    id: UUID | None
    name: str
    phone: str | None


class BookingSource(BaseModel):
    code: str
    name: str
    is_direct: bool


class BookingRead(BaseModel):
    id: UUID
    number: str
    status: BookingStatus
    arrival: dt.date
    departure: dt.date
    nights: int
    room_type: NamedRef
    rate_plan: NamedRef
    units: int
    adults: int
    children: int
    guest: BookingGuest
    source: BookingSource
    total_amount: Decimal
    paid_amount: Decimal
    balance_due: Decimal
    payment_state: PaymentState
    price_edited: bool  # staff set the total by hand
    overbooking_risk: bool  # a night of this stay has more sold than there are units
    notes: str | None
    cancel_note: str | None
    cancelled_at: dt.datetime | None
    created_at: dt.datetime


class BookingNight(BaseModel):
    date: dt.date
    amount: Decimal  # all units of the booking, this night


class BookingPayment(BaseModel):
    id: UUID
    amount: Decimal
    method: str
    received_on: dt.date
    note: str | None
    recorded_at: dt.datetime


class BookingTerms(BaseModel):
    non_refundable: bool
    free_cancellation_days: int | None


class BookingDetail(BookingRead):
    nightly: list[BookingNight]
    payments: list[BookingPayment]
    terms: BookingTerms | None


class BookingPage(BaseModel):
    items: list[BookingRead]
    next_cursor: str | None
