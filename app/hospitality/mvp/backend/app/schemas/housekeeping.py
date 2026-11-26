"""Rooms to clean: the phone board, its actions, and problems for the front desk."""

import datetime as dt
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.schemas.plain_text import PLAIN_TEXT

Note = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=300, pattern=PLAIN_TEXT)
]
ProblemKind = Literal["dnd", "refused", "repair", "empty", "other"]
ReadyWhen = Literal["clean", "inspected"]
Stayover = Literal["daily", "on_request"]


class _Request(BaseModel):
    model_config = ConfigDict(extra="forbid")


class HkGuest(BaseModel):
    name: str
    adults: int
    children: int
    arrival: dt.date
    departure: dt.date
    eta: dt.time | None = None
    special_requests: str | None = None


class HkTask(BaseModel):
    id: UUID
    unit_id: UUID
    room_name: str
    room_type: str
    kind: str
    status: str
    priority: str
    assigned_staff_id: UUID | None
    assigned_name: str | None
    mine: bool
    arriving: HkGuest | None
    staying: HkGuest | None
    started_at: dt.datetime | None
    completed_at: dt.datetime | None
    awaiting_inspection: bool
    inspection_result: str | None
    notes: str | None
    problem_kind: str | None
    problem_note: str | None
    problem_at: dt.datetime | None


class HkRoom(BaseModel):
    id: UUID
    name: str
    room_type: str
    hk_status: str
    fo_status: str
    service_status: str
    arrival_today: bool
    task_id: UUID | None
    task_status: str | None
    assigned_name: str | None


class HkStaff(BaseModel):
    id: UUID
    name: str


class HkBoard(BaseModel):
    date: dt.date
    tasks: list[HkTask]
    rooms: list[HkRoom]
    staff: list[HkStaff]
    my_staff_id: UUID | None
    big_buttons: bool
    ready_when: ReadyWhen
    stayover: Stayover
    poll_seconds: int


class HkProblem(BaseModel):
    task_id: UUID
    unit_id: UUID
    room_name: str
    kind: str
    note: str | None
    at: dt.datetime
    by_name: str | None


class ProblemRequest(_Request):
    kind: ProblemKind
    note: Note | None = None


class AssignRequest(_Request):
    staff_id: UUID | None = None


class SplitRequest(_Request):
    staff_ids: list[UUID] = Field(min_length=1, max_length=50)


class InspectRequest(_Request):
    passed: bool
    reason: Note | None = None


class RoomStatusRequest(_Request):
    hk_status: Literal["dirty", "clean", "inspected"]


class HkSettingsRequest(_Request):
    ready_when: ReadyWhen
    stayover: Stayover


class ModeRequest(_Request):
    big_buttons: bool
