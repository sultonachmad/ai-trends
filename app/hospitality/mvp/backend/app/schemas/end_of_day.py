"""Cash drawers and closing a day."""

import datetime as dt
from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.schemas.bookings import Rupiah
from app.schemas.plain_text import PLAIN_TEXT

Reason = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=3, max_length=300, pattern=PLAIN_TEXT)
]
Note = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=300, pattern=PLAIN_TEXT)
]
Float = Annotated[Decimal, Field(ge=0, le=1_000_000_000, max_digits=18, decimal_places=2)]


class MethodTotal(BaseModel):
    method: str
    received: Decimal
    paid_out: Decimal  # refunds and paid-outs


class DrawerRead(BaseModel):
    id: UUID
    staff_name: str
    business_date: dt.date
    opened_at: dt.datetime
    closed_at: dt.datetime | None
    status: str
    opening_float: Decimal
    cash_in: Decimal
    cash_out: Decimal  # cash refunds
    paid_outs: Decimal
    expected_cash: Decimal
    counted_cash: Decimal | None
    variance: Decimal | None
    notes: str | None
    by_method: list[MethodTotal]


class MyDrawer(BaseModel):
    drawer: DrawerRead | None


class OpenDrawerRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    opening_float: Float


class PaidOutRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    amount: Rupiah
    reason: Reason


class CloseDrawerRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    counted_cash: Float
    note: Note | None = None


class CheckItem(BaseModel):
    booking_id: UUID | None = None
    label: str


class DayCheck(BaseModel):
    code: str
    level: Literal["blocking", "warning"]
    count: int
    items: list[CheckItem]


class DayRead(BaseModel):
    date: dt.date
    today: dt.date  # the property's date now
    status: str  # open or closed
    closed_at: dt.datetime | None
    closed_by: str | None
    can_close: bool
    checks: list[DayCheck]
    summary: dict  # see day_summary.read_summary; frozen once closed
    drawers: list[DrawerRead]


class CloseDayRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    override_reason: Reason | None = None


class ReopenDayRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: Reason


class DayCloseState(BaseModel):
    """For the front desk: the oldest past day still open, if any."""

    unclosed: dt.date | None = None
