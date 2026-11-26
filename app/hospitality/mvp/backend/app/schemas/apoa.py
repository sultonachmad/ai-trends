"""The APOA worklist and marks. Numbers leave the server masked only."""

import datetime as dt
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, StringConstraints

from app.schemas.plain_text import PLAIN_TEXT

Step = Literal["arrival", "departure"]
Reason = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=3, max_length=300, pattern=PLAIN_TEXT)
]
Reference = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80, pattern=PLAIN_TEXT)
]


class StepState(BaseModel):
    status: str  # pending, submitted or not_required
    at: dt.datetime | None = None
    by: str | None = None
    reference: str | None = None
    reason: str | None = None


class ApoaItem(BaseModel):
    """One foreign guest on one stay, and where they are in APOA."""

    booking_id: UUID
    booking_number: str
    guest_id: UUID
    document_id: UUID
    full_name: str
    nationality: str
    masked_number: str | None
    visa_type: str | None
    room: str | None
    checked_in_at: dt.datetime
    checked_out_at: dt.datetime | None
    step: Step | None  # what is due next; None when both steps are done
    due_at: dt.datetime | None
    overdue: bool
    has_image: bool
    arrival: StepState
    departure: StepState


class Unregistered(BaseModel):
    """A foreign party with fewer guests listed than the booking is for."""

    booking_id: UUID
    booking_number: str
    guest_name: str
    listed: int
    expected: int


class ApoaList(BaseModel):
    date: dt.date
    deadline_hours: int
    to_report: list[ApoaItem]
    to_check_out: list[ApoaItem]
    done: list[ApoaItem]
    unregistered: list[Unregistered]
    truncated: bool = False  # more stays than the list shows; the oldest check-outs are left out


class ApoaCounts(BaseModel):
    due: int = 0
    overdue: int = 0


class MarkRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    booking_id: UUID
    guest_id: UUID
    step: Step
    reference: Reference | None = None


class ReasonRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    booking_id: UUID
    guest_id: UUID
    step: Step
    reason: Reason
