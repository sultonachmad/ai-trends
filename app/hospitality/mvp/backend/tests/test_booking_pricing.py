"""Booking prices: adding up nightly prices, and spreading an edited total over them."""

from decimal import Decimal

import pytest

from app.services.booking_pricing import spread_total, suggested_total

D = Decimal


def test_suggested_total_is_nights_times_units() -> None:
    assert suggested_total([D("500000"), D("750000")], units=1) == D("1250000")
    assert suggested_total([D("500000"), D("750000")], units=3) == D("3750000")


def test_spread_keeps_the_shape_of_the_nightly_prices() -> None:
    cells = spread_total(D("2000000"), [D("500000"), D("1500000")])

    assert cells == [D("500000"), D("1500000")]


def test_spread_scales_down_and_always_adds_up_exactly() -> None:
    weights = [D("500000"), D("500000"), D("500000")]

    cells = spread_total(D("1000000"), weights)

    assert sum(cells) == D("1000000")
    assert cells == [D("333334"), D("333333"), D("333333")]
    assert all(cell == cell.to_integral_value() for cell in cells)


@pytest.mark.parametrize(
    ("total", "weights"),
    [
        ("1", ["500000", "750000", "900000"]),
        ("999999", ["1", "1", "1", "1", "1", "1", "1"]),
        ("123456789", ["650000", "950000", "650000", "950000"]),
        ("700000", ["0", "0"]),
        ("5000000", ["750000"] * 365),
    ],
)
def test_spread_is_exact_for_awkward_numbers(total: str, weights: list[str]) -> None:
    cells = spread_total(D(total), [D(w) for w in weights])

    assert len(cells) == len(weights)
    assert sum(cells) == D(total)
    assert all(cell >= 0 and cell == cell.to_integral_value() for cell in cells)


def test_spread_of_nothing_is_nothing() -> None:
    assert spread_total(D("0"), [D("1"), D("2")]) == [D("0"), D("0")]


def test_spread_needs_at_least_one_cell() -> None:
    with pytest.raises(ValueError, match="at least one"):
        spread_total(D("100"), [])
