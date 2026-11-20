"""Shapes for the rooms-and-prices calendar: the read model and one change request."""

import datetime as dt
from decimal import Decimal
from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.payment_links import Rupiah

# Widest window one read may ask for (two months on screen).
MAX_READ_DAYS = 62
MAX_ROOM_TYPES_PER_CHANGE = 200
MAX_MIN_STAY_NIGHTS = 365
Weekday = Annotated[int, Field(ge=0, le=6, description="0 = Monday … 6 = Sunday")]


class _Change(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SetPrice(_Change):
    kind: Literal["set_price"]
    rate_plan_id: UUID
    amount: Rupiah


class ClearPrice(_Change):
    """Back to the rate plan's base price."""

    kind: Literal["clear_price"]
    rate_plan_id: UUID


class Close(_Change):
    kind: Literal["close"]


class Open(_Change):
    kind: Literal["open"]


class SetMinStay(_Change):
    """Guests arriving on these dates must stay at least `nights` (1 = no rule)."""

    kind: Literal["set_min_stay"]
    nights: int = Field(ge=1, le=MAX_MIN_STAY_NIGHTS)


class ClearMinStay(_Change):
    kind: Literal["clear_min_stay"]


CalendarChange = Annotated[
    SetPrice | ClearPrice | Close | Open | SetMinStay | ClearMinStay,
    Field(discriminator="kind"),
]


class CalendarChangeRequest(BaseModel):
    """One change applied to every chosen room type on every chosen date."""

    model_config = ConfigDict(extra="forbid")

    start: dt.date
    end: dt.date
    weekdays: list[Weekday] | None = Field(
        default=None, min_length=1, max_length=7, description="Omitted = every day."
    )
    room_type_ids: list[UUID] = Field(min_length=1, max_length=MAX_ROOM_TYPES_PER_CHANGE)
    change: CalendarChange

    @model_validator(mode="after")
    def _no_repeats(self) -> Self:
        if len(set(self.room_type_ids)) != len(self.room_type_ids):
            raise ValueError("a room type may be listed only once")
        if self.weekdays is not None and len(set(self.weekdays)) != len(self.weekdays):
            raise ValueError("a weekday may be listed only once")
        return self


class CalendarChangeResult(BaseModel):
    dates: int
    room_types: int


class DayPrice(BaseModel):
    rate_plan_id: UUID
    amount: Decimal
    is_override: bool  # False = the rate plan's base price


class CalendarDay(BaseModel):
    date: dt.date
    available: int  # units that can still be sold
    closed: bool
    min_stay: int | None  # for guests arriving this date
    prices: list[DayPrice]


class CalendarRatePlan(BaseModel):
    id: UUID
    name: str


class CalendarRoomType(BaseModel):
    id: UUID
    name: str
    units: int
    rate_plans: list[CalendarRatePlan]  # the plans that sell this room type
    days: list[CalendarDay]


class CalendarRead(BaseModel):
    start: dt.date
    end: dt.date
    today: dt.date  # at the property
    last_editable_date: dt.date
    room_types: list[CalendarRoomType]
