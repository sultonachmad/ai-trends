"""Reading and writing iCalendar (.ics) files, availability only.

`busy_dates` turns a calendar from another site into the nights it marks as busy,
clipped to the selling window. Anything it cannot read with confidence raises
`IcalFormatError`, so the caller keeps the blocks it has rather than releasing them.

`build_calendar` writes our side: date ranges titled "Not available", with no guest,
price, booking or property details.
"""

import datetime as dt
import hashlib
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from zoneinfo import ZoneInfo

from icalendar import Calendar, Event

MAX_EVENTS = 5000
MAX_OCCURRENCES = 20_000
MAX_EXPANDED_DAYS = 200_000  # total work per calendar, however it is repeated
EXPORT_UID_SUFFIX = "@availability-export"
EXPORT_TITLE = "Not available"
PRODUCT_ID = "-//Availability Calendar//EN"
_SUPPORTED_RULE_PARTS = {"FREQ", "INTERVAL", "COUNT", "UNTIL", "BYDAY"}
_WEEKDAYS = {"MO": 0, "TU": 1, "WE": 2, "TH": 3, "FR": 4, "SA": 5, "SU": 6}
_PARSE_ERRORS = (
    ValueError,
    KeyError,
    TypeError,
    AttributeError,
    IndexError,
    OverflowError,
    RecursionError,
)


class IcalFormatError(Exception):
    """The file is not a calendar we can read with confidence."""


@dataclass(frozen=True)
class Window:
    """The nights that matter: `start` inclusive, `end` exclusive."""

    start: dt.date
    end: dt.date


def _day(value: dt.date | dt.datetime, zone: ZoneInfo) -> dt.date:
    if isinstance(value, dt.datetime):
        return value.astimezone(zone).date() if value.tzinfo else value.date()
    return value


def _length_in_nights(event: Event, first: dt.date, zone: ZoneInfo) -> int:
    """Nights one occurrence covers; an event inside one day still blocks that day."""
    start = event["DTSTART"].dt
    if "DTEND" in event:
        last = _day(event["DTEND"].dt, zone)
    elif "DURATION" in event:
        last = _day(start + event["DURATION"].dt, zone)
    else:
        return 1
    return max((last - first).days, 1)


def _excluded_days(event: Event, zone: ZoneInfo) -> set[dt.date]:
    raw = event.get("EXDATE")
    if raw is None:
        return set()
    groups = raw if isinstance(raw, list) else [raw]
    return {_day(item.dt, zone) for group in groups for item in group.dts}


def _weekly_days(first: dt.date, interval: int, weekdays: list[int]) -> Iterator[dt.date]:
    monday = first - dt.timedelta(days=first.weekday())
    while True:
        for weekday in weekdays:
            day = monday + dt.timedelta(days=weekday)
            if day >= first:
                yield day
        monday += dt.timedelta(weeks=interval)


def _daily_days(first: dt.date, interval: int) -> Iterator[dt.date]:
    day = first
    while True:
        yield day
        day += dt.timedelta(days=interval)


def _rule_days(rule: dict, first: dt.date, zone: ZoneInfo) -> Iterator[dt.date]:
    if set(rule) - _SUPPORTED_RULE_PARTS:
        raise IcalFormatError("unsupported repeat rule")
    frequency = str(rule["FREQ"][0]).upper()
    interval = int(rule.get("INTERVAL", [1])[0])
    if interval < 1:
        raise IcalFormatError("invalid repeat interval")
    if frequency == "DAILY" and "BYDAY" not in rule:
        return _daily_days(first, interval)
    if frequency == "WEEKLY":
        names = [str(name).upper() for name in rule.get("BYDAY", [])]
        if any(name not in _WEEKDAYS for name in names):
            raise IcalFormatError("unsupported repeat day")
        weekdays = sorted({_WEEKDAYS[name] for name in names} or {first.weekday()})
        return _weekly_days(first, interval, weekdays)
    raise IcalFormatError("unsupported repeat rule")


def _occurrences(event: Event, first: dt.date, window: Window, zone: ZoneInfo) -> Iterator[dt.date]:
    """Start days of an event, stopping at the end of the window."""
    rule = event.get("RRULE")
    if rule is None:
        yield first
        return
    count = int(rule["COUNT"][0]) if "COUNT" in rule else None
    until = _day(rule["UNTIL"][0], zone) if "UNTIL" in rule else None
    excluded = _excluded_days(event, zone)
    for index, day in enumerate(_rule_days(rule, first, zone)):
        if index >= MAX_OCCURRENCES:
            raise IcalFormatError("too many repeats")
        if day >= window.end or (count is not None and index >= count):
            return
        if until is not None and day > until:
            return
        if day not in excluded:
            yield day


def _counts_as_busy(event: Event) -> bool:
    if str(event.get("STATUS", "")).upper() == "CANCELLED":
        return False
    if str(event.get("TRANSP", "")).upper() == "TRANSPARENT":
        return False
    return not str(event.get("UID", "")).endswith(EXPORT_UID_SUFFIX)  # our own dates, echoed


def _event_nights(
    event: Event, window: Window, zone: ZoneInfo, budget: int
) -> tuple[set[dt.date], int]:
    """The event's nights in the window, and how much of `budget` is left."""
    first = _day(event["DTSTART"].dt, zone)
    nights = _length_in_nights(event, first, zone)
    found: set[dt.date] = set()
    for start in _occurrences(event, first, window, zone):
        begin = max(start, window.start)
        end = min(start + dt.timedelta(days=nights), window.end)
        span = max((end - begin).days, 0)
        budget -= span + 1  # an occurrence outside the window still costs a step
        if budget < 0:
            raise IcalFormatError("calendar expands too far")
        found.update(begin + dt.timedelta(days=n) for n in range(span))
    return found, budget


def busy_dates(raw: bytes, window: Window, timezone_name: str) -> set[dt.date]:
    """The nights in `window` this calendar marks as busy."""
    if b"BEGIN:VCALENDAR" not in raw[:4096].upper():
        raise IcalFormatError("not a calendar")
    zone = ZoneInfo(timezone_name)
    try:
        events = Calendar.from_ical(raw).walk("VEVENT")
        if len(events) > MAX_EVENTS:
            raise IcalFormatError("too many events")
        busy: set[dt.date] = set()
        budget = MAX_EXPANDED_DAYS
        for event in events:
            if _counts_as_busy(event):
                nights, budget = _event_nights(event, window, zone, budget)
                busy |= nights
        return busy
    except _PARSE_ERRORS as exc:
        raise IcalFormatError("unreadable calendar") from exc


def _ranges(days: Iterable[dt.date]) -> list[tuple[dt.date, dt.date]]:
    """Consecutive days as (first, day after last)."""
    ranges: list[tuple[dt.date, dt.date]] = []
    for day in sorted(set(days)):
        if ranges and ranges[-1][1] == day:
            ranges[-1] = (ranges[-1][0], day + dt.timedelta(days=1))
        else:
            ranges.append((day, day + dt.timedelta(days=1)))
    return ranges


def build_calendar(days: Iterable[dt.date], *, uid_seed: str, now: dt.datetime) -> bytes:
    """An .ics of busy date ranges. `uid_seed` keeps event ids stable and unguessable."""
    calendar = Calendar()
    calendar.add("prodid", PRODUCT_ID)
    calendar.add("version", "2.0")
    for first, end in _ranges(days):
        event = Event()
        digest = hashlib.sha256(f"{uid_seed}:{first.isoformat()}".encode()).hexdigest()[:32]
        event.add("uid", f"{digest}{EXPORT_UID_SUFFIX}")
        event.add("dtstamp", now)
        event.add("dtstart", first)
        event.add("dtend", end)
        event.add("summary", EXPORT_TITLE)
        calendar.add_component(event)
    return calendar.to_ical()
