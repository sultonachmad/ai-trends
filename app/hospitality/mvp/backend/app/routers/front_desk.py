"""Front desk.

GET  /api/front-desk/today                       arrivals, in-house, departures, rooms
GET  /api/front-desk/bookings/{id}/free-rooms    rooms free for the whole stay
PUT  /api/front-desk/lines/{id}/room             assign, clear or move
PUT  /api/front-desk/lines/{id}/lock             keep the guest in this room
POST /api/front-desk/bookings/{id}/check-in
POST /api/front-desk/bookings/{id}/check-out
POST /api/front-desk/bookings/{id}/no-show
POST /api/front-desk/bookings/{id}/undo          today's action, with a reason
"""

from collections.abc import Awaitable, Callable
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel.ext.asyncio.session import AsyncSession

from app.database import get_session
from app.models.tenant import Property, Reservation
from app.rbac.dependencies import _user_has_permission, require_permission
from app.schemas.front_desk import (
    AssignRoomRequest,
    CheckInRequest,
    CheckOutRequest,
    FreeRoom,
    FrontDeskEntry,
    FrontDeskToday,
    LockRoomRequest,
    UndoRequest,
)
from app.services import calendar_dates as dates_of
from app.services import front_desk as desk
from app.services import front_desk_reads as reads
from app.services import room_assignment as rooms
from app.services.front_desk_errors import (
    FrontDeskError,
    PricePermissionError,
    UnpaidPermissionError,
)
from app.services.guest_id_errors import NoIdPermissionError
from app.services.workspace import find_property
from app.tenancy.context import TenantContext, get_tenant_context
from app.tenancy.session import get_tenant_session

VIEW = require_permission("frontdesk:view", "See arrivals, in-house guests, departures and rooms")

EDIT = require_permission("frontdesk:edit", "Assign rooms and check guests in and out")

BOOKING_EDIT = "bookings:edit"  # lowering a price or waiving payment needs booking rights

front_desk_router = APIRouter(prefix="/api/front-desk", tags=["front-desk"])


async def _answer(
    session: AsyncSession,
    context: TenantContext,
    prop: Property,
    call: Callable[[], Awaitable[Reservation]],
) -> FrontDeskEntry:
    """Run an action and answer with the booking as the desk now sees it."""
    timezone = prop.timezone
    try:
        booking = await call()
    except FrontDeskError as exc:
        await session.rollback()
        raise HTTPException(
            status_code=exc.status_code,
            detail={"code": exc.code, "message": exc.message, "rooms": exc.rooms},
        ) from None
    today = dates_of.property_today(timezone)
    [entry] = await reads.read_entries(session, context, [booking], today, timezone)
    return entry


@front_desk_router.get("/today", response_model=FrontDeskToday)
async def today(
    context: TenantContext = Depends(get_tenant_context),
    session: AsyncSession = Depends(get_tenant_session),
    _view=VIEW,
) -> FrontDeskToday:
    prop = await find_property(session, context)
    return await reads.read_today(session, context, prop)


@front_desk_router.get("/bookings/{booking_id}/free-rooms", response_model=list[FreeRoom])
async def free_rooms(
    booking_id: UUID,
    context: TenantContext = Depends(get_tenant_context),
    session: AsyncSession = Depends(get_tenant_session),
    _view=VIEW,
) -> list[FreeRoom]:
    prop = await find_property(session, context)
    try:
        return await rooms.free_rooms(session, context, prop, booking_id)
    except FrontDeskError as exc:
        raise HTTPException(
            status_code=exc.status_code, detail={"code": exc.code, "message": exc.message}
        ) from None


@front_desk_router.put("/lines/{line_id}/room", response_model=FrontDeskEntry)
async def assign_room(
    line_id: UUID,
    body: AssignRoomRequest,
    context: TenantContext = Depends(get_tenant_context),
    session: AsyncSession = Depends(get_tenant_session),
    _edit=EDIT,
) -> FrontDeskEntry:
    prop = await find_property(session, context)
    return await _answer(
        session, context, prop, lambda: rooms.assign_room(session, context, prop, line_id, body)
    )


@front_desk_router.put("/lines/{line_id}/lock", response_model=FrontDeskEntry)
async def lock_room(
    line_id: UUID,
    body: LockRoomRequest,
    context: TenantContext = Depends(get_tenant_context),
    session: AsyncSession = Depends(get_tenant_session),
    _edit=EDIT,
) -> FrontDeskEntry:
    prop = await find_property(session, context)
    return await _answer(
        session,
        context,
        prop,
        lambda: rooms.lock_room(session, context, prop, line_id, body.locked),
    )


@front_desk_router.post("/bookings/{booking_id}/check-in", response_model=FrontDeskEntry)
async def check_in(
    booking_id: UUID,
    body: CheckInRequest,
    context: TenantContext = Depends(get_tenant_context),
    session: AsyncSession = Depends(get_tenant_session),
    rbac_session: AsyncSession = Depends(get_session, use_cache=False),
    user: dict = EDIT,
) -> FrontDeskEntry:
    if body.no_id_reason is not None and not await _user_has_permission(
        int(user["user_id"]), BOOKING_EDIT, rbac_session
    ):
        exc = NoIdPermissionError()
        raise HTTPException(
            status_code=exc.status_code, detail={"code": exc.code, "message": exc.message}
        )
    prop = await find_property(session, context)
    return await _answer(
        session, context, prop, lambda: desk.check_in(session, context, prop, booking_id, body)
    )


@front_desk_router.post("/bookings/{booking_id}/check-out", response_model=FrontDeskEntry)
async def check_out(
    booking_id: UUID,
    body: CheckOutRequest,
    context: TenantContext = Depends(get_tenant_context),
    session: AsyncSession = Depends(get_tenant_session),
    rbac_session: AsyncSession = Depends(get_session, use_cache=False),
    user: dict = EDIT,
) -> FrontDeskEntry:
    needs = [
        error
        for wanted, error in (
            (body.early == "nights_stayed", PricePermissionError),
            (body.leave_unpaid_reason is not None, UnpaidPermissionError),
        )
        if wanted
    ]
    if needs and not await _user_has_permission(int(user["user_id"]), BOOKING_EDIT, rbac_session):
        exc = needs[0]()
        raise HTTPException(
            status_code=exc.status_code, detail={"code": exc.code, "message": exc.message}
        )
    prop = await find_property(session, context)
    return await _answer(
        session, context, prop, lambda: desk.check_out(session, context, prop, booking_id, body)
    )


@front_desk_router.post("/bookings/{booking_id}/no-show", response_model=FrontDeskEntry)
async def no_show(
    booking_id: UUID,
    context: TenantContext = Depends(get_tenant_context),
    session: AsyncSession = Depends(get_tenant_session),
    _edit=EDIT,
) -> FrontDeskEntry:
    prop = await find_property(session, context)
    return await _answer(
        session, context, prop, lambda: desk.mark_no_show(session, context, prop, booking_id)
    )


@front_desk_router.post("/bookings/{booking_id}/undo", response_model=FrontDeskEntry)
async def undo(
    booking_id: UUID,
    body: UndoRequest,
    context: TenantContext = Depends(get_tenant_context),
    session: AsyncSession = Depends(get_tenant_session),
    _edit=EDIT,
) -> FrontDeskEntry:
    prop = await find_property(session, context)
    return await _answer(
        session, context, prop, lambda: desk.undo(session, context, prop, booking_id, body)
    )
