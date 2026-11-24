"""Splitting a price into its base, service charge and PBJT."""

from decimal import Decimal

import pytest

from app.services.tax_engine import NETT, PLUS_PLUS, TaxRates, split

D = Decimal
TEN_TEN = TaxRates(service_pct=D("10"), pbjt_pct=D("10"), pbjt_on_service=True)


def test_plus_plus_adds_service_then_tax_on_both() -> None:
    parts = split(D("500000"), TEN_TEN, PLUS_PLUS)

    assert (parts.base, parts.service, parts.pbjt, parts.total) == (
        D("500000"),
        D("50000"),
        D("55000"),
        D("605000"),
    )


def test_tax_can_leave_the_service_charge_out() -> None:
    rates = TaxRates(service_pct=D("10"), pbjt_pct=D("10"), pbjt_on_service=False)

    assert split(D("500000"), rates, PLUS_PLUS).pbjt == D("50000")


def test_nett_works_backwards_and_adds_up_exactly() -> None:
    parts = split(D("605000"), TEN_TEN, NETT)

    assert (parts.base, parts.service, parts.pbjt, parts.total) == (
        D("500000"),
        D("50000"),
        D("55000"),
        D("605000"),
    )


@pytest.mark.parametrize("amount", ["1", "99", "333333", "1000001", "987654321"])
@pytest.mark.parametrize("mode", [NETT, PLUS_PLUS])
def test_parts_always_add_up(amount: str, mode: str) -> None:
    parts = split(D(amount), TEN_TEN, mode)

    assert parts.base + parts.service + parts.pbjt == parts.total
    if mode == NETT:
        assert parts.total == D(amount)


def test_rounding_is_half_up_to_whole_rupiah() -> None:
    rates = TaxRates(service_pct=D("0"), pbjt_pct=D("10"), pbjt_on_service=True)

    assert split(D("15"), rates, PLUS_PLUS).pbjt == D("2")
    assert split(D("14"), rates, PLUS_PLUS).pbjt == D("1")


def test_no_rates_means_no_tax() -> None:
    parts = split(D("500000"), None, PLUS_PLUS)

    assert (parts.service, parts.pbjt, parts.total) == (D("0"), D("0"), D("500000"))


def test_negative_lines_reduce_the_tax() -> None:
    parts = split(D("-100000"), TEN_TEN, PLUS_PLUS)

    assert (parts.service, parts.pbjt, parts.total) == (D("-10000"), D("-11000"), D("-121000"))
