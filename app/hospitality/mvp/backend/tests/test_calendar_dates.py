"""Calendar date rules: the property's "today", the editable window, weekday expansion."""

import datetime as dt

import pytest

from app.services.calendar_dates import (
    BeyondHorizonError,
    PastDateError,
    RangeReversedError,
    RangeTooLongError,
    check_change_window,
    check_read_window,
    expand_dates,
    last_editable_date,
    property_today,
)

D = dt.date


def test_today_follows_the_property_timezone() -> None:
    late_utc = dt.datetime(2026, 11, 30, 17, 30, tzinfo=dt.UTC)  # 01:30 on 1 Dec in Bali

    assert property_today("Asia/Makassar", late_utc) == D(2026, 12, 1)
    assert property_today("UTC", late_utc) == D(2026, 11, 30)


def test_unknown_timezone_falls_back_to_utc() -> None:
    now = dt.datetime(2026, 6, 1, 23, 0, tzinfo=dt.UTC)

    assert property_today("Not/AZone", now) == D(2026, 6, 1)


def test_last_editable_date_is_the_horizon_from_today() -> None:
    assert last_editable_date(D(2026, 1, 1), 365) == D(2026, 12, 31)
    assert last_editable_date(D(2026, 1, 1), 1) == D(2026, 1, 1)


def test_expand_every_day_inclusive() -> None:
    assert expand_dates(D(2026, 2, 27), D(2026, 3, 1), None) == [
        D(2026, 2, 27),
        D(2026, 2, 28),
        D(2026, 3, 1),
    ]


def test_expand_chosen_weekdays_only() -> None:
    # 2026-11-20 is a Friday (weekday 4); keep Fridays and Saturdays.
    dates = expand_dates(D(2026, 11, 20), D(2026, 11, 30), frozenset({4, 5}))

    assert dates == [D(2026, 11, 20), D(2026, 11, 21), D(2026, 11, 27), D(2026, 11, 28)]


def test_expand_can_come_back_empty() -> None:
    assert expand_dates(D(2026, 11, 23), D(2026, 11, 24), frozenset({6})) == []


def test_single_day_range() -> None:
    assert expand_dates(D(2026, 5, 5), D(2026, 5, 5), None) == [D(2026, 5, 5)]


TODAY = D(2026, 11, 20)


def test_a_change_within_the_window_is_accepted() -> None:
    check_change_window(TODAY, D(2027, 11, 19), today=TODAY, horizon_days=365, max_days=365)


@pytest.mark.parametrize(
    ("start", "end", "error"),
    [
        (D(2026, 11, 22), D(2026, 11, 21), RangeReversedError),
        (D(2026, 11, 19), D(2026, 11, 21), PastDateError),
        (D(2026, 11, 21), D(2027, 11, 20), BeyondHorizonError),
    ],
)
def test_bad_change_windows_are_refused(start: D, end: D, error: type[Exception]) -> None:
    with pytest.raises(error):
        check_change_window(start, end, today=TODAY, horizon_days=365, max_days=365)


def test_a_change_longer_than_the_limit_is_refused() -> None:
    with pytest.raises(RangeTooLongError) as caught:
        check_change_window(
            TODAY, TODAY + dt.timedelta(days=31), today=TODAY, horizon_days=365, max_days=31
        )

    assert caught.value.max_days == 31


def test_reading_may_include_the_past_but_not_an_endless_window() -> None:
    check_read_window(D(2026, 1, 1), D(2026, 1, 31), max_days=31)
    with pytest.raises(RangeReversedError):
        check_read_window(D(2026, 1, 2), D(2026, 1, 1), max_days=31)
    with pytest.raises(RangeTooLongError):
        check_read_window(D(2026, 1, 1), D(2026, 2, 1), max_days=31)
