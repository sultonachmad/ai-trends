"""The owner's setup of the public booking page: its name, publishing, what is sold."""

import logging

from sqlalchemy.exc import IntegrityError
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.tenant import BookingPage, Property, RatePlan
from app.schemas.booking_page import BookingPagePlan, BookingPageSaveRequest, BookingPageSetup
from app.services import tenant_audit
from app.services.bookings import lock_property
from app.tenancy.context import TenantContext

log = logging.getLogger(__name__)

ENTITY = "bookingpage"
ACTIVE = "active"
RESERVED_SLUGS = frozenset(
    {"admin", "api", "app", "book", "booking", "bookings", "help", "login", "pay", "support", "www"}
)


class SlugTakenError(Exception):
    """Another property already uses this page name (or it is reserved)."""


class NothingToSellError(Exception):
    """A page cannot be published with no rate plan on sale."""


class UnknownPlanError(Exception):
    """A plan in the request is not an active plan of this property."""


async def _page(
    session: AsyncSession, context: TenantContext, prop: Property
) -> BookingPage | None:
    return (
        await session.exec(
            select(BookingPage).where(
                col(BookingPage.tenant_id) == context.tenant_id,
                col(BookingPage.property_id) == prop.id,
            )
        )
    ).first()


async def _plans(session: AsyncSession, context: TenantContext, prop: Property) -> list[RatePlan]:
    rows = await session.exec(
        select(RatePlan)
        .where(
            col(RatePlan.tenant_id) == context.tenant_id,
            col(RatePlan.property_id) == prop.id,
            col(RatePlan.status) == ACTIVE,
        )
        .order_by(col(RatePlan.sort_order), col(RatePlan.name))
        .execution_options(populate_existing=True)
    )
    return list(rows.all())


async def read_setup(
    session: AsyncSession, context: TenantContext, prop: Property
) -> BookingPageSetup:
    page = await _page(session, context, prop)
    plans = await _plans(session, context, prop)
    return BookingPageSetup(
        slug=page.slug if page else None,
        is_published=bool(page and page.is_published),
        plans=[BookingPagePlan(id=p.id, name=p.name, sold=p.is_public) for p in plans],
    )


async def save_setup(
    session: AsyncSession,
    context: TenantContext,
    prop: Property,
    request: BookingPageSaveRequest,
) -> BookingPageSetup:
    """Save the name, what is sold and whether the page is live. Commits."""
    if request.slug in RESERVED_SLUGS:
        raise SlugTakenError
    property_id = prop.id
    await lock_property(session, context, property_id)
    plans = await _plans(session, context, prop)
    known = {plan.id for plan in plans}
    wanted = set(request.sold_plan_ids)
    if wanted - known:
        await session.rollback()
        raise UnknownPlanError
    if request.is_published and not wanted:
        await session.rollback()
        raise NothingToSellError
    for plan in plans:
        plan.is_public = plan.id in wanted
        session.add(plan)
    page = await _page(session, context, prop)
    if page is None:
        page = BookingPage(
            tenant_id=context.tenant_id,
            property_id=property_id,
            slug=request.slug,
            created_by=str(context.user_id),
        )
    page.slug = request.slug
    page.is_published = request.is_published
    page.updated_by = str(context.user_id)
    session.add(page)
    try:
        await session.flush()
    except IntegrityError:
        await session.rollback()
        raise SlugTakenError from None
    await tenant_audit.record(
        session,
        context,
        "booking_page.saved",
        property_id=property_id,
        entity_table=ENTITY,
        entity_id=page.id,
        payload={"slug": request.slug, "published": request.is_published},
    )
    await session.commit()
    log.info("Booking page saved property=%s published=%s", property_id, request.is_published)
    return await read_setup(session, context, prop)
