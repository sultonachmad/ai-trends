"""What a guest sees on the public page: availability and all-in prices.

Uses the same stay checks as a staff booking. A rate plan is offered only when every
night passes its rules (BR-BE-03). Exact unit counts are never exposed.
"""

import datetime as dt
from dataclasses import dataclass
from decimal import ROUND_CEILING, Decimal

from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.tenant import Property, RatePlan, UnitType
from app.schemas.booking_page import (
    PublicAvailability,
    PublicCalendar,
    PublicDay,
    PublicPage,
    PublicRateOption,
    PublicRoomChoice,
    PublicRoomResult,
)
from app.services import calendar_dates as dates_of
from app.services import rate_policies as policies
from app.services.booking_stays import CheckedStay, OverCapacityError, Stay, check_dates, check_stay
from app.services.calendar import read_calendar
from app.services.rate_plans import find_base_prices
from app.services.tax_rules import RateBook, rate_book
from app.services.tax_rules import priced as taxed_price
from app.tenancy.business_settings import PropertySettings, resolve_property_settings
from app.tenancy.context import TenantContext

ACTIVE = "active"
MAX_CALENDAR_DAYS = 62
MAX_SEARCH_PAIRS = 40  # a public request never runs an unbounded number of stay checks
ONE_RUPIAH = Decimal("1")


class CalendarRangeError(Exception):
    """The calendar range is reversed or too long."""


@dataclass(frozen=True)
class SellablePair:
    room: UnitType
    plan: RatePlan


def deposit_of(total: Decimal, percent: int) -> Decimal:
    """The deposit in whole rupiah, rounded up and never above the total."""
    share = (total * percent / Decimal(100)).quantize(ONE_RUPIAH, rounding=ROUND_CEILING)
    return min(share, total)


def stay_problem(checked: CheckedStay) -> tuple[str | None, int | None]:
    """Why this stay cannot be sold: (reason, minimum nights), or (None, None)."""
    nights = checked.nights
    if any(night.closed for night in nights):
        return "closed", None
    required = nights[0].min_stay
    if required is not None and len(nights) < required:
        return "min_stay", required
    if any(night.available < checked.stay.units for night in nights):
        return "sold_out", None
    return None, None


async def sellable_pairs(
    session: AsyncSession, context: TenantContext, prop: Property
) -> list[SellablePair]:
    """Active room types with each active plan marked for the booking page."""
    plans = (
        await session.exec(
            select(RatePlan)
            .where(
                col(RatePlan.tenant_id) == context.tenant_id,
                col(RatePlan.property_id) == prop.id,
                col(RatePlan.status) == ACTIVE,
                col(RatePlan.is_public).is_(True),
            )
            .order_by(col(RatePlan.sort_order), col(RatePlan.name))
        )
    ).all()
    rooms = (
        await session.exec(
            select(UnitType)
            .where(
                col(UnitType.tenant_id) == context.tenant_id,
                col(UnitType.property_id) == prop.id,
                col(UnitType.is_active).is_(True),
            )
            .order_by(col(UnitType.name))
        )
    ).all()
    links = await find_base_prices(session, context, [plan.id for plan in plans])
    priced = {(link.rate_plan_id, link.unit_type_id) for link in links}
    return [
        SellablePair(room, plan) for room in rooms for plan in plans if (plan.id, room.id) in priced
    ]


async def read_page(session: AsyncSession, context: TenantContext, prop: Property) -> PublicPage:
    settings = resolve_property_settings(prop.settings)
    today = dates_of.property_today(prop.timezone)
    pairs = await sellable_pairs(session, context, prop)
    rooms = {pair.room.id: pair.room.name for pair in pairs}
    return PublicPage(
        property_name=prop.name,
        city=(prop.address or {}).get("city"),
        check_in_time=prop.check_in_time,
        check_out_time=prop.check_out_time,
        today=today,
        last_arrival=dates_of.last_editable_date(today, settings.calendar_horizon_days),
        max_nights=settings.booking_max_nights,
        deposit_percent=settings.direct_deposit_percent,
        hold_minutes=settings.direct_hold_minutes,
        whatsapp_phone=prop.whatsapp_phone,
        rooms=[PublicRoomChoice(id=room_id, name=name) for room_id, name in rooms.items()],
    )


async def read_public_calendar(
    session: AsyncSession, context: TenantContext, prop: Property, start: dt.date, end: dt.date
) -> PublicCalendar:
    """Per date: can anything be sold, from what price, with what minimum stay."""
    today = dates_of.property_today(prop.timezone)
    start = max(start, today)
    if end < start or (end - start).days >= MAX_CALENDAR_DAYS:
        raise CalendarRangeError
    pairs = await sellable_pairs(session, context, prop)
    sold = {(pair.room.id, pair.plan.id) for pair in pairs}
    calendar = await read_calendar(session, context, prop, start, end)
    book = await rate_book(session, context.tenant_id, prop.id)
    mode = prop.price_display_mode
    best: dict[dt.date, tuple[Decimal, int | None]] = {}
    for room in calendar.room_types:
        for day in room.days:
            if day.closed or day.available < 1:
                continue
            prices = [p.amount for p in day.prices if (room.id, p.rate_plan_id) in sold]
            if not prices:
                continue
            low = taxed_price(book, mode, [(day.date, min(prices))])[0]  # what the guest pays
            current = best.get(day.date)
            if current is None or low < current[0]:
                best[day.date] = (low, day.min_stay)
    days = dates_of.expand_dates(start, end, None)
    return PublicCalendar(
        days=[
            PublicDay(
                date=day,
                available=day in best,
                lowest_price=best[day][0] if day in best else None,
                min_stay=best[day][1] if day in best else None,
            )
            for day in days
        ]
    )


async def _option(
    session: AsyncSession,
    context: TenantContext,
    checked: CheckedStay,
    settings: PropertySettings,
    prop_mode: str,
    book: RateBook,
) -> PublicRateOption:
    """What the guest pays for this plan, service charge and PBJT included."""
    policy_id = checked.plan.cancellation_policy_id
    terms = policies.terms_of(
        (await policies.policies_by_id(session, context, {policy_id}))[policy_id]
    )
    nights = [(night.date, night.amount) for night in checked.nights]
    total, tax = taxed_price(book, prop_mode, nights)
    return PublicRateOption(
        rate_plan_id=checked.plan.id,
        name=checked.plan.name,
        total=total,
        tax=tax,
        deposit=deposit_of(total, settings.direct_deposit_percent),
        non_refundable=terms.non_refundable,
        free_cancellation_days=terms.free_days,
    )


_REASON_ORDER = ("min_stay", "closed", "sold_out", "too_many_guests")


async def search(
    session: AsyncSession,
    context: TenantContext,
    prop: Property,
    arrival: dt.date,
    departure: dt.date,
    adults: int,
    children: int,
) -> PublicAvailability:
    """Room types and plans that can really be booked for this stay."""
    settings = resolve_property_settings(prop.settings)
    today = dates_of.property_today(prop.timezone)
    pairs = (await sellable_pairs(session, context, prop))[:MAX_SEARCH_PAIRS]
    book = await rate_book(session, context.tenant_id, prop.id)
    rooms: dict[object, PublicRoomResult] = {}
    reasons: dict[str, int | None] = {}
    for pair in pairs:
        stay = Stay(arrival, departure, pair.room.id, pair.plan.id, 1, adults, children)
        check_dates(stay, prop, settings)
        if arrival < today:
            raise PastArrivalError
        try:
            checked = await check_stay(session, context, prop, settings, stay)
        except OverCapacityError:
            reasons.setdefault("too_many_guests", None)
            continue
        problem, required = stay_problem(checked)
        if problem:
            reasons.setdefault(problem, required)
            continue
        result = rooms.setdefault(
            pair.room.id,
            PublicRoomResult(
                id=pair.room.id,
                name=pair.room.name,
                max_guests=pair.room.max_occupancy,
                options=[],
            ),
        )
        result.options.append(
            await _option(session, context, checked, settings, prop.price_display_mode, book)
        )
    reason = None
    if not rooms:
        reason = next((r for r in _REASON_ORDER if r in reasons), "sold_out")
    return PublicAvailability(
        nights=(departure - arrival).days,
        rooms=list(rooms.values()),
        unavailable_reason=reason,
        min_stay=reasons.get("min_stay") if reason == "min_stay" else None,
    )


class PastArrivalError(Exception):
    """A guest cannot book a stay starting before today."""
