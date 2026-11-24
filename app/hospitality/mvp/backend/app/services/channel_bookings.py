"""Channel bookings inbound: what the channel sold, applied to our bookings.

One idempotent entry point, `handle_booking_event`, whatever brought the event in
(polling today; a webhook later). The envelope is stored first on the unique
(connection, external id, version) key — a repeat delivery changes nothing — then
applied: new bookings are created through `bookings.book()` (the same path staff use),
modifications through `update_booking`, cancellations through `cancel_booking`.

A channel booking is never rejected: the channel has already confirmed it to the
guest (BR-CM-02). A night with nothing left is taken anyway and flagged
`overbooking_risk`; a channel room with no match is stored and flagged
`unmapped_product` for staff to map; a price far from our truth flags
`price_mismatch` as a warning. Acknowledgement is stamped only after the envelope is
durably stored (FR-CM-031).
"""

import datetime as dt
import logging
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.channels.provider import ChannelBookingEvent
from app.models.tenant import (
    ChannelBooking,
    ChannelConnection,
    ChannelMapping,
    Property,
    Reservation,
)
from app.services import bookings as booking_service
from app.services import tenant_audit
from app.services.booking_guests import find_or_create_guest
from app.services.bookings import Stay, cancel_booking, update_booking
from app.services.channel_truth import mappings_of
from app.services.stay_status import STARTED
from app.tenancy.context import TenantContext

log = logging.getLogger(__name__)

ENTITY = "channelbooking"
NEW, MODIFY, CANCEL = "new", "modify", "cancel"
APPLIED, NEEDS_ATTENTION, FAILED = "applied", "needs_attention", "failed"
OVERBOOKING_RISK = "overbooking_risk"
UNMAPPED_PRODUCT = "unmapped_product"
PRICE_MISMATCH = "price_mismatch"
STAY_STARTED = "stay_started"  # the guest has arrived: a person decides
# A channel price further than this from our truth is worth a human look.
PRICE_TOLERANCE = Decimal("0.01")
CHANNEL_CANCEL_NOTE = "Dibatalkan di kanal"


class DuplicateEventError(Exception):
    """This exact version was already applied; a healthy repeat, nothing to do."""


class StaleVersionError(Exception):
    """A newer version of this booking was already applied."""


class UnknownEventKindError(Exception):
    """The channel sent an event kind we do not know."""


async def _existing(
    session: AsyncSession, context: TenantContext, connection_id: UUID, event: ChannelBookingEvent
) -> ChannelBooking | None:
    return (
        await session.exec(
            select(ChannelBooking)
            .where(
                col(ChannelBooking.tenant_id) == context.tenant_id,
                col(ChannelBooking.channel_connection_id) == connection_id,
                col(ChannelBooking.external_booking_id) == event.external_booking_id,
            )
            # numeric order: versions are stored as text ('10' < '9' lexicographically)
            .order_by(func.length(col(ChannelBooking.external_version)).desc())
            .order_by(col(ChannelBooking.external_version).desc())
            .limit(1)
        )
    ).first()


async def _store_envelope(
    session: AsyncSession,
    context: TenantContext,
    connection: ChannelConnection,
    event: ChannelBookingEvent,
) -> ChannelBooking:
    """Store the envelope durably before anything is applied (idempotent)."""
    envelope = ChannelBooking(
        tenant_id=context.tenant_id,
        channel_connection_id=connection.id,
        external_booking_id=event.external_booking_id,
        external_version=str(event.version),
        event_kind=event.kind,
        raw=event.raw,
        processing_status="pending",
    )
    session.add(envelope)
    await session.commit()
    return envelope


def _nights(event: ChannelBookingEvent) -> list[dt.date]:
    arrival = dt.date.fromisoformat(event.arrival)
    departure = dt.date.fromisoformat(event.departure)
    return [arrival + dt.timedelta(days=n) for n in range(max((departure - arrival).days, 1))]


async def _mapping_for(
    session: AsyncSession, context: TenantContext, connection_id: UUID, event: ChannelBookingEvent
) -> ChannelMapping | None:
    """The mapping that sells the channel room/rate this booking names, if any."""
    mappings = await mappings_of(session, context, connection_id)
    for mapping in mappings:
        if (
            mapping.external_room_id == event.external_room_id
            and mapping.external_rate_id == event.external_rate_id
        ):
            return mapping
    return None


async def _our_truth_total(
    session: AsyncSession,
    context: TenantContext,
    prop: Property,
    mapping: ChannelMapping,
    event: ChannelBookingEvent,
) -> Decimal | None:
    """Our calendar price for the same stay (before the connection's adjustment)."""
    from app.services.calendar import stay_nights

    nights = _nights(event)
    try:
        plan_nights = await stay_nights(
            session, context, prop.id, mapping.unit_type_id, mapping.rate_plan_id, nights
        )
    except Exception:  # noqa: BLE001 — truth is advisory here
        return None
    return sum((night.amount for night in plan_nights), Decimal("0")) * event.units


async def handle_booking_event(
    session: AsyncSession,
    context: TenantContext,
    connection: ChannelConnection,
    event: ChannelBookingEvent,
) -> ChannelBooking:
    """Apply one channel booking event. Idempotent. Commits.

    Returns the envelope, `applied` or `needs_attention` with a reason.
    """
    existing = await _existing(session, context, connection.id, event)
    if existing is not None and existing.processing_status in (APPLIED, NEEDS_ATTENTION):
        if int(existing.external_version) >= event.version:
            if int(existing.external_version) == event.version:
                raise DuplicateEventError
            raise StaleVersionError
    envelope = await _store_envelope(session, context, connection, event)
    prop = (
        await session.exec(
            select(Property).where(
                col(Property.tenant_id) == context.tenant_id,
                col(Property.id) == connection.property_id,
            )
        )
    ).one()
    try:
        if event.kind == CANCEL:
            await _apply_cancel(session, context, connection, envelope, event)
        elif event.kind in (NEW, MODIFY):
            await _apply_stay(session, context, connection, envelope, event, prop)
        else:
            raise UnknownEventKindError(event.kind)
    except _Attention as attention:
        envelope.processing_status = NEEDS_ATTENTION
        envelope.attention_reason = attention.reason
    except Exception as exc:  # noqa: BLE001 — a channel booking is never silently lost
        log.exception(
            "Channel booking failed external=%s v%s", event.external_booking_id, event.version
        )
        envelope.processing_status = FAILED
        envelope.attention_reason = f"processing_error: {type(exc).__name__}"[:120]
    else:
        envelope.processing_status = APPLIED
        envelope.attention_reason = (envelope.raw or {}).get("_server", {}).get("attention_flag")
    envelope.processed_at = dt.datetime.now(dt.UTC)
    envelope.acknowledged_at = dt.datetime.now(dt.UTC)
    session.add(envelope)
    await session.commit()
    await tenant_audit.record(
        session,
        context,
        f"channel.booking.{envelope.processing_status}",
        property_id=connection.property_id,
        entity_table=ENTITY,
        entity_id=envelope.id,
        payload={
            "external_booking_id": event.external_booking_id,
            "version": event.version,
            "kind": event.kind,
            **({"reason": envelope.attention_reason} if envelope.attention_reason else {}),
        },
    )
    await session.commit()
    log.info(
        "Channel booking %s %s external=%s v%s",
        envelope.processing_status,
        event.kind,
        event.external_booking_id,
        event.version,
    )
    return envelope


class _Attention(Exception):
    """Applying the event needs a person; the envelope says why."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


async def _apply_stay(
    session: AsyncSession,
    context: TenantContext,
    connection: ChannelConnection,
    envelope: ChannelBooking,
    event: ChannelBookingEvent,
    prop: Property,
) -> None:
    """Create (new) or change (modify) the reservation behind the booking."""
    mapping = await _mapping_for(session, context, connection.id, event)
    if mapping is None:
        raise _Attention(UNMAPPED_PRODUCT)
    guest = await find_or_create_guest(
        session, context.tenant_id, event.guests.name, event.guests.phone
    )
    stay = Stay(
        arrival=dt.date.fromisoformat(event.arrival),
        departure=dt.date.fromisoformat(event.departure),
        room_type_id=mapping.unit_type_id,
        rate_plan_id=mapping.rate_plan_id,
        units=event.units,
        adults=1,
        children=0,
    )
    # A channel booking is never rejected for lack of rooms (BR-CM-02): the shortage
    # is flagged rather than refused, and the flag clears when the night recovers.
    # On a modify, the nights this reservation itself already holds are not a shortage.
    own_units = await _own_units(session, context, connection, event, stay)
    shortage = await _has_shortage(session, context, stay, own_units)
    total = Decimal(str(event.total_amount))
    if event.kind == NEW:
        reservation = await booking_service.book(
            session,
            context,
            prop,
            booking_service.BookingOrder(
                stay=stay,
                guest=guest,
                source=await _channel_row(session, context, connection),
                total_amount=total,
                allow_overbooking=True,
                booked_by="channel",
            ),
        )
    else:
        reservation = await _reservation_for(session, context, connection, event)
        if reservation is not None and reservation.status in STARTED:
            raise _Attention(STAY_STARTED)
        if reservation is None or reservation.status != "confirmed":
            raise _Attention(UNMAPPED_PRODUCT)  # nothing to modify; staff must look
        from app.schemas.bookings import BookingUpdateRequest

        reservation = await update_booking(
            session,
            context,
            prop,
            reservation.id,
            BookingUpdateRequest(**_channel_changes(stay, total, event)),
        )
    envelope.reservation_id = reservation.id
    session.add(envelope)
    await _set_channel_fields(session, reservation, connection, event)
    mismatch = await _price_mismatch(session, context, prop, mapping, event, total)
    if shortage:
        raise _Attention(OVERBOOKING_RISK)
    if mismatch:
        # stored under a server-only key: a channel cannot forge a reason
        envelope.raw = {**dict(envelope.raw), "_server": {"attention_flag": PRICE_MISMATCH}}


async def _apply_cancel(
    session: AsyncSession,
    context: TenantContext,
    connection: ChannelConnection,
    envelope: ChannelBooking,
    event: ChannelBookingEvent,
) -> None:
    reservation = await _reservation_for(session, context, connection, event)
    if reservation is not None and reservation.status in STARTED:
        raise _Attention(STAY_STARTED)
    if reservation is None or reservation.status != "confirmed":
        # a cancel for a booking we never applied (e.g. it was unmapped) is done:
        # there is nothing to cancel, and nothing to ask staff for
        envelope.processing_status = APPLIED
        return
    reservation_id = reservation.id  # read before any rollback
    prop = await _property_of(session, context, connection)
    await cancel_booking(session, context, prop, reservation_id, CHANNEL_CANCEL_NOTE)
    envelope.reservation_id = reservation_id
    session.add(envelope)


async def _property_of(
    session: AsyncSession, context: TenantContext, connection: ChannelConnection
) -> Property:
    return (
        await session.exec(
            select(Property).where(
                col(Property.tenant_id) == context.tenant_id,
                col(Property.id) == connection.property_id,
            )
        )
    ).one()


async def _channel_row(
    session: AsyncSession, context: TenantContext, connection: ChannelConnection
):
    from app.models.tenant import Channel

    return (
        await session.exec(
            select(Channel).where(
                col(Channel.tenant_id) == context.tenant_id,
                col(Channel.id) == connection.channel_id,
            )
        )
    ).one()


async def _reservation_for(
    session: AsyncSession,
    context: TenantContext,
    connection: ChannelConnection,
    event: ChannelBookingEvent,
) -> Reservation | None:
    """The reservation an earlier version of this booking created."""
    rows = (
        await session.exec(
            select(ChannelBooking)
            .where(
                col(ChannelBooking.tenant_id) == context.tenant_id,
                col(ChannelBooking.channel_connection_id) == connection.id,
                col(ChannelBooking.external_booking_id) == event.external_booking_id,
                col(ChannelBooking.reservation_id).is_not(None),
            )
            .order_by(func.length(col(ChannelBooking.external_version)).desc())
            .order_by(col(ChannelBooking.external_version).desc())
        )
    ).all()
    for row in rows:
        reservation = (
            await session.exec(
                select(Reservation).where(
                    col(Reservation.tenant_id) == context.tenant_id,
                    col(Reservation.id) == row.reservation_id,
                )
            )
        ).first()
        if reservation is not None:
            return reservation
    return None


async def _own_units(
    session: AsyncSession,
    context: TenantContext,
    connection: ChannelConnection,
    event: ChannelBookingEvent,
    stay: Stay,
) -> int:
    """Units this booking's reservation already holds on the stay's room type (0 on new)."""
    if event.kind == NEW:
        return 0
    reservation = await _reservation_for(session, context, connection, event)
    if reservation is None or reservation.status != "confirmed":
        return 0
    from app.services.bookings import lines_of

    lines = await lines_of(session, context, [reservation.id])
    if not lines or lines[0].unit_type_id != stay.room_type_id:
        return 0
    return len(lines)


async def _has_shortage(
    session: AsyncSession, context: TenantContext, stay: Stay, own_units: int
) -> bool:
    """True when one of the stay's nights has fewer units left than it needs."""
    from app.services.inventory import taken_by_night, units_in_use

    sold = await taken_by_night(
        session, context, [stay.room_type_id], stay.nights[0], stay.nights[-1]
    )
    in_use = await units_in_use(session, context, [stay.room_type_id])
    available_room = in_use.get(stay.room_type_id, 0)
    return any(
        available_room - sold.get((stay.room_type_id, night), 0) + own_units < stay.units
        for night in stay.nights
    )


async def _price_mismatch(
    session: AsyncSession,
    context: TenantContext,
    prop: Property,
    mapping: ChannelMapping,
    event: ChannelBookingEvent,
    total: Decimal,
) -> bool:
    truth = await _our_truth_total(session, context, prop, mapping, event)
    if truth is None or truth == Decimal("0"):
        return False
    difference = abs(total - truth) / truth
    return difference > PRICE_TOLERANCE


async def _set_channel_fields(
    session: AsyncSession,
    reservation: Reservation,
    connection: ChannelConnection,
    event: ChannelBookingEvent,
) -> None:
    """Commission, collect model and the channel's own reference on the reservation."""
    reservation.channel_id = connection.channel_id
    reservation.channel_reference = event.external_booking_id[:64]
    reservation.payment_collect_model = event.payment_collect
    commission = Decimal(str(connection.settings.get("commission_percent", "0")))
    if commission and event.total_amount:
        reservation.commission_amount = (
            Decimal(str(event.total_amount)) * commission / Decimal("100")
        ).quantize(Decimal("1"))
    session.add(reservation)
    await session.commit()


def _channel_changes(stay: Stay, total: Decimal, event: ChannelBookingEvent) -> dict:
    """The update payload a channel modification maps onto (incl. guest corrections)."""
    return {
        "arrival": stay.arrival,
        "departure": stay.departure,
        "room_type_id": stay.room_type_id,
        "rate_plan_id": stay.rate_plan_id,
        "units": stay.units,
        "total_amount": total,
        "guest_name": event.guests.name,
        **({"guest_phone": event.guests.phone} if event.guests.phone else {}),
        "allow_overbooking": True,
    }
