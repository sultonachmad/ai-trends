"""Booking prices in whole rupiah.

A booking has one price per unit per night. The suggested price is the calendar's
nightly prices added up. When staff type a different total, it is spread over the same
cells in proportion to the calendar prices, so the cells always add up to the total.
"""

from decimal import ROUND_DOWN, Decimal

ZERO = Decimal("0")
ONE = Decimal("1")


def suggested_total(nightly: list[Decimal], *, units: int) -> Decimal:
    """The calendar price of the stay: every night, for every unit."""
    return sum(nightly, ZERO) * units


def spread_total(total: Decimal, weights: list[Decimal]) -> list[Decimal]:
    """Split `total` into whole-rupiah cells proportional to `weights`, summing exactly.

    Leftover rupiah (from rounding down) go one each to the earliest cells. Equal weights
    are used when every weight is zero.
    """
    if not weights:
        raise ValueError("a total needs at least one cell to be spread over")
    basis = weights if any(weight > ZERO for weight in weights) else [ONE] * len(weights)
    whole = sum(basis, ZERO)
    cells = [(total * weight / whole).quantize(ONE, rounding=ROUND_DOWN) for weight in basis]
    leftover = int(total - sum(cells, ZERO))
    return [cell + ONE if index < leftover else cell for index, cell in enumerate(cells)]
