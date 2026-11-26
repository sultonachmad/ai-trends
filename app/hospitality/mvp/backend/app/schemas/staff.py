"""The team: staff members, join links and the roles they can be given."""

import datetime as dt
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, StringConstraints

from app.schemas.plain_text import PLAIN_TEXT

StaffRole = Literal["manager", "front_desk", "housekeeper"]
Name = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80, pattern=PLAIN_TEXT)
]
Email = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        to_lower=True,
        min_length=3,
        max_length=254,
        pattern=r"^[^@\s<>]+@[^@\s<>]+\.[^@\s<>]+$",
    ),
]


class _Request(BaseModel):
    model_config = ConfigDict(extra="forbid")


class InviteRequest(_Request):
    name: Name
    email: Email
    role: StaffRole


class RoleRequest(_Request):
    role: StaffRole


class InviteRead(BaseModel):
    id: UUID
    name: str | None
    email: str
    role: str
    created_at: dt.datetime
    expires_at: dt.datetime


class InviteCreated(BaseModel):
    invite: InviteRead
    token: str  # shown once; only its hash is stored


class MemberRead(BaseModel):
    staff_id: UUID
    name: str
    email: str | None
    role: str  # manager, front_desk, housekeeper, or custom
    is_owner: bool
    is_me: bool
    joined_at: dt.datetime | None


class TeamRead(BaseModel):
    members: list[MemberRead]
    invites: list[InviteRead]


class JoinPreview(BaseModel):
    workspace: str
    name: str | None
    email_hint: str
    role: str
    state: Literal["open", "expired", "used", "revoked"]


class JoinResult(BaseModel):
    role: str
