"""Requests and answers for calendar links (iCal)."""

import datetime as dt
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

Label = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)]
ImportUrl = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2048)]


class CalendarLinkCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    room_type_id: UUID
    label: Label
    import_url: ImportUrl | None = None


class CalendarLinkUpdateRequest(BaseModel):
    """Omitted fields stay as they are; `import_url: null` stops importing."""

    model_config = ConfigDict(extra="forbid")

    label: Label | None = None
    import_url: ImportUrl | None = None


class CalendarImportStatus(BaseModel):
    url_hint: str  # host only: the full URL is a secret
    last_synced_at: dt.datetime | None
    last_error: str | None  # a short code, translated by the page
    failing_since: dt.datetime | None
    at_risk: bool
    busy_dates: int


class CalendarLinkRead(BaseModel):
    id: UUID
    label: str
    room_type_id: UUID
    room_type_name: str
    imports: CalendarImportStatus | None
    conflict_dates: list[dt.date]  # busy on the site while we have nothing left


class CalendarLinkCreated(CalendarLinkRead):
    """The only answers that carry the private link; it cannot be shown again."""

    export_path: str


class SimulatedCalendarRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    busy: list[dt.date] = Field(default_factory=list, max_length=400)
    broken: bool = False


class SimulatedCalendarRead(BaseModel):
    url: str
