"""Reading other sites' calendars and writing ours."""

import datetime as dt

import pytest

from app.channels.ical_format import (
    EXPORT_TITLE,
    EXPORT_UID_SUFFIX,
    MAX_EVENTS,
    IcalFormatError,
    Window,
    build_calendar,
    busy_dates,
)

WINDOW = Window(dt.date(2027, 1, 1), dt.date(2027, 3, 1))
JAKARTA = "Asia/Jakarta"


def d(day: int, month: int = 1) -> dt.date:
    return dt.date(2027, month, day)


def calendar(*events: str) -> bytes:
    body = "".join(f"BEGIN:VEVENT\r\nUID:{i}@x\r\n{e}END:VEVENT\r\n" for i, e in enumerate(events))
    return f"BEGIN:VCALENDAR\r\nVERSION:2.0\r\nPRODID:-//t//EN\r\n{body}END:VCALENDAR\r\n".encode()


def test_all_day_event_excludes_checkout_day() -> None:
    raw = calendar("DTSTART;VALUE=DATE:20270110\r\nDTEND;VALUE=DATE:20270113\r\n")
    assert busy_dates(raw, WINDOW, JAKARTA) == {d(10), d(11), d(12)}


def test_missing_end_is_one_day() -> None:
    assert busy_dates(calendar("DTSTART;VALUE=DATE:20270110\r\n"), WINDOW, JAKARTA) == {d(10)}


def test_timed_event_uses_the_property_timezone() -> None:
    # 18:00 UTC on the 9th is 01:00 on the 10th in Jakarta
    raw = calendar("DTSTART:20270109T180000Z\r\nDTEND:20270111T040000Z\r\n")
    assert busy_dates(raw, WINDOW, JAKARTA) == {d(10)}


def test_event_within_one_day_blocks_it() -> None:
    raw = calendar("DTSTART:20270110T090000\r\nDTEND:20270110T110000\r\n")
    assert busy_dates(raw, WINDOW, JAKARTA) == {d(10)}


def test_duration_is_honoured() -> None:
    raw = calendar("DTSTART;VALUE=DATE:20270110\r\nDURATION:P2D\r\n")
    assert busy_dates(raw, WINDOW, JAKARTA) == {d(10), d(11)}


def test_folded_lines_are_read() -> None:
    raw = calendar("SUMMARY:A long\r\n  title\r\nDTSTART;VALUE=DATE:20270110\r\n")
    assert busy_dates(raw, WINDOW, JAKARTA) == {d(10)}


@pytest.mark.parametrize("extra", ["STATUS:CANCELLED\r\n", "TRANSP:TRANSPARENT\r\n"])
def test_events_that_are_not_busy_are_ignored(extra: str) -> None:
    assert busy_dates(calendar(f"DTSTART;VALUE=DATE:20270110\r\n{extra}"), WINDOW, JAKARTA) == set()


def test_our_own_exported_dates_are_not_imported_back() -> None:
    now = dt.datetime(2027, 1, 1, tzinfo=dt.UTC)
    assert busy_dates(build_calendar([d(10)], uid_seed="s", now=now), WINDOW, JAKARTA) == set()


def test_dates_are_clipped_to_the_window() -> None:
    raw = calendar("DTSTART;VALUE=DATE:20261230\r\nDTEND;VALUE=DATE:20270102\r\n")
    assert busy_dates(raw, WINDOW, JAKARTA) == {d(1)}


def test_weekly_repeat_with_count_and_exception() -> None:
    raw = calendar(
        "DTSTART;VALUE=DATE:20270104\r\nRRULE:FREQ=WEEKLY;COUNT=3\r\nEXDATE;VALUE=DATE:20270111\r\n"
    )
    assert busy_dates(raw, WINDOW, JAKARTA) == {d(4), d(18)}


def test_daily_repeat_stops_at_until() -> None:
    raw = calendar("DTSTART;VALUE=DATE:20270104\r\nRRULE:FREQ=DAILY;UNTIL=20270106\r\n")
    assert busy_dates(raw, WINDOW, JAKARTA) == {d(4), d(5), d(6)}


def test_endless_repeat_is_bounded_by_the_window() -> None:
    raw = calendar("DTSTART;VALUE=DATE:20270225\r\nRRULE:FREQ=DAILY\r\n")
    assert max(busy_dates(raw, WINDOW, JAKARTA)) == d(28, 2)


@pytest.mark.parametrize(
    "raw",
    [
        b"<html>not found</html>",
        b"",
        calendar("SUMMARY:no start\r\n"),
        calendar("DTSTART;VALUE=DATE:20270104\r\nRRULE:FREQ=MONTHLY\r\n"),
    ],
)
def test_unreadable_calendars_are_refused(raw: bytes) -> None:
    with pytest.raises(IcalFormatError):
        busy_dates(raw, WINDOW, JAKARTA)


def test_too_many_events_are_refused() -> None:
    raw = calendar(*["DTSTART;VALUE=DATE:20270110\r\n"] * (MAX_EVENTS + 1))
    with pytest.raises(IcalFormatError):
        busy_dates(raw, WINDOW, JAKARTA)


def test_export_merges_ranges_and_holds_nothing_private() -> None:
    now = dt.datetime(2027, 1, 1, tzinfo=dt.UTC)
    raw = build_calendar([d(10), d(11), d(14)], uid_seed="secret-seed", now=now)
    text = raw.decode()
    assert text.count("BEGIN:VEVENT") == 2
    assert "DTSTART;VALUE=DATE:20270110" in text and "DTEND;VALUE=DATE:20270112" in text
    assert EXPORT_TITLE in text and EXPORT_UID_SUFFIX in text
    assert "secret-seed" not in text


def test_export_uids_are_stable() -> None:
    first = build_calendar([d(10)], uid_seed="s", now=dt.datetime(2027, 1, 1, tzinfo=dt.UTC))
    second = build_calendar([d(10)], uid_seed="s", now=dt.datetime(2027, 1, 2, tzinfo=dt.UTC))
    uid = next(line for line in first.decode().splitlines() if line.startswith("UID"))
    assert uid in second.decode()


def test_a_calendar_that_expands_too_far_is_refused() -> None:
    event = "DTSTART;VALUE=DATE:20270101\r\nDTEND;VALUE=DATE:20270301\r\nRRULE:FREQ=DAILY\r\n"
    with pytest.raises(IcalFormatError):
        busy_dates(calendar(*[event] * 200), WINDOW, JAKARTA)
