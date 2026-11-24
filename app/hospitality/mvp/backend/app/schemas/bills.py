"""The guest bill and its receipts."""

import datetime as dt
from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.schemas.bookings import BookingPayment, Rupiah

ChargeCategory = Literal[
    "extra_bed", "food_drinks", "laundry", "transport", "minibar", "late_checkout", "other"
]
LineCategory = Literal[
    "extra_bed",
    "food_drinks",
    "laundry",
    "transport",
    "minibar",
    "late_checkout",
    "other",
    "discount",
    "correction",
]
LineText = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True, min_length=1, max_length=200, pattern=r"^[^<>\x00-\x1f]*$"
    ),
]
ReasonLine = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True, min_length=3, max_length=200, pattern=r"^[^<>\x00-\x1f]*$"
    ),
]
MAX_QUANTITY = 999
MAX_CORRECTION = Decimal("100000000")  # Rp 100 million per correction


class ChargeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    category: ChargeCategory
    description: LineText
    quantity: int = Field(ge=1, le=MAX_QUANTITY)
    unit_price: Rupiah


class DiscountRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    amount: Rupiah
    reason: ReasonLine


class CorrectionRequest(BaseModel):
    """A signed amount: negative takes money off, positive adds it."""

    model_config = ConfigDict(extra="forbid")

    amount: Decimal = Field(ge=-MAX_CORRECTION, le=MAX_CORRECTION, decimal_places=0)
    reason: ReasonLine


class VoidRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: ReasonLine


class BillNight(BaseModel):
    date: dt.date
    amount: Decimal


class BillLine(BaseModel):
    id: UUID
    category: LineCategory
    description: str
    quantity: Decimal
    unit_price: Decimal | None
    amount: Decimal
    business_date: dt.date
    posted_at: dt.datetime
    voided: bool
    void_reason: str | None
    can_void: bool


class BillTaxes(BaseModel):
    confirmed: bool  # the owner has set and confirmed tax rates
    included: bool  # nett: inside the prices; ++: added on top
    service: Decimal
    pbjt: Decimal


class ReceiptSummary(BaseModel):
    id: UUID
    number: str
    issued_at: dt.datetime
    total: Decimal
    replaced: bool = False  # a later check-out issued a newer receipt


class BillRead(BaseModel):
    booking_id: UUID
    number: str
    status: str
    guest_name: str
    arrival: dt.date
    departure: dt.date
    closed: bool  # no new charges: checked out, cancelled, no-show or awaiting payment
    paid_to_channel: bool  # the guest paid the channel for the room
    left_unpaid: bool
    room_type: str
    room_nights: list[BillNight]
    room_total: Decimal
    lines: list[BillLine]
    extras_total: Decimal
    taxes: BillTaxes
    payments: list[BookingPayment]
    paid: Decimal
    balance: Decimal
    receipts: list[ReceiptSummary]


class ReceiptLine(BaseModel):
    description: str
    quantity: Decimal
    unit_price: Decimal
    amount: Decimal
    is_room: bool


class ReceiptRead(BaseModel):
    id: UUID
    number: str
    issued_at: dt.datetime
    business_date: dt.date | None
    issuer_name: str
    issuer_tax_id: str | None
    property_name: str
    booking_number: str
    guest_name: str
    arrival: dt.date
    departure: dt.date
    paid_to_channel: bool
    lines: list[ReceiptLine]
    taxes_included: bool  # nett: service and PBJT are inside the line amounts
    subtotal: Decimal
    service: Decimal
    pbjt: Decimal
    total: Decimal
    paid: Decimal
    balance: Decimal
