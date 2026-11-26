"""What the front desk page reads and sends."""

import datetime as dt
from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, StringConstraints

from app.schemas.apoa import ApoaCounts

UndoReason = Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=300)]
EarlyChoice = Literal["keep_price", "nights_stayed"]


class FrontDeskRoom(BaseModel):
    """One room line of a booking and the room given to it, if any."""

    line_id: UUID
    unit_id: UUID | None
    name: str | None
    hk_status: str | None
    service_status: str | None
    locked: bool


class FrontDeskEntry(BaseModel):
    id: UUID
    number: str
    status: str
    guest_name: str
    guest_phone: str | None
    arrival: dt.date
    departure: dt.date
    nights: int
    room_type: str
    units: int
    adults: int
    children: int
    source: str
    total_amount: Decimal
    total_with_tax: Decimal
    balance_due: Decimal
    overdue: bool  # the arrival or departure should already have happened
    can_undo: bool = False  # today's check-in can still be taken back
    rooms: list[FrontDeskRoom]


class RoomToday(BaseModel):
    id: UUID
    name: str
    room_type: str
    hk_status: str
    fo_status: str
    service_status: str
    guest_name: str | None
    booking_id: UUID | None
    departure: dt.date | None


class FrontDeskToday(BaseModel):
    date: dt.date
    arrivals: list[FrontDeskEntry]
    in_house: list[FrontDeskEntry]
    departures: list[FrontDeskEntry]
    done_today: list[FrontDeskEntry]  # finished today and still possible to undo
    rooms: list[RoomToday]
    apoa: ApoaCounts = ApoaCounts()  # foreign guests due or overdue in APOA


class FreeRoom(BaseModel):
    id: UUID
    name: str
    hk_status: str
    service_status: str
    ready: bool


class AssignRoomRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    unit_id: UUID | None
    accept_not_ready: bool = False


class LockRoomRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    locked: bool


class CheckInRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    accept_not_ready: bool = False
    # Check in although the main guest's ID is not confirmed. Needs `bookings:edit`.
    no_id_reason: UndoReason | None = None


class CheckOutRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    early: EarlyChoice | None = None
    leave_unpaid_reason: UndoReason | None = None  # needs bookings:edit


class UndoRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: UndoReason
