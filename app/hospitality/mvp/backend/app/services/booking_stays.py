"""What makes a stay bookable: its dates, room type, rate plan and guest count.

Shared by quoting, creating and changing a booking, whoever is asking (staff now;
channels and the booking page later).
"""

import datetime as dt
from dataclasses import dataclass
from uuid import UUID

from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.tenant import Property, RatePlan, UnitType
from app.services import calendar_dates as dates_of
from app.services.calendar import StayNight, stay_nights
from app.services.rate_plans import ACTIVE, find_base_prices
from app.tenancy.business_settings import PropertySettings
from app.tenancy.context import TenantContext
from app.tenancy.timezones import property_zone

CHECK_IN_TIME = dt.time(14, 0)
CHECK_OUT_TIME = dt.time(12, 0)
# Hard ceilings, whatever the property's own settings say.
MAX_NIGHTS_CEILING = 366
MAX_UNIT_NIGHTS = 5000  # units × nights of one booking: rows written under the property lock


class StayError(Exception):
    """A stay that cannot be booked as asked."""


class DepartureNotAfterArrivalError(StayError):
    pass


class StayTooLongError(StayError):
    def __init__(self, max_nights: int) -> None:
        super().__init__(f"a stay may be at most {max_nights} nights")
        self.max_nights = max_nights


class ArrivalTooFarBackError(StayError):
    def __init__(self, earliest: dt.date) -> None:
        super().__init__(f"arrival may not be before {earliest.isoformat()}")
        self.earliest = earliest


class ArrivalBeyondHorizonError(StayError):
    def __init__(self, latest: dt.date) -> None:
        super().__init__(f"arrival may not be after {latest.isoformat()}")
        self.latest = latest


class UnknownRoomTypeError(StayError):
    """Not an active room type of this property."""


class UnknownRatePlanError(StayError):
    """Not an active rate plan of this property."""


class PlanDoesNotSellRoomError(StayError):
    pass


class TooManyUnitsError(StayError):
    def __init__(self, limit: int) -> None:
        super().__init__(f"a booking may hold at most {limit} units")
        self.limit = limit


class StayTooLargeError(StayError):
    """Too many units for a stay this long (units × nights over the ceiling)."""


class OverCapacityError(StayError):
    def __init__(self, max_guests: int) -> None:
        super().__init__(f"at most {max_guests} guests fit")
        self.max_guests = max_guests


@dataclass(frozen=True)
class Stay:
    arrival: dt.date
    departure: dt.date
    room_type_id: UUID
    rate_plan_id: UUID
    units: int
    adults: int
    children: int

    @property
    def night_count(self) -> int:
        """Nights slept, from the dates alone (cheap even for an absurd range)."""
        return max((self.departure - self.arrival).days, 0)

    @property
    def nights(self) -> list[dt.date]:
        """Every night slept: arrival up to, not including, departure.

        Empty for a stay longer than any booking may be, so a wild date range sent by a
        client can never make the server build a huge list; `check_dates` refuses it.
        """
        if not 0 < self.night_count <= MAX_NIGHTS_CEILING:
            return []
        return dates_of.expand_dates(self.arrival, self.departure - dates_of.ONE_DAY, None)


@dataclass(frozen=True)
class CheckedStay:
    stay: Stay
    room: UnitType
    plan: RatePlan
    nights: list[StayNight]

    @property
    def max_guests(self) -> int:
        return self.room.max_occupancy * self.stay.units


def check_dates(stay: Stay, prop: Property, settings: PropertySettings) -> None:
    """Refuse dates that are reversed, too long, too far back or beyond the calendar."""
    if stay.departure <= stay.arrival:
        raise DepartureNotAfterArrivalError
    if stay.night_count > min(settings.booking_max_nights, MAX_NIGHTS_CEILING):
        raise StayTooLongError(settings.booking_max_nights)
    today = dates_of.property_today(prop.timezone)
    earliest = today - dt.timedelta(days=settings.booking_backdate_days)
    if stay.arrival < earliest:
        raise ArrivalTooFarBackError(earliest)
    latest = dates_of.last_editable_date(today, settings.calendar_horizon_days)
    if stay.arrival > latest:
        raise ArrivalBeyondHorizonError(latest)


async def check_stay(
    session: AsyncSession,
    context: TenantContext,
    prop: Property,
    settings: PropertySettings,
    stay: Stay,
    *,
    dates_changed: bool = True,
) -> CheckedStay:
    """The stay with its room type, rate plan and nightly prices, or a `StayError`."""
    if dates_changed:
        check_dates(stay, prop, settings)
    if stay.units > settings.booking_max_units:
        raise TooManyUnitsError(settings.booking_max_units)
    if not 0 < stay.night_count <= MAX_NIGHTS_CEILING:
        raise DepartureNotAfterArrivalError  # stored dates are always in range; a guard
    if stay.units * stay.night_count > MAX_UNIT_NIGHTS:
        raise StayTooLargeError
    room = (
        await session.exec(
            select(UnitType).where(
                col(UnitType.tenant_id) == context.tenant_id,
                col(UnitType.property_id) == prop.id,
                col(UnitType.id) == stay.room_type_id,
                col(UnitType.is_active).is_(True),
            )
        )
    ).first()
    if room is None:
        raise UnknownRoomTypeError
    plan = (
        await session.exec(
            select(RatePlan).where(
                col(RatePlan.tenant_id) == context.tenant_id,
                col(RatePlan.property_id) == prop.id,
                col(RatePlan.id) == stay.rate_plan_id,
                col(RatePlan.status) == ACTIVE,
            )
        )
    ).first()
    if plan is None:
        raise UnknownRatePlanError
    links = await find_base_prices(session, context, [plan.id])
    if stay.room_type_id not in {link.unit_type_id for link in links}:
        raise PlanDoesNotSellRoomError
    if stay.adults + stay.children > room.max_occupancy * stay.units:
        raise OverCapacityError(room.max_occupancy * stay.units)
    nights = await stay_nights(session, context, prop.id, room.id, plan.id, stay.nights)
    return CheckedStay(stay=stay, room=room, plan=plan, nights=nights)


def stay_times(stay: Stay, timezone_name: str) -> tuple[dt.datetime, dt.datetime]:
    """Check-in and check-out moments of the stay, in UTC."""
    zone = property_zone(timezone_name)
    start = dt.datetime.combine(stay.arrival, CHECK_IN_TIME, tzinfo=zone)
    end = dt.datetime.combine(stay.departure, CHECK_OUT_TIME, tzinfo=zone)
    return start.astimezone(dt.UTC), end.astimezone(dt.UTC)
