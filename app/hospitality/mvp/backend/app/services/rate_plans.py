"""Rate plans: a name, terms, and the normal nightly price of each room type they sell.

The base price lives on the plan/room-type link. The calendar stores only the dates
whose price differs (see `services/calendar.py`).
"""

import logging
import uuid
from decimal import Decimal
from uuid import UUID

from sqlalchemy import delete, func
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.tenant import Property, RateDaily, RatePlan, RatePlanUnitType, UnitType
from app.schemas.rate_plans import (
    RatePlanCreateRequest,
    RatePlanRead,
    RatePlanUpdateRequest,
    RoomPrice,
    RoomPriceRead,
)
from app.services import rate_policies as policies
from app.services.rate_policies import CancellationTerms
from app.tenancy.business_settings import PropertySettings, resolve_property_settings
from app.tenancy.context import TenantContext

log = logging.getLogger(__name__)

ACTIVE = "active"
INACTIVE = "inactive"


class RatePlanNotFoundError(Exception):
    """No such rate plan on the caller's property."""


class RatePlanNameTakenError(Exception):
    """Another active rate plan of the property already has this name."""


class TooManySwitchedOffError(Exception):
    """So many switched-off records that a new one may not be added; reuse an old one."""


class RatePlanLimitError(Exception):
    """The property has as many active rate plans as it may."""

    def __init__(self, limit: int) -> None:
        super().__init__(f"rate plan limit reached ({limit})")
        self.limit = limit


class UnknownRoomTypeError(Exception):
    """A price names a room type that is not an active room type of this property."""


class RateOutOfRangeError(Exception):
    """A nightly price outside the property's allowed range."""

    def __init__(self, minimum: int, maximum: int) -> None:
        super().__init__(f"price must be between {minimum} and {maximum}")
        self.minimum = minimum
        self.maximum = maximum


def check_rate(amount: Decimal, settings: PropertySettings) -> None:
    """Refuse a nightly price outside the property's range."""
    if not settings.room_rate_min_amount_idr <= amount <= settings.room_rate_max_amount_idr:
        raise RateOutOfRangeError(
            settings.room_rate_min_amount_idr, settings.room_rate_max_amount_idr
        )


async def _lock_property(session: AsyncSession, context: TenantContext, property_id: UUID) -> None:
    """Serialise changes to a property's rate plans (names, limit, shared terms records)."""
    await session.exec(
        select(col(Property.id))
        .where(col(Property.tenant_id) == context.tenant_id, col(Property.id) == property_id)
        .with_for_update()
    )


async def find_rate_plans(
    session: AsyncSession, context: TenantContext, property_id: UUID, *, active_only: bool = False
) -> list[RatePlan]:
    """The property's rate plans in creation order."""
    statement = select(RatePlan).where(
        col(RatePlan.tenant_id) == context.tenant_id, col(RatePlan.property_id) == property_id
    )
    if active_only:
        statement = statement.where(col(RatePlan.status) == ACTIVE)
    rows = await session.exec(
        statement.order_by(col(RatePlan.sort_order), col(RatePlan.created_at), col(RatePlan.id))
    )
    return list(rows.all())


async def find_base_prices(
    session: AsyncSession, context: TenantContext, plan_ids: list[UUID]
) -> list[RatePlanUnitType]:
    """Every plan/room-type link of the given plans."""
    if not plan_ids:
        return []
    rows = await session.exec(
        select(RatePlanUnitType).where(
            col(RatePlanUnitType.tenant_id) == context.tenant_id,
            col(RatePlanUnitType.rate_plan_id).in_(plan_ids),
        )
    )
    return list(rows.all())


async def _read_many(
    session: AsyncSession, context: TenantContext, plans: list[RatePlan]
) -> list[RatePlanRead]:
    links = await find_base_prices(session, context, [plan.id for plan in plans])
    room_order = await _room_order(session, context, {link.unit_type_id for link in links})
    terms = await policies.policies_by_id(
        session, context, {plan.cancellation_policy_id for plan in plans}
    )
    result = []
    for plan in plans:
        own = sorted(
            (link for link in links if link.rate_plan_id == plan.id),
            key=lambda link: room_order.get(link.unit_type_id, 0),
        )
        chosen = policies.terms_of(terms[plan.cancellation_policy_id])
        result.append(
            RatePlanRead(
                id=plan.id,
                name=plan.name,
                meal_plan=plan.meal_plan,
                non_refundable=chosen.non_refundable,
                free_cancellation_days=chosen.free_days,
                is_active=plan.status == ACTIVE,
                prices=[
                    RoomPriceRead(room_type_id=link.unit_type_id, amount=link.base_amount)
                    for link in own
                ],
            )
        )
    return result


async def _room_order(
    session: AsyncSession, context: TenantContext, room_type_ids: set[UUID]
) -> dict[UUID, int]:
    if not room_type_ids:
        return {}
    rows = await session.exec(
        select(col(UnitType.id), col(UnitType.sort_order)).where(
            col(UnitType.tenant_id) == context.tenant_id, col(UnitType.id).in_(room_type_ids)
        )
    )
    return {room_type_id: sort_order for room_type_id, sort_order in rows.all()}


async def list_rate_plans(
    session: AsyncSession, context: TenantContext, property_id: UUID
) -> list[RatePlanRead]:
    plans = await find_rate_plans(session, context, property_id)
    return await _read_many(session, context, plans)


async def _check_prices(
    session: AsyncSession,
    context: TenantContext,
    property_id: UUID,
    prices: list[RoomPrice],
    settings: PropertySettings,
) -> None:
    for price in prices:
        check_rate(price.amount, settings)
    wanted = {price.room_type_id for price in prices}
    rows = await session.exec(
        select(col(UnitType.id)).where(
            col(UnitType.tenant_id) == context.tenant_id,
            col(UnitType.property_id) == property_id,
            col(UnitType.is_active).is_(True),
            col(UnitType.id).in_(wanted),
        )
    )
    if set(rows.all()) != wanted:
        raise UnknownRoomTypeError


async def _check_name_free(
    session: AsyncSession, context: TenantContext, property_id: UUID, name: str, own_id: UUID | None
) -> None:
    statement = select(col(RatePlan.id)).where(
        col(RatePlan.tenant_id) == context.tenant_id,
        col(RatePlan.property_id) == property_id,
        col(RatePlan.status) == ACTIVE,
        func.lower(col(RatePlan.name)) == name.lower(),
    )
    if own_id is not None:
        statement = statement.where(col(RatePlan.id) != own_id)
    if (await session.exec(statement)).first() is not None:
        raise RatePlanNameTakenError


async def _check_limit(
    session: AsyncSession, context: TenantContext, property_id: UUID, settings: PropertySettings
) -> None:
    active = (
        await session.exec(
            select(func.count())
            .select_from(RatePlan)
            .where(
                col(RatePlan.tenant_id) == context.tenant_id,
                col(RatePlan.property_id) == property_id,
                col(RatePlan.status) == ACTIVE,
            )
        )
    ).one()
    if int(active) >= settings.max_rate_plans:
        raise RatePlanLimitError(settings.max_rate_plans)


async def _active_among(
    session: AsyncSession, context: TenantContext, room_type_ids: set[UUID]
) -> set[UUID]:
    if not room_type_ids:
        return set()
    rows = await session.exec(
        select(col(UnitType.id)).where(
            col(UnitType.tenant_id) == context.tenant_id,
            col(UnitType.id).in_(room_type_ids),
            col(UnitType.is_active).is_(True),
        )
    )
    return set(rows.all())


async def _replace_prices(
    session: AsyncSession, context: TenantContext, plan: RatePlan, prices: list[RoomPrice]
) -> None:
    """Make the plan sell exactly `prices`; overrides of dropped room types go with them.

    A room type that is switched off cannot be priced, so its price is left as it is:
    switching the room type back on brings the price back with it.
    """
    current = {
        link.unit_type_id: link for link in await find_base_prices(session, context, [plan.id])
    }
    wanted = {price.room_type_id: price.amount for price in prices}
    in_use = await _active_among(session, context, set(current))
    dropped = [
        room_type_id
        for room_type_id in current
        if room_type_id not in wanted and room_type_id in in_use
    ]
    for room_type_id in dropped:
        await session.delete(current[room_type_id])
        # a mapping to a plan that no longer prices the room would break every push
        from sqlalchemy import delete as _delete

        from app.models.tenant import ChannelMapping

        await session.exec(
            _delete(ChannelMapping).where(
                col(ChannelMapping.tenant_id) == context.tenant_id,
                col(ChannelMapping.rate_plan_id) == plan.id,
                col(ChannelMapping.unit_type_id) == room_type_id,
            )
        )
    if dropped:
        await session.exec(
            delete(RateDaily).where(
                col(RateDaily.tenant_id) == context.tenant_id,
                col(RateDaily.rate_plan_id) == plan.id,
                col(RateDaily.unit_type_id).in_(dropped),
            )
        )
    for room_type_id, amount in wanted.items():
        link = current.get(room_type_id) or RatePlanUnitType(
            tenant_id=context.tenant_id, rate_plan_id=plan.id, unit_type_id=room_type_id
        )
        link.base_amount = amount
        session.add(link)
        # A date already priced at the new base is no longer different from it.
        await session.exec(
            delete(RateDaily).where(
                col(RateDaily.tenant_id) == context.tenant_id,
                col(RateDaily.rate_plan_id) == plan.id,
                col(RateDaily.unit_type_id) == room_type_id,
                col(RateDaily.amount) == amount,
            )
        )


async def create_rate_plan(
    session: AsyncSession, context: TenantContext, prop: Property, request: RatePlanCreateRequest
) -> RatePlanRead:
    """Create a rate plan with its base prices. Commits."""
    settings = resolve_property_settings(prop.settings)
    property_id = prop.id
    await _lock_property(session, context, property_id)
    await _check_limit(session, context, property_id, settings)
    await _check_name_free(session, context, property_id, request.name, None)
    await _check_prices(session, context, property_id, request.prices, settings)
    free_days = (
        request.free_cancellation_days
        if request.free_cancellation_days is not None
        else settings.free_cancellation_days
    )
    terms = CancellationTerms(
        non_refundable=request.non_refundable,
        free_days=None if request.non_refundable else free_days,
    )
    cancellation = await policies.cancellation_policy_for(session, context, property_id, terms)
    payment = await policies.deposit_policy_for(session, context, property_id)
    existing = len(await find_rate_plans(session, context, property_id))
    if existing >= settings.max_rate_plans * settings.switched_off_allowance:
        raise TooManySwitchedOffError
    plan = RatePlan(
        tenant_id=context.tenant_id,
        property_id=property_id,
        code=f"rp-{uuid.uuid4().hex[:10]}",
        name=request.name,
        meal_plan=request.meal_plan,
        cancellation_policy_id=cancellation.id,
        payment_policy_id=payment.id,
        sort_order=existing + 1,
        created_by=str(context.user_id),
    )
    session.add(plan)
    await session.flush()
    await _replace_prices(session, context, plan, request.prices)
    await session.commit()
    log.info("Rate plan created rate_plan=%s room_types=%s", plan.id, len(request.prices))
    return (await _read_many(session, context, [plan]))[0]


async def _get(
    session: AsyncSession, context: TenantContext, property_id: UUID, rate_plan_id: UUID
) -> RatePlan:
    plan = (
        await session.exec(
            select(RatePlan)
            .where(
                col(RatePlan.tenant_id) == context.tenant_id,
                col(RatePlan.property_id) == property_id,
                col(RatePlan.id) == rate_plan_id,
            )
            .with_for_update()
        )
    ).first()
    if plan is None:
        raise RatePlanNotFoundError
    return plan


async def _changed_terms(
    session: AsyncSession,
    context: TenantContext,
    plan: RatePlan,
    request: RatePlanUpdateRequest,
    settings: PropertySettings,
) -> CancellationTerms | None:
    """The new terms when the request changes them, else None."""
    if request.non_refundable is None and request.free_cancellation_days is None:
        return None
    if request.non_refundable:
        return CancellationTerms(non_refundable=True, free_days=None)
    current = policies.terms_of(
        (await policies.policies_by_id(session, context, {plan.cancellation_policy_id}))[
            plan.cancellation_policy_id
        ]
    )
    if request.free_cancellation_days is not None:
        # Days sent on their own mean "free cancellation", also for a non-refundable plan.
        return CancellationTerms(non_refundable=False, free_days=request.free_cancellation_days)
    free_days = current.free_days if current.free_days is not None else None
    return CancellationTerms(
        non_refundable=False,
        free_days=free_days if free_days is not None else settings.free_cancellation_days,
    )


async def update_rate_plan(
    session: AsyncSession,
    context: TenantContext,
    prop: Property,
    rate_plan_id: UUID,
    request: RatePlanUpdateRequest,
) -> RatePlanRead:
    """Change the fields that were sent. Commits."""
    settings = resolve_property_settings(prop.settings)
    property_id = prop.id
    await _lock_property(session, context, property_id)
    plan = await _get(session, context, property_id, rate_plan_id)
    was_active = plan.status == ACTIVE
    will_be_active = was_active if request.is_active is None else request.is_active
    new_name = request.name if request.name is not None else plan.name
    if will_be_active and not was_active:
        await _check_limit(session, context, property_id, settings)
    if will_be_active and (not was_active or new_name.lower() != plan.name.lower()):
        await _check_name_free(session, context, property_id, new_name, plan.id)
    if request.prices is not None:
        await _check_prices(session, context, property_id, request.prices, settings)
        await _replace_prices(session, context, plan, request.prices)
    terms = await _changed_terms(session, context, plan, request, settings)
    if terms is not None:
        cancellation = await policies.cancellation_policy_for(session, context, property_id, terms)
        plan.cancellation_policy_id = cancellation.id
    plan.name = new_name
    if request.meal_plan is not None:
        plan.meal_plan = request.meal_plan
    plan.status = ACTIVE if will_be_active else INACTIVE
    plan.updated_by = str(context.user_id)
    session.add(plan)
    if request.prices is not None:
        # every room the plan now prices differently, over the whole window
        from app.services.calendar_dates import property_today
        from app.services.channel_queue import enqueue as enqueue_channels
        from app.services.channel_queue import horizon as channel_horizon

        touched = list({price.room_type_id for price in request.prices})
        await enqueue_channels(
            session,
            context,
            property_id,
            touched,
            channel_horizon(property_today(prop.timezone), 366),
        )
    await session.commit()
    log.info("Rate plan updated rate_plan=%s", plan.id)
    return (await _read_many(session, context, [plan]))[0]
