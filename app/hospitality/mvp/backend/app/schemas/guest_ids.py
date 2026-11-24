"""Guests on a booking and their ID documents. Numbers leave the server masked only."""

import datetime as dt
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, StringConstraints

DocType = Literal["ktp", "passport"]
Gender = Literal["male", "female"]
VisaType = Literal["visa_free", "voa", "b211a", "kitas", "kitap", "other"]

IdNumber = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=40, pattern=r"^[^<>]*$")
]
PersonName = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True, min_length=1, max_length=120, pattern=r"^[^<>\x00-\x1f]*$"
    ),
]
Country = Annotated[str, StringConstraints(strip_whitespace=True, to_upper=True, max_length=3)]


class IdDocumentRead(BaseModel):
    id: UUID
    doc_type: str
    masked_number: str | None  # None once the number was cleared after retention
    issuing_country: str | None
    expires_on: dt.date | None
    visa_type: str | None
    entry_date: dt.date | None
    confirmed_at: dt.datetime | None
    confirmed_by: str | None
    has_image: bool
    usable: bool  # confirmed, number kept and not expired


class GuestOnBooking(BaseModel):
    guest_id: UUID
    full_name: str
    is_main: bool
    nationality: str | None
    birth_date: dt.date | None
    gender: str | None
    document: IdDocumentRead | None


class ReaderInfo(BaseModel):
    name: str
    simulated: bool


class BookingGuests(BaseModel):
    booking_id: UUID
    status: str
    main_guest_ready: bool
    can_change: bool  # the stay is not finished or cancelled
    reader: ReaderInfo
    guests: list[GuestOnBooking]


class ReadFieldsOut(BaseModel):
    number: str | None
    full_name: str | None
    birth_date: dt.date | None
    gender: str | None
    nationality: str | None
    expires_on: dt.date | None
    visa_type: str | None
    entry_date: dt.date | None


class ScanResult(BaseModel):
    scan_id: UUID
    reader: ReaderInfo
    fields: ReadFieldsOut


class ConfirmIdRequest(BaseModel):
    """Fields staff checked against the document. `checked` must be true."""

    model_config = ConfigDict(extra="forbid")

    guest_id: UUID | None = None  # None = a new guest on this booking
    doc_type: DocType
    number: IdNumber
    full_name: PersonName
    birth_date: dt.date | None = None
    gender: Gender | None = None
    nationality: Country | None = None
    expires_on: dt.date | None = None
    visa_type: VisaType | None = None
    entry_date: dt.date | None = None
    scan_id: UUID | None = None
    checked: Literal[True]


class RevealedNumber(BaseModel):
    number: str


class IdView(BaseModel):
    """One entry of the ID history: who confirmed or looked at what, and when."""

    event: str
    at: dt.datetime
    by: str
    guest_id: UUID | None
    document_id: UUID | None
