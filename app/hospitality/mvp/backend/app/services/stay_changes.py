"""Moving the end of a stay that has already begun.

Nights already slept keep their prices. Only the nights added or removed change, so an
in-house guest's stay is never repriced from today's calendar.
"""

import datetime as dt
from collections import defaultdict
from dataclasses import replace
from decimal import Decimal
from uuid import UUID

from sqlalchemy import delete, insert, update
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.tenant import Property, Reservation, ReservationDailyRate, ReservationUnit
from app.schemas.bookings import BookingUpdateRequest
from app.services import calendar_dates as dates_of
from app.services import inventory
from app.services.booking_stays import Stay, StayTooLongError, check_dates, check_stay, stay_times
from app.services.bookings import (
    PRICE_EDITED,
    _cell_amounts,
    _changed_stay,
    _take,
    occupied_unit_ids,
)
from app.services.stay_status import LEFT_EARLY
from app.tenancy.business_settings import PropertySettings, resolve_property_settings
from app.tenancy.context import TenantContext


class DepartureInPastError(Exception):
    """An in-house stay cannot end before today."""


class RoomTakenError(Exception):
    """The room is taken by another stay on these dates."""


def _set_end(prop: Property, stay: Stay, lines: list[ReservationUnit]) -> None:
    _, end_at = stay_times(stay, prop.timezone)
    for line in lines:
        line.departure_date = stay.departure
        line.end_at = end_at
        line.blocked_until = end_at


async def shorten_stay(
    session: AsyncSession,
    context: TenantContext,
    prop: Property,
    booking: Reservation,
    lines: list[ReservationUnit],
    old: Stay,
    departure: dt.date,
    *,
    keep_price: bool,
) -> Stay:
    """End the stay earlier and put the unused nights back on sale. Does not commit."""
    new = replace(old, departure=departure)
    line_ids = [line.id for line in lines]
    removed: dict[UUID, Decimal] = defaultdict(Decimal)
    rows = await session.exec(
        select(ReservationDailyRate).where(
            col(ReservationDailyRate.tenant_id) == context.tenant_id,
            col(ReservationDailyRate.reservation_unit_id).in_(line_ids),
            col(ReservationDailyRate.stay_date) >= departure,
        )
    )
    for rate in rows.all():
        removed[rate.reservation_unit_id] += rate.amount
    await session.exec(
        delete(ReservationDailyRate).where(
            col(ReservationDailyRate.tenant_id) == context.tenant_id,
            col(ReservationDailyRate.reservation_unit_id).in_(line_ids),
            col(ReservationDailyRate.stay_date) >= departure,
        )
    )
    await inventory.release_units(
        session,
        context,
        old.room_type_id,
        [night for night in old.nights if night >= departure],
        old.units,
    )
    if keep_price:
        await _move_to_last_night(session, context, removed, departure)
        booking.source_detail = {**booking.source_detail, PRICE_EDITED: True}
    else:
        for line in lines:
            line.total_amount -= removed[line.id]
        booking.total_amount -= sum(removed.values(), Decimal(0))
    booking.source_detail = {**booking.source_detail, LEFT_EARLY: True}
    _set_end(prop, new, lines)
    session.add_all(lines)
    return new


async def _move_to_last_night(
    session: AsyncSession,
    context: TenantContext,
    removed: dict[UUID, Decimal],
    departure: dt.date,
) -> None:
    """The full price stays on the booking, carried by the last night slept."""
    for line_id, amount in removed.items():
        await session.exec(
            update(ReservationDailyRate)
            .where(
                col(ReservationDailyRate.tenant_id) == context.tenant_id,
                col(ReservationDailyRate.reservation_unit_id) == line_id,
                col(ReservationDailyRate.stay_date) == departure - dates_of.ONE_DAY,
            )
            .values(amount=ReservationDailyRate.amount + amount)
            .execution_options(synchronize_session=False)
        )


async def _extend_stay(
    session: AsyncSession,
    context: TenantContext,
    prop: Property,
    settings: PropertySettings,
    booking: Reservation,
    lines: list[ReservationUnit],
    old: Stay,
    departure: dt.date,
    allow_overbooking: bool,
) -> Stay:
    new = replace(old, departure=departure)
    if new.night_count > settings.booking_max_nights:
        raise StayTooLongError(settings.booking_max_nights)
    added = replace(old, arrival=old.departure, departure=departure)
    today = dates_of.property_today(prop.timezone)
    check_dates(replace(added, arrival=max(added.arrival, today)), prop, settings)
    checked = await check_stay(session, context, prop, settings, added, dates_changed=False)
    start_at, blocked_until = stay_times(new, prop.timezone)
    rooms = [line.unit_id for line in lines if line.unit_id is not None]
    if await occupied_unit_ids(session, context, rooms, start_at, blocked_until, booking.id):
        await session.rollback()
        raise RoomTakenError
    await _take(session, context, prop, checked, allow_overbooking)
    cells = _cell_amounts(checked, None)
    per_unit = len(checked.nights)
    rate_rows = []
    for index, line in enumerate(lines):
        amounts = cells[index * per_unit : (index + 1) * per_unit]
        line.total_amount += sum(amounts, Decimal(0))
        rate_rows.extend(
            {
                "tenant_id": context.tenant_id,
                "reservation_unit_id": line.id,
                "stay_date": night.date,
                "rate_plan_id": old.rate_plan_id,
                "unit_type_id": old.room_type_id,
                "amount": amount,
            }
            for night, amount in zip(checked.nights, amounts, strict=True)
        )
    await session.exec(insert(ReservationDailyRate), params=rate_rows)
    booking.total_amount += sum(cells, Decimal(0))
    _set_end(prop, new, lines)
    session.add_all(lines)
    return new


async def change_in_house_stay(
    session: AsyncSession,
    context: TenantContext,
    prop: Property,
    booking: Reservation,
    lines: list[ReservationUnit],
    old: Stay,
    request: BookingUpdateRequest,
) -> Stay:
    """Apply guest counts and a new departure to a checked-in stay. Does not commit."""
    settings = resolve_property_settings(prop.settings)
    wanted = _changed_stay(old, request)
    counted = replace(old, adults=wanted.adults, children=wanted.children)
    if counted != old:
        await check_stay(session, context, prop, settings, counted, dates_changed=False)
    if wanted.departure == old.departure:
        return counted
    today = dates_of.property_today(prop.timezone)
    if wanted.departure < today or wanted.departure <= old.arrival:
        await session.rollback()
        raise DepartureInPastError
    if wanted.departure < old.departure:
        return await shorten_stay(
            session, context, prop, booking, lines, counted, wanted.departure, keep_price=True
        )
    return await _extend_stay(
        session,
        context,
        prop,
        settings,
        booking,
        lines,
        counted,
        wanted.departure,
        request.allow_overbooking,
    )
