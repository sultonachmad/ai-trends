"""What a property sells on one channel, per date: the truth the sender pushes.

For every matched pair (our room type + rate plan → the channel's room + rate) this is
availability, closed state, minimum stay and the price a guest pays on the channel:
our calendar price with the connection's adjustment applied, whole rupiah.

Availability is what the channel may sell: our units in use minus what bookings hold,
minus any units the property keeps for direct or walk-in sale — never below zero, and
zero on a date closed for sale.
"""

import datetime as dt
from decimal import ROUND_HALF_UP, Decimal
from uuid import UUID

from sqlmodel.ext.asyncio.session import AsyncSession

from app.channels.provider import AriDay
from app.models.tenant import ChannelConnection, ChannelMapping, Property
from app.services.calendar import StayNight, stay_nights
from app.services.inventory import taken_by_night, units_in_use
from app.tenancy.business_settings import PropertySettings
from app.tenancy.context import TenantContext

HUNDRED = Decimal("100")
ONE_RUPIAH = Decimal("1")


def adjusted_price(price: Decimal, adjustment_percent: Decimal) -> int:
    """Our price with the connection's adjustment applied, whole rupiah (half up)."""
    factor = (HUNDRED + adjustment_percent) / HUNDRED
    return int((price * factor).quantize(ONE_RUPIAH, rounding=ROUND_HALF_UP))


async def mappings_of(
    session: AsyncSession, context: TenantContext, connection_id: UUID
) -> list[ChannelMapping]:
    from sqlmodel import col, select

    from app.models.tenant import ChannelMapping as Mapping

    rows = await session.exec(
        select(Mapping)
        .where(
            col(Mapping.tenant_id) == context.tenant_id,
            col(Mapping.channel_connection_id) == connection_id,
            col(Mapping.rate_plan_id).is_not(None),
            col(Mapping.external_rate_id).is_not(None),
        )
        .order_by(col(Mapping.created_at), col(Mapping.id))
    )
    return list(rows.all())


async def build_days(
    session: AsyncSession,
    context: TenantContext,
    prop: Property,
    settings: PropertySettings,
    connection: ChannelConnection,
    mappings: list[ChannelMapping],
    dates: list[dt.date],
) -> dict[str, list[AriDay]]:
    """The truth per channel room for `dates`, from the calendar and bookings.

    Rooms with no mapping are absent — nothing is sold there. A paused connection is
    sent as closed everywhere; the sender decides that, not this builder.
    """
    if not mappings or not dates:
        return {}
    room_ids = list({mapping.unit_type_id for mapping in mappings})
    ordered = sorted(dates)
    sold = await taken_by_night(session, context, room_ids, ordered[0], ordered[-1])
    in_use = await units_in_use(session, context, room_ids)

    # one stay_nights query per distinct (room type, rate plan) pair
    nights: dict[tuple[UUID, UUID], dict[dt.date, StayNight]] = {}
    for mapping in mappings:
        key = (mapping.unit_type_id, mapping.rate_plan_id)
        if key not in nights:
            plan_nights = await stay_nights(
                session, context, prop.id, mapping.unit_type_id, mapping.rate_plan_id, ordered
            )
            nights[key] = {night.date: night for night in plan_nights}

    adjustment = connection.rate_markup_pct
    hold_back = settings.channel_hold_back_units
    per_channel_room: dict[str, list[ChannelMapping]] = {}
    for mapping in mappings:
        per_channel_room.setdefault(mapping.external_room_id, []).append(mapping)

    days: dict[str, list[AriDay]] = {}
    for external_room, room_mappings in per_channel_room.items():
        room_type_id = room_mappings[0].unit_type_id
        available_room = in_use.get(room_type_id, 0)
        room_days = []
        for date in ordered:
            night = nights[(room_type_id, room_mappings[0].rate_plan_id)].get(date)
            closed = night.closed if night else False
            min_stay = night.min_stay if night else None
            available = max(available_room - sold.get((room_type_id, date), 0) - hold_back, 0)
            if closed:
                available = 0
            prices = {}
            for mapping in room_mappings:
                night = nights[(mapping.unit_type_id, mapping.rate_plan_id)].get(date)
                if night is not None:
                    prices[mapping.external_rate_id] = adjusted_price(night.amount, adjustment)
            room_days.append(
                AriDay(
                    date=date.isoformat(),
                    available=available,
                    closed=closed,
                    min_stay=min_stay,
                    prices=prices,
                )
            )
        days[external_room] = room_days
    return days
