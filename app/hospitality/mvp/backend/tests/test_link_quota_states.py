"""Quota states shown to staff: fine, close to the limit, limit reached, unlimited."""

import datetime as dt

import pytest

from app.services.link_quota import LinkQuota, month_start_utc

RESET = dt.datetime(2026, 12, 1, tzinfo=dt.UTC)


def _quota(used: int, limit: int | None, percent: int = 80) -> LinkQuota:
    return LinkQuota(
        used=used, limit=limit, warning_percent=percent, resets_at=RESET, resets_on=RESET.date()
    )


@pytest.mark.parametrize(
    ("used", "limit", "warning", "reached"),
    [
        (0, 30, False, False),
        (23, 30, False, False),
        (24, 30, True, False),
        (29, 30, True, False),
        (30, 30, False, True),
        (31, 30, False, True),  # the limit was lowered after links were made
        (0, 0, False, True),
        (500, None, False, False),
    ],
)
def test_states(used: int, limit: int | None, warning: bool, reached: bool) -> None:
    quota = _quota(used, limit)

    assert (quota.warning, quota.limit_reached) == (warning, reached)


def test_warning_at_one_hundred_percent_never_shows() -> None:
    assert not _quota(29, 30, percent=100).warning


def test_month_start_uses_the_property_timezone() -> None:
    now = dt.datetime(2026, 11, 30, 23, 30, tzinfo=dt.UTC)  # already 1 Dec in Bali

    assert month_start_utc(now, "Asia/Makassar") == dt.datetime(2026, 11, 30, 16, tzinfo=dt.UTC)
    assert month_start_utc(now, "UTC") == dt.datetime(2026, 11, 1, tzinfo=dt.UTC)
