"""A month's service charge and PBJT, by day and by booking."""

import datetime as dt
from decimal import Decimal

from pydantic import BaseModel

ZERO = Decimal("0")


class TaxAmounts(BaseModel):
    room_nights: int = 0
    room_base: Decimal = ZERO
    extras_base: Decimal = ZERO
    service: Decimal = ZERO
    pbjt: Decimal = ZERO
    untaxed: Decimal = ZERO  # extras the region does not tax
    channel_nights: int = 0  # paid through a channel: tax inside the price, reported apart
    channel_base: Decimal = ZERO
    channel_service: Decimal = ZERO
    channel_pbjt: Decimal = ZERO


class TaxDay(TaxAmounts):
    date: dt.date


class TaxBooking(TaxAmounts):
    booking_id: str
    number: str
    arrival: dt.date
    departure: dt.date
    source: str
    price_mode: str


class TaxMonth(BaseModel):
    month: str  # YYYY-MM
    first_day: dt.date
    last_day: dt.date
    is_set: bool  # tax rates confirmed in settings
    draft: bool  # some day of the month is not closed yet
    closed_days: int
    days_in_month: int
    days: list[TaxDay]
    bookings: list[TaxBooking]
    totals: TaxAmounts
