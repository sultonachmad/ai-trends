"""Shapes for room types and their units."""

from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

# One line of plain text: shown to guests and sent to channels. Control characters,
# invisible characters and text-direction overrides are refused, so a name cannot be
# made to look like another one.
UNSAFE_IN_NAMES = (
    "\x00-\x1f\x7f-\x9f"  # C0 and C1 controls
    "\u200b-\u200f"  # zero-width characters and direction marks
    "\u2028-\u202e"  # line/paragraph separators and direction embeddings/overrides
    "\u2060-\u2069"  # word joiner, invisible operators, direction isolates
    "\ufeff"  # byte-order mark
)
RoomName = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True, min_length=1, max_length=80, pattern=f"^[^{UNSAFE_IN_NAMES}]+$"
    ),
]
RoomKind = Literal["room", "villa", "apartment", "cabin", "other"]
MAX_GUESTS_CEILING = 50
UNITS_CEILING = 1000  # the property's own limit is a setting, checked in the service


class RoomTypeCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: RoomName
    kind: RoomKind = "room"
    units: int = Field(ge=1, le=UNITS_CEILING, description="How many of this room there are.")
    max_guests: int = Field(ge=1, le=MAX_GUESTS_CEILING)


class RoomTypeUpdateRequest(BaseModel):
    """Only the fields sent are changed."""

    model_config = ConfigDict(extra="forbid")

    name: RoomName | None = None
    kind: RoomKind | None = None
    units: int | None = Field(default=None, ge=1, le=UNITS_CEILING)
    max_guests: int | None = Field(default=None, ge=1, le=MAX_GUESTS_CEILING)
    is_active: bool | None = None


class UnitRenameRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: RoomName


class UnitRead(BaseModel):
    id: UUID
    name: str


class RoomTypeRead(BaseModel):
    id: UUID
    name: str
    kind: str
    max_guests: int
    is_active: bool
    units: list[UnitRead]  # the units in use, in order
