"""Repair requests: the board, a request, and the actions on it."""

import datetime as dt
from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.schemas.plain_text import PLAIN_TEXT

Category = Literal["ac", "plumbing", "electrical", "furniture", "tv_wifi", "door_lock", "other"]
Text300 = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=300, pattern=PLAIN_TEXT)
]
Text80 = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80, pattern=PLAIN_TEXT)
]
Cost = Annotated[Decimal, Field(ge=0, le=1_000_000_000, max_digits=18, decimal_places=2)]


class _Request(BaseModel):
    model_config = ConfigDict(extra="forbid")


class OffSale(BaseModel):
    first_night: dt.date
    last_night: dt.date


class MaintRequest(BaseModel):
    id: UUID
    number: str
    unit_id: UUID | None
    room_name: str | None
    place: str | None
    category: str
    urgent: bool
    description: str
    status: str
    status_note: str | None
    reported_by_name: str | None
    reported_at: dt.datetime
    from_housekeeping: bool
    assigned_staff_id: UUID | None
    assigned_name: str | None
    vendor_name: str | None
    mine: bool
    has_photo: bool
    off_sale: OffSale | None
    cost: Decimal | None
    completed_at: dt.datetime | None


class MaintRoom(BaseModel):
    id: UUID
    name: str


class MaintBoard(BaseModel):
    today: dt.date
    requests: list[MaintRequest]
    rooms: list[MaintRoom]
    staff: list[MaintRoom]  # id and name of active staff, for giving a repair to someone


class MaintNotice(BaseModel):
    """For the front desk: an urgent repair or a room off sale."""

    id: UUID
    number: str
    room_name: str | None
    place: str | None
    category: str
    urgent: bool
    off_sale_until: dt.date | None


class WaitRequest(_Request):
    note: Text300


class FixRequest(_Request):
    note: Text300 | None = None
    cost: Cost | None = None


class CancelRequest(_Request):
    reason: Text300


class AssignRequest(_Request):
    staff_id: UUID | None = None
    vendor_name: Text80 | None = None


class OffSaleRequest(_Request):
    first_night: dt.date
    last_night: dt.date
