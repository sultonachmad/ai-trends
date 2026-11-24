"""A property's tax rules: service charge and PBJT, each effective from a date."""

import datetime as dt
import logging
from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID

from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.tenant import Property, TaxRule
from app.schemas.taxes import TaxRegionRead, TaxSettingsRead, TaxSettingsUpdate, UpcomingRates
from app.services import calendar_dates as dates_of
from app.services import tenant_audit
from app.services.tax_engine import NETT, TaxRates
from app.services.tax_regions import REGIONS
from app.tenancy.context import TenantContext

log = logging.getLogger(__name__)

PBJT, SERVICE = "pbjt_hotel", "service_charge"
ZERO = Decimal("0")
MAX_DAYS_AHEAD = 366


class TaxOwnerOnlyError(PermissionError):
    """Taxes change what guests pay and what is owed to Bapenda: the owner decides."""


class TaxDateError(Exception):
    """Rates can start today or within a year, never in the past."""


def _code(kind: str, prop: Property) -> str:
    return f"{'PBJT' if kind == PBJT else 'SVC'}-{prop.code}"


def _covers(rule: TaxRule, day: dt.date) -> bool:
    return rule.effective_from <= day and (rule.effective_to is None or rule.effective_to >= day)


@dataclass(frozen=True)
class RateBook:
    """Every active rule of a property, to answer "what applies on this date"."""

    rules: tuple[TaxRule, ...]

    def _rule(self, kind: str, day: dt.date) -> TaxRule | None:
        found = [r for r in self.rules if r.report_category == kind and _covers(r, day)]
        return max(found, key=lambda rule: rule.effective_from) if found else None

    def rates_on(self, day: dt.date) -> TaxRates | None:
        pbjt, service = self._rule(PBJT, day), self._rule(SERVICE, day)
        if pbjt is None and service is None:
            return None
        return TaxRates(
            service_pct=service.rate_pct if service else ZERO,
            pbjt_pct=pbjt.rate_pct if pbjt else ZERO,
            pbjt_on_service=bool((pbjt.exemptions if pbjt else {}).get("pbjt_on_service", True)),
        )

    def untaxed_on(self, day: dt.date) -> frozenset[str]:
        rule = self._rule(PBJT, day) or self._rule(SERVICE, day)
        return frozenset((rule.exemptions or {}).get("untaxed", [])) if rule else frozenset()

    @property
    def is_set(self) -> bool:
        return bool(self.rules)


async def rate_book(session: AsyncSession, tenant_id: UUID, property_id: UUID) -> RateBook:
    rows = await session.exec(
        select(TaxRule).where(
            col(TaxRule.tenant_id) == tenant_id,
            col(TaxRule.property_id) == property_id,
            col(TaxRule.report_category).in_((PBJT, SERVICE)),
            col(TaxRule.is_active).is_(True),
        )
    )
    return RateBook(rules=tuple(rows.all()))


def _regions() -> list[TaxRegionRead]:
    return [
        TaxRegionRead(
            code=r.code, name=r.name, province=r.province, suggested_pbjt_pct=r.suggested_pbjt_pct
        )
        for r in REGIONS
    ]


async def read_settings(
    session: AsyncSession, context: TenantContext, prop: Property
) -> TaxSettingsRead:
    book = await rate_book(session, context.tenant_id, prop.id)
    today = dates_of.property_today(prop.timezone)
    now = book.rates_on(today)
    current = book._rule(PBJT, today) or book._rule(SERVICE, today)
    later = sorted(r.effective_from for r in book.rules if r.effective_from > today)
    upcoming = None
    if later:
        rates = book.rates_on(later[0])
        upcoming = UpcomingRates(
            effective_from=later[0],
            pbjt_pct=(rates.pbjt_pct if rates else ZERO).quantize(Decimal("0.01")),
            service_pct=(rates.service_pct if rates else ZERO).quantize(Decimal("0.01")),
        )
    shown = now or (book.rates_on(later[0]) if later else None)
    return TaxSettingsRead(
        confirmed=book.is_set,
        can_edit=context.is_owner,
        region_code=prop.region_code,
        pbjt_pct=(shown.pbjt_pct if shown else ZERO).quantize(Decimal("0.01")),
        service_pct=(shown.service_pct if shown else ZERO).quantize(Decimal("0.01")),
        pbjt_on_service=shown.pbjt_on_service if shown else True,
        price_mode=prop.price_display_mode or NETT,
        untaxed_categories=sorted(
            book.untaxed_on(today if now else (later[0] if later else today))
        ),
        effective_from=current.effective_from if current else None,
        upcoming=upcoming,
        regions=_regions(),
    )


async def _save_rule(
    session: AsyncSession,
    context: TenantContext,
    prop: Property,
    kind: str,
    rate: Decimal,
    request: TaxSettingsUpdate,
) -> None:
    code, start = _code(kind, prop), request.effective_from
    rows = (
        await session.exec(
            select(TaxRule).where(
                col(TaxRule.tenant_id) == context.tenant_id, col(TaxRule.code) == code
            )
        )
    ).all()
    same_day = None
    later = [r.effective_from for r in rows if r.is_active and r.effective_from > start]
    for rule in rows:
        if rule.effective_from == start:
            same_day = rule
        elif rule.effective_from < start and (
            rule.effective_to is None or rule.effective_to >= start
        ):
            rule.effective_to = start - dt.timedelta(days=1)  # a scheduled later change stays
        session.add(rule)
    exemptions = {
        "untaxed": sorted(set(request.untaxed_categories)),
        "pbjt_on_service": request.pbjt_on_service,
    }
    rule = same_day or TaxRule(
        tenant_id=context.tenant_id,
        property_id=prop.id,
        code=code,
        effective_from=start,
        calc_kind="percent",
        report_category=kind,
        created_by=str(context.user_id),
    )
    rule.name = "PBJT jasa perhotelan" if kind == PBJT else "Service charge"
    rule.rate_pct = rate
    rule.compound_order = 2 if kind == PBJT else 1
    rule.region_code = request.region_code
    rule.effective_to = min(later) - dt.timedelta(days=1) if later else None
    rule.exemptions = exemptions
    rule.is_active = True
    session.add(rule)


async def _refresh_open_bookings(
    session: AsyncSession, context: TenantContext, property_id: UUID, start: dt.date
) -> None:
    """Bookings with nights from `start` on owe by the new rules from now."""
    from app.models.tenant import Reservation
    from app.services.bill_balance import refresh_balance
    from app.services.stay_status import CONFIRMED, IN_HOUSE, TENTATIVE

    await session.flush()
    rows = await session.exec(
        select(Reservation)
        .where(
            col(Reservation.tenant_id) == context.tenant_id,
            col(Reservation.property_id) == property_id,
            col(Reservation.status).in_((TENTATIVE, CONFIRMED, IN_HOUSE)),
            col(Reservation.departure_date) > start,
        )
        .with_for_update()
    )
    for booking in rows.all():
        await refresh_balance(session, context.tenant_id, booking)


async def save_settings(
    session: AsyncSession, context: TenantContext, prop: Property, request: TaxSettingsUpdate
) -> TaxSettingsRead:
    """Save rates from a date, the region and the price mode for new bookings. Commits."""
    if not context.is_owner:
        raise TaxOwnerOnlyError
    today = dates_of.property_today(prop.timezone)
    if not today <= request.effective_from <= today + dt.timedelta(days=MAX_DAYS_AHEAD):
        raise TaxDateError
    before = await read_settings(session, context, prop)
    await _save_rule(session, context, prop, PBJT, request.pbjt_pct, request)
    await _save_rule(session, context, prop, SERVICE, request.service_pct, request)
    prop.region_code = request.region_code
    prop.price_display_mode = request.price_mode
    session.add(prop)
    await tenant_audit.record(
        session,
        context,
        "taxes.updated",
        property_id=prop.id,
        entity_table="property",
        entity_id=prop.id,
        payload={
            "region": request.region_code,
            "pbjt_pct": str(request.pbjt_pct),
            "service_pct": str(request.service_pct),
            "pbjt_on_service": request.pbjt_on_service,
            "price_mode": request.price_mode,
            "effective_from": request.effective_from.isoformat(),
            "untaxed_categories": sorted(set(request.untaxed_categories)),
            "before": {
                "confirmed": before.confirmed,
                "region": before.region_code,
                "pbjt_pct": str(before.pbjt_pct),
                "service_pct": str(before.service_pct),
                "price_mode": before.price_mode,
                "untaxed_categories": before.untaxed_categories,
            },
        },
    )
    await _refresh_open_bookings(session, context, prop.id, request.effective_from)
    await session.commit()
    await session.refresh(prop)
    log.info("Tax settings saved property=%s from=%s", prop.id, request.effective_from)
    return await read_settings(session, context, prop)


def priced(
    book: RateBook, mode: str, nights: list[tuple[dt.date, Decimal]]
) -> tuple[Decimal, Decimal]:
    """(what the guest pays, the service charge and PBJT inside it) for these nights."""
    from app.services.tax_engine import split

    parts = [split(amount, book.rates_on(day), mode) for day, amount in nights]
    return (
        sum((part.total for part in parts), ZERO),
        sum((part.service + part.pbjt for part in parts), ZERO),
    )
