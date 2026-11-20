"""Date rules of the rooms-and-prices calendar.

All calendar dates are the property's local dates: "today" is today where the
property is, not where the server is.
"""

import datetime as dt

from app.tenancy.timezones import property_zone

ONE_DAY = dt.timedelta(days=1)


class CalendarDateError(ValueError):
    """A date range the calendar cannot accept."""


class RangeReversedError(CalendarDateError):
    """The end date is before the start date."""


class PastDateError(CalendarDateError):
    """The range starts before today; the past cannot be changed."""


class BeyondHorizonError(CalendarDateError):
    """The range ends after the last date the calendar can be changed for."""

    def __init__(self, last_date: dt.date) -> None:
        super().__init__(f"dates after {last_date.isoformat()} cannot be changed yet")
        self.last_date = last_date


class RangeTooLongError(CalendarDateError):
    """The range covers more days than one request may."""

    def __init__(self, max_days: int) -> None:
        super().__init__(f"a range may cover at most {max_days} days")
        self.max_days = max_days


def property_today(timezone_name: str, now: dt.datetime | None = None) -> dt.date:
    """Today's date at the property."""
    moment = now or dt.datetime.now(dt.UTC)
    return moment.astimezone(property_zone(timezone_name)).date()


def last_editable_date(today: dt.date, horizon_days: int) -> dt.date:
    """The last date that can be changed: `horizon_days` days counting today."""
    return today + dt.timedelta(days=horizon_days - 1)


def day_count(start: dt.date, end: dt.date) -> int:
    """Days in the inclusive range."""
    return (end - start).days + 1


def expand_dates(start: dt.date, end: dt.date, weekdays: frozenset[int] | None) -> list[dt.date]:
    """Every date from `start` to `end` inclusive, kept to `weekdays` (0 = Monday) if given."""
    dates = [start + dt.timedelta(days=offset) for offset in range(day_count(start, end))]
    if weekdays is None:
        return dates
    return [date for date in dates if date.weekday() in weekdays]


def _check_order_and_length(start: dt.date, end: dt.date, max_days: int) -> None:
    if end < start:
        raise RangeReversedError("the end date is before the start date")
    if day_count(start, end) > max_days:
        raise RangeTooLongError(max_days)


def check_change_window(
    start: dt.date, end: dt.date, *, today: dt.date, horizon_days: int, max_days: int
) -> None:
    """Refuse a change that is reversed, in the past, beyond the horizon or too long."""
    if end < start:
        raise RangeReversedError("the end date is before the start date")
    if start < today:
        raise PastDateError("past dates cannot be changed")
    last_date = last_editable_date(today, horizon_days)
    if end > last_date:
        raise BeyondHorizonError(last_date)
    _check_order_and_length(start, end, max_days)


def check_read_window(start: dt.date, end: dt.date, *, max_days: int) -> None:
    """Refuse a read that is reversed or wider than one request may be."""
    _check_order_and_length(start, end, max_days)
