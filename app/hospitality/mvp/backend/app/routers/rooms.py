"""Room type routes.

GET   /api/room-types
POST  /api/room-types
PATCH /api/room-types/{id}
PATCH /api/room-types/{id}/units/{unit_id}      rename one unit
"""

from collections.abc import Awaitable, Callable
from typing import TypeVar
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel.ext.asyncio.session import AsyncSession

from app.schemas.rooms import (
    RoomTypeCreateRequest,
    RoomTypeRead,
    RoomTypeUpdateRequest,
    UnitRenameRequest,
)
from app.services import room_types as rooms
from app.services.workspace import find_property
from app.tenancy.context import TenantContext, get_tenant_context
from app.tenancy.session import get_tenant_session

rooms_router = APIRouter(prefix="/api/room-types", tags=["room-types"])

NOT_FOUND = "Room type not found"
T = TypeVar("T")


async def _guarded(call: Callable[[], Awaitable[T]]) -> T:
    """Run a room-type service call, turning its domain errors into HTTP answers."""
    try:
        return await call()
    except rooms.RoomTypeNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=NOT_FOUND) from None
    except rooms.UnitNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Unit not found"
        ) from None
    except rooms.RoomTypeNameTakenError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A room type with this name already exists.",
        ) from None
    except rooms.RoomTypeLimitError as exc:
        noun = "room type" if exc.limit == 1 else "room types"
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"A property can have at most {exc.limit} {noun} in use.",
        ) from None
    except rooms.TooManySwitchedOffError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Too many switched-off room types. Switch one back on and change it instead.",
        ) from None
    except rooms.TooManyUnitsError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"A room type can have at most {exc.limit} units.",
        ) from None


@rooms_router.get("", response_model=list[RoomTypeRead])
async def list_room_types(
    context: TenantContext = Depends(get_tenant_context),
    session: AsyncSession = Depends(get_tenant_session),
) -> list[RoomTypeRead]:
    prop = await find_property(session, context)
    return await rooms.list_room_types(session, context, prop.id)


@rooms_router.post("", response_model=RoomTypeRead, status_code=status.HTTP_201_CREATED)
async def create_room_type(
    body: RoomTypeCreateRequest,
    context: TenantContext = Depends(get_tenant_context),
    session: AsyncSession = Depends(get_tenant_session),
) -> RoomTypeRead:
    prop = await find_property(session, context)
    return await _guarded(lambda: rooms.create_room_type(session, context, prop, body))


@rooms_router.patch("/{room_type_id}", response_model=RoomTypeRead)
async def update_room_type(
    room_type_id: UUID,
    body: RoomTypeUpdateRequest,
    context: TenantContext = Depends(get_tenant_context),
    session: AsyncSession = Depends(get_tenant_session),
) -> RoomTypeRead:
    prop = await find_property(session, context)
    return await _guarded(
        lambda: rooms.update_room_type(session, context, prop, room_type_id, body)
    )


@rooms_router.patch("/{room_type_id}/units/{unit_id}", response_model=RoomTypeRead)
async def rename_unit(
    room_type_id: UUID,
    unit_id: UUID,
    body: UnitRenameRequest,
    context: TenantContext = Depends(get_tenant_context),
    session: AsyncSession = Depends(get_tenant_session),
) -> RoomTypeRead:
    prop = await find_property(session, context)
    return await _guarded(
        lambda: rooms.rename_unit(session, context, prop.id, room_type_id, unit_id, body.name)
    )
