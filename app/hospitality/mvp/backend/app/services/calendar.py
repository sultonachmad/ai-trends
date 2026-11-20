"""The rooms-and-prices calendar: the property's single source of truth.

Two entry points, on purpose:

* `read_calendar` answers "what is sellable, at what price, on these dates".
* `apply_calendar_change` is the only way prices, closed dates and minimum stays change.

Everything that shows or sends availability and prices (the calendar screen, channel
updates, the booking page) goes through these, so they cannot disagree.

Storage is sparse. A price is stored for a date only when it differs from the rate
plan's base price (`ratedaily`); a date has a `restriction` row only while it is closed
or has a minimum stay. Changes to one property are serialised by locking its row.
"""

import datetime as dt
import logging
import uuid
from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID

from sqlalchemy import ColumnElement, delete, insert, update
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.tenant import Property, RateDaily, RatePlan, Restriction, UnitType
from app.schemas.calendar import (
    MAX_READ_DAYS,
    CalendarChangeRequest,
    CalendarDay,
    CalendarRatePlan,
    CalendarRead,
    CalendarRoomType,
    ClearMinStay,
    ClearPrice,
    Close,
    DayPrice,
    Open,
    SetMinStay,
    SetPrice,
)
from app.services import calendar_dates as dates_of
from app.services.inventory import sold_by_night, units_in_use
from app.services.rate_plans import ACTIVE, check_rate, find_base_prices, find_rate_plans
from app.services.room_types import find_room_types
from app.tenancy.business_settings import resolve_property_settings
from app.tenancy.context import TenantContext

log = logging.getLogger(__name__)

NO_MIN_STAY = 1
# Most date × room-type cells one change may touch, whatever the property's own limits.
MAX_CELLS_PER_CHANGE = 20_000


class ChangeTooLargeError(Exception):
    """The change covers more date × room-type cells than one request may."""


class NothingToChangeError(Exception):
    """The chosen weekdays match no date in the range."""


class UnknownRoomTypeError(Exception):
    """A chosen room type is not an active room type of this property."""


class UnknownRatePlanError(Exception):
    """The rate plan is not an active rate plan of this property."""


class PlanDoesNotSellRoomError(Exception):
    """The rate plan does not sell every chosen room type."""


@dataclass(frozen=True)
class AppliedChange:
    """What a change touched; later milestones send exactly this to channels."""

    dates: list[dt.date]
    room_type_ids: list[UUID]


# ---- reading ----------------------------------------------------------------------------


async def _price_overrides(
    session: AsyncSession,
    context: TenantContext,
    plan_ids: list[UUID],
    start: dt.date,
    end: dt.date,
) -> dict[tuple[UUID, UUID, dt.date], Decimal]:
    if not plan_ids:
        return {}
    rows = await session.exec(
        select(
            col(RateDaily.rate_plan_id),
            col(RateDaily.unit_type_id),
            col(RateDaily.stay_date),
            col(RateDaily.amount),
        ).where(
            col(RateDaily.tenant_id) == context.tenant_id,
            col(RateDaily.rate_plan_id).in_(plan_ids),
            col(RateDaily.stay_date) >= start,
            col(RateDaily.stay_date) <= end,
        )
    )
    return {(plan_id, room_id, day): amount for plan_id, room_id, day, amount in rows.all()}


def _room_rules(
    context: TenantContext, property_id: UUID, room_type_ids: list[UUID]
) -> tuple[ColumnElement[bool], ...]:
    """Filter for the rule rows this calendar owns: per room type, all plans, all channels."""
    return (
        col(Restriction.tenant_id) == context.tenant_id,
        col(Restriction.property_id) == property_id,
        col(Restriction.unit_type_id).in_(room_type_ids),
        col(Restriction.rate_plan_id).is_(None),
        col(Restriction.channel_id).is_(None),
    )


async def _rules(
    session: AsyncSession,
    context: TenantContext,
    property_id: UUID,
    room_type_ids: list[UUID],
    start: dt.date,
    end: dt.date,
) -> dict[tuple[UUID, dt.date], tuple[bool, int | None]]:
    """(closed, minimum stay) for the dates that have a rule."""
    if not room_type_ids:
        return {}
    rows = await session.exec(
        select(
            col(Restriction.unit_type_id),
            col(Restriction.stay_date),
            col(Restriction.stop_sell),
            col(Restriction.min_stay_arrival),
        ).where(
            *_room_rules(context, property_id, room_type_ids),
            col(Restriction.stay_date) >= start,
            col(Restriction.stay_date) <= end,
        )
    )
    return {(room_id, day): (closed, min_stay) for room_id, day, closed, min_stay in rows.all()}


async def read_calendar(
    session: AsyncSession, context: TenantContext, prop: Property, start: dt.date, end: dt.date
) -> CalendarRead:
    """Availability, closed state, minimum stay and prices for the property's active rooms."""
    dates_of.check_read_window(start, end, max_days=MAX_READ_DAYS)
    settings = resolve_property_settings(prop.settings)
    today = dates_of.property_today(prop.timezone)
    rooms = await find_room_types(session, context, prop.id, active_only=True)
    plans = await find_rate_plans(session, context, prop.id, active_only=True)
    room_ids = [room.id for room in rooms]
    plan_ids = [plan.id for plan in plans]
    units = await units_in_use(session, context, room_ids)
    links = await find_base_prices(session, context, plan_ids)
    base = {(link.rate_plan_id, link.unit_type_id): link.base_amount for link in links}
    overrides = await _price_overrides(session, context, plan_ids, start, end)
    rules = await _rules(session, context, prop.id, room_ids, start, end)
    sold = await sold_by_night(session, context, room_ids, start, end)
    days = dates_of.expand_dates(start, end, None)
    room_types = [
        _room_calendar(room, units.get(room.id, 0), plans, base, overrides, rules, sold, days)
        for room in rooms
    ]
    return CalendarRead(
        start=start,
        end=end,
        today=today,
        last_editable_date=dates_of.last_editable_date(today, settings.calendar_horizon_days),
        room_types=room_types,
    )


def _room_calendar(
    room: UnitType,
    units: int,
    plans: list[RatePlan],
    base: dict[tuple[UUID, UUID], Decimal],
    overrides: dict[tuple[UUID, UUID, dt.date], Decimal],
    rules: dict[tuple[UUID, dt.date], tuple[bool, int | None]],
    sold: dict[tuple[UUID, dt.date], int],
    days: list[dt.date],
) -> CalendarRoomType:
    selling = [plan for plan in plans if (plan.id, room.id) in base]
    calendar_days = []
    for day in days:
        closed, min_stay = rules.get((room.id, day), (False, None))
        prices = [
            DayPrice(
                rate_plan_id=plan.id,
                amount=overrides.get((plan.id, room.id, day), base[(plan.id, room.id)]),
                is_override=(plan.id, room.id, day) in overrides,
            )
            for plan in selling
        ]
        left = units - sold.get((room.id, day), 0)
        calendar_days.append(
            CalendarDay(
                date=day,
                available=max(left, 0),
                oversold=left < 0,
                closed=closed,
                min_stay=min_stay,
                prices=prices,
            )
        )
    return CalendarRoomType(
        id=room.id,
        name=room.name,
        units=units,
        rate_plans=[CalendarRatePlan(id=plan.id, name=plan.name) for plan in selling],
        days=calendar_days,
    )


@dataclass(frozen=True)
class StayNight:
    """One night of a stay in one room type on one rate plan."""

    date: dt.date
    amount: Decimal
    units: int
    sold: int
    closed: bool
    min_stay: int | None

    @property
    def available(self) -> int:
        return self.units - self.sold


async def stay_nights(
    session: AsyncSession,
    context: TenantContext,
    property_id: UUID,
    room_type_id: UUID,
    rate_plan_id: UUID,
    nights: list[dt.date],
) -> list[StayNight]:
    """Price, units, units sold and selling rules for each night of a stay.

    The caller has checked that the room type is in use and that the plan sells it.
    Unlike `read_calendar` this has no window limit: a stay may be a year long.
    """
    first, last = nights[0], nights[-1]
    units = (await units_in_use(session, context, [room_type_id])).get(room_type_id, 0)
    links = await find_base_prices(session, context, [rate_plan_id])
    base = next(link.base_amount for link in links if link.unit_type_id == room_type_id)
    overrides = await _price_overrides(session, context, [rate_plan_id], first, last)
    rules = await _rules(session, context, property_id, [room_type_id], first, last)
    sold = await sold_by_night(session, context, [room_type_id], first, last)
    result = []
    for night in nights:
        closed, min_stay = rules.get((room_type_id, night), (False, None))
        result.append(
            StayNight(
                date=night,
                amount=overrides.get((rate_plan_id, room_type_id, night), base),
                units=units,
                sold=sold.get((room_type_id, night), 0),
                closed=closed,
                min_stay=min_stay,
            )
        )
    return result


# ---- changing ---------------------------------------------------------------------------


async def _check_rooms(
    session: AsyncSession, context: TenantContext, property_id: UUID, room_type_ids: list[UUID]
) -> None:
    rows = await session.exec(
        select(col(UnitType.id)).where(
            col(UnitType.tenant_id) == context.tenant_id,
            col(UnitType.property_id) == property_id,
            col(UnitType.is_active).is_(True),
            col(UnitType.id).in_(room_type_ids),
        )
    )
    if set(rows.all()) != set(room_type_ids):
        raise UnknownRoomTypeError


async def _base_prices_of_plan(
    session: AsyncSession,
    context: TenantContext,
    property_id: UUID,
    rate_plan_id: UUID,
    room_type_ids: list[UUID],
) -> dict[UUID, Decimal]:
    """Base price per chosen room type; the plan must be in use and sell all of them."""
    plan = (
        await session.exec(
            select(col(RatePlan.id)).where(
                col(RatePlan.tenant_id) == context.tenant_id,
                col(RatePlan.property_id) == property_id,
                col(RatePlan.id) == rate_plan_id,
                col(RatePlan.status) == ACTIVE,
            )
        )
    ).first()
    if plan is None:
        raise UnknownRatePlanError
    links = await find_base_prices(session, context, [rate_plan_id])
    base = {link.unit_type_id: link.base_amount for link in links}
    if not set(room_type_ids) <= set(base):
        raise PlanDoesNotSellRoomError
    return {room_id: base[room_id] for room_id in room_type_ids}


async def _apply_price(
    session: AsyncSession,
    context: TenantContext,
    property_id: UUID,
    request: CalendarChangeRequest,
    change: SetPrice | ClearPrice,
    days: list[dt.date],
    source: str,
) -> None:
    """Replace the stored prices of these dates; a price equal to the base is not stored."""
    base = await _base_prices_of_plan(
        session, context, property_id, change.rate_plan_id, request.room_type_ids
    )
    await session.exec(
        delete(RateDaily).where(
            col(RateDaily.tenant_id) == context.tenant_id,
            col(RateDaily.rate_plan_id) == change.rate_plan_id,
            col(RateDaily.unit_type_id).in_(request.room_type_ids),
            col(RateDaily.stay_date).in_(days),
        )
    )
    if isinstance(change, ClearPrice):
        return
    rows = [
        {
            "id": uuid.uuid4(),
            "tenant_id": context.tenant_id,
            "rate_plan_id": change.rate_plan_id,
            "unit_type_id": room_id,
            "stay_date": day,
            "amount": change.amount,
            "source": source,
            "updated_by": str(context.user_id),
        }
        for room_id in request.room_type_ids
        if base[room_id] != change.amount
        for day in days
    ]
    if rows:
        await session.exec(insert(RateDaily), params=rows)


# A rule row that no longer says anything and can go.
_UNUSED_RULE = (
    col(Restriction.stop_sell).is_(False),
    col(Restriction.closed_to_arrival).is_(False),
    col(Restriction.closed_to_departure).is_(False),
    col(Restriction.min_stay_arrival).is_(None),
    col(Restriction.min_stay_through).is_(None),
    col(Restriction.max_stay).is_(None),
    col(Restriction.min_advance_days).is_(None),
    col(Restriction.max_advance_days).is_(None),
)


def _rule_values(change: Close | Open | SetMinStay | ClearMinStay) -> dict[str, bool | int | None]:
    """The columns this change sets (the other column of an existing row is kept)."""
    if isinstance(change, Close):
        return {"stop_sell": True}
    if isinstance(change, Open):
        return {"stop_sell": False}
    if isinstance(change, SetMinStay) and change.nights > NO_MIN_STAY:
        return {"min_stay_arrival": change.nights}
    return {"min_stay_arrival": None}


async def _apply_rule(
    session: AsyncSession,
    context: TenantContext,
    property_id: UUID,
    request: CalendarChangeRequest,
    change: Close | Open | SetMinStay | ClearMinStay,
    days: list[dt.date],
    source: str,
) -> None:
    """Close/open dates or set/clear the minimum stay, keeping the other of the two.

    Three statements whatever the size: update the dates that already have a row,
    insert the ones that do not, then remove rows that no longer say anything.
    """
    values = _rule_values(change)
    in_scope = (
        *_room_rules(context, property_id, request.room_type_ids),
        col(Restriction.stay_date).in_(days),
    )
    existing = set(
        (
            await session.exec(
                select(col(Restriction.unit_type_id), col(Restriction.stay_date)).where(*in_scope)
            )
        ).all()
    )
    if existing:
        await session.exec(
            update(Restriction)
            .where(*in_scope)
            .values(**values, source=source, updated_by=str(context.user_id))
        )
    if any(values.values()):  # opening or clearing a date without a row stores nothing
        rows = [
            {
                "id": uuid.uuid4(),
                "tenant_id": context.tenant_id,
                "property_id": property_id,
                "stay_date": day,
                "unit_type_id": room_id,
                "source": source,
                "updated_by": str(context.user_id),
                **values,
            }
            for room_id in request.room_type_ids
            for day in days
            if (room_id, day) not in existing
        ]
        if rows:
            await session.exec(insert(Restriction), params=rows)
    await session.exec(delete(Restriction).where(*in_scope, *_UNUSED_RULE))


async def apply_calendar_change(
    session: AsyncSession, context: TenantContext, prop: Property, request: CalendarChangeRequest
) -> AppliedChange:
    """Apply one change to every chosen room type on every chosen date. All or nothing. Commits."""
    settings = resolve_property_settings(prop.settings)
    property_id = prop.id
    dates_of.check_change_window(
        request.start,
        request.end,
        today=dates_of.property_today(prop.timezone),
        horizon_days=settings.calendar_horizon_days,
        max_days=settings.calendar_max_change_days,
    )
    weekdays = frozenset(request.weekdays) if request.weekdays is not None else None
    days = dates_of.expand_dates(request.start, request.end, weekdays)
    if not days:
        raise NothingToChangeError
    if len(days) * len(request.room_type_ids) > MAX_CELLS_PER_CHANGE:
        raise ChangeTooLargeError
    change = request.change
    if isinstance(change, SetPrice):
        check_rate(change.amount, settings)
    await session.exec(
        select(col(Property.id))
        .where(col(Property.tenant_id) == context.tenant_id, col(Property.id) == property_id)
        .with_for_update()
    )
    await _check_rooms(session, context, property_id, request.room_type_ids)
    source = "manual" if len(days) == 1 and len(request.room_type_ids) == 1 else "bulk"
    if isinstance(change, SetPrice | ClearPrice):
        await _apply_price(session, context, property_id, request, change, days, source)
    else:
        await _apply_rule(session, context, property_id, request, change, days, source)
    await session.commit()
    log.info(
        "Calendar changed property=%s kind=%s dates=%s room_types=%s",
        property_id,
        change.kind,
        len(days),
        len(request.room_type_ids),
    )
    return AppliedChange(dates=days, room_type_ids=list(request.room_type_ids))
