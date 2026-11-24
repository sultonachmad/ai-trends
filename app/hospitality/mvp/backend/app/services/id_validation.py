"""Checks on KTP and passport fields, before staff may confirm them.

Pure functions, no database. Each problem has a stable `code` the page translates and
the `field` it belongs to, so the form can mark it.

NIK layout (16 digits): province (2), regency (2), district (2), birth day (2, plus 40
for women), birth month (2), birth year (2), serial (4). Province codes follow the
current Kemendagri list; nationality is checked as two letters only, not against an
official country list.
"""

import datetime as dt
import re
from dataclasses import dataclass

from app.security.identity_crypto import normalise_number

KTP = "ktp"
PASSPORT = "passport"
DOC_TYPES = (KTP, PASSPORT)
INDONESIA = "ID"
VISA_TYPES = ("visa_free", "voa", "b211a", "kitas", "kitap", "other")
GENDERS = ("male", "female")

NIK_LENGTH = 16
_WOMAN_DAY_OFFSET = 40
_PROVINCES = frozenset(
    [*range(11, 20), 21, *range(31, 37), *range(51, 54), *range(61, 66), *range(71, 77)]
    + [81, 82, *range(91, 97)]
)
_KTP_CHARS = re.compile(r"^[0-9 .\-]+$")
_PASSPORT_CHARS = re.compile(r"^[A-Za-z0-9 \-]+$")
_PASSPORT_LENGTH = (6, 12)
_COUNTRY = re.compile(r"^[A-Z]{2}$")
_LEAP_YEAR = 2000  # any leap year, so 29 February in a NIK is a real date


@dataclass(frozen=True)
class IdFields:
    """What staff confirm for one document."""

    doc_type: str
    number: str
    full_name: str
    birth_date: dt.date | None
    gender: str | None
    nationality: str | None
    expires_on: dt.date | None = None
    visa_type: str | None = None
    entry_date: dt.date | None = None

    @property
    def clean_number(self) -> str:
        return normalise_number(self.number)

    @property
    def is_foreign(self) -> bool:
        return self.doc_type == PASSPORT and self.nationality != INDONESIA


@dataclass(frozen=True)
class Problem:
    code: str
    field: str


@dataclass(frozen=True)
class NikParts:
    province: int
    day: int
    month: int
    year_2: int
    serial: str

    @property
    def is_woman(self) -> bool:
        return self.day > _WOMAN_DAY_OFFSET

    @property
    def birth_day(self) -> int:
        return self.day - _WOMAN_DAY_OFFSET if self.is_woman else self.day


def nik_parts(nik: str) -> NikParts:
    return NikParts(
        province=int(nik[0:2]),
        day=int(nik[6:8]),
        month=int(nik[8:10]),
        year_2=int(nik[10:12]),
        serial=nik[12:16],
    )


def _real_day(day: int, month: int) -> bool:
    try:
        dt.date(_LEAP_YEAR, month, day)
    except ValueError:
        return False
    return True


def _nik_problems(fields: IdFields) -> list[Problem]:
    nik = fields.clean_number
    if not _KTP_CHARS.match(fields.number) or len(nik) != NIK_LENGTH or not nik.isdigit():
        return [Problem("nik_format", "number")]
    parts = nik_parts(nik)
    found = []
    if parts.province not in _PROVINCES:
        found.append(Problem("nik_region", "number"))
    if not _real_day(parts.birth_day, parts.month):
        found.append(Problem("nik_birth_date", "number"))
    elif fields.birth_date and (
        (parts.birth_day, parts.month, parts.year_2)
        != (fields.birth_date.day, fields.birth_date.month, fields.birth_date.year % 100)
    ):
        found.append(Problem("nik_birth_date_mismatch", "birth_date"))
    if parts.serial == "0000":
        found.append(Problem("nik_serial", "number"))
    if fields.gender in GENDERS and (fields.gender == "female") != parts.is_woman:
        found.append(Problem("nik_gender", "gender"))
    if fields.nationality not in (None, INDONESIA):
        found.append(Problem("ktp_not_indonesian", "nationality"))
    return found


def _passport_problems(fields: IdFields, today: dt.date) -> list[Problem]:
    low, high = _PASSPORT_LENGTH
    found = []
    if not _PASSPORT_CHARS.match(fields.number) or not low <= len(fields.clean_number) <= high:
        found.append(Problem("passport_format", "number"))
    if fields.nationality is None:
        return [*found, Problem("nationality_missing", "nationality")]
    if fields.expires_on is None:
        found.append(Problem("expiry_missing", "expires_on"))
    elif fields.expires_on < today:
        found.append(Problem("expired", "expires_on"))
    if fields.is_foreign:
        found.extend(_visa_problems(fields, today))
    return found


def _visa_problems(fields: IdFields, today: dt.date) -> list[Problem]:
    found = []
    if fields.visa_type is None:
        found.append(Problem("visa_missing", "visa_type"))
    elif fields.visa_type not in VISA_TYPES:
        found.append(Problem("visa_type", "visa_type"))
    if fields.entry_date is None:
        found.append(Problem("entry_missing", "entry_date"))
    elif fields.entry_date > today:
        found.append(Problem("entry_future", "entry_date"))
    return found


def _common_problems(fields: IdFields, today: dt.date) -> list[Problem]:
    found = []
    if not fields.full_name.strip():
        found.append(Problem("name_missing", "full_name"))
    if fields.birth_date and fields.birth_date > today:
        found.append(Problem("birth_date_future", "birth_date"))
    if fields.nationality is not None and not _COUNTRY.match(fields.nationality):
        found.append(Problem("nationality", "nationality"))
    return found


def problems(fields: IdFields, today: dt.date) -> list[Problem]:
    """Everything wrong with `fields`; empty when they may be confirmed."""
    if fields.doc_type not in DOC_TYPES:
        return [Problem("doc_type", "doc_type")]
    found = _common_problems(fields, today)
    if fields.doc_type == KTP:
        return found + _nik_problems(fields)
    return found + _passport_problems(fields, today)
