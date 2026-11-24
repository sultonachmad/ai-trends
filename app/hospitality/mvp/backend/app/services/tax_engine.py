"""Service charge and PBJT on one price, in whole rupiah.

"++" prices exclude both, so they are added on top. "Nett" prices include both, so the
parts are worked out backwards and always add up to the price exactly.
"""

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

NETT = "nett"
PLUS_PLUS = "plus_plus"
ZERO = Decimal("0")
ONE = Decimal("1")
HUNDRED = Decimal("100")


@dataclass(frozen=True)
class TaxRates:
    service_pct: Decimal
    pbjt_pct: Decimal
    pbjt_on_service: bool  # PBJT is charged on the price plus the service charge


@dataclass(frozen=True)
class TaxSplit:
    base: Decimal
    service: Decimal
    pbjt: Decimal

    @property
    def total(self) -> Decimal:
        return self.base + self.service + self.pbjt


def _round(value: Decimal) -> Decimal:
    return value.quantize(ONE, rounding=ROUND_HALF_UP)


def _on_top(base: Decimal, rates: TaxRates) -> TaxSplit:
    service = _round(base * rates.service_pct / HUNDRED)
    taxed = base + service if rates.pbjt_on_service else base
    return TaxSplit(base=base, service=service, pbjt=_round(taxed * rates.pbjt_pct / HUNDRED))


def _factor(rates: TaxRates) -> Decimal:
    service = rates.service_pct / HUNDRED
    pbjt = rates.pbjt_pct / HUNDRED
    if rates.pbjt_on_service:
        return (ONE + service) * (ONE + pbjt)
    return ONE + service + pbjt


def _inside(price: Decimal, rates: TaxRates) -> TaxSplit:
    base = _round(price / _factor(rates))
    service = _round(base * rates.service_pct / HUNDRED)
    return TaxSplit(base=base, service=service, pbjt=price - base - service)


def split(amount: Decimal, rates: TaxRates | None, mode: str) -> TaxSplit:
    """The parts of `amount` priced in `mode`; no rates means no tax."""
    if rates is None or (rates.service_pct == ZERO and rates.pbjt_pct == ZERO):
        return TaxSplit(base=amount, service=ZERO, pbjt=ZERO)
    sign = -ONE if amount < ZERO else ONE
    parts = _inside(abs(amount), rates) if mode == NETT else _on_top(abs(amount), rates)
    return TaxSplit(base=sign * parts.base, service=sign * parts.service, pbjt=sign * parts.pbjt)
