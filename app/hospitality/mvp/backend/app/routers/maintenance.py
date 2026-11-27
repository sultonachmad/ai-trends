"""Repair requests.

GET  /api/maintenance                      open requests and the last two weeks' (view)
POST /api/maintenance                      report one, with an optional photo (edit)
GET  /api/maintenance/{id}/photo           the photo (view)
POST /api/maintenance/{id}/start|wait|fix  work it (edit: the person it is given to, or
                                           anyone while nobody has it; supervisors always)
POST /api/maintenance/{id}/assign|cancel   supervisors (manage)
POST /api/maintenance/{id}/off-sale        take its room off sale for some nights (manage)
POST /api/maintenance/{id}/on-sale         put it back (manage)

Every action answers with the fresh board.
"""

from collections.abc import Awaitable, Callable
from typing import Annotated, Any, TypeVar
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile
from sqlmodel.ext.asyncio.session import AsyncSession

from app.database import get_session
from app.documents.storage import DocumentStorage, get_document_storage
from app.rbac.dependencies import _user_has_permission, require_permission
from app.schemas.maintenance import (
    AssignRequest,
    CancelRequest,
    Category,
    FixRequest,
    MaintBoard,
    OffSaleRequest,
    Text80,
    Text300,
    WaitRequest,
)
from app.services import maintenance, maintenance_blocks, maintenance_reads
from app.services.front_desk_errors import FrontDeskError
from app.services.workspace import find_property
from app.tenancy.business_settings import MAX_PROOF_UPLOAD_MB
from app.tenancy.context import TenantContext, get_tenant_context
from app.tenancy.session import get_tenant_session

VIEW = require_permission("maintenance:view", "See repair requests and rooms off sale")
EDIT = require_permission("maintenance:edit", "Report repairs and work the ones given to you")
MANAGE = require_permission(
    "maintenance:manage", "Give repairs to people, cancel them and take rooms off sale"
)
MANAGE_CODE = "maintenance:manage"
BYTES_PER_MB = 1024 * 1024
NO_STORE = {"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"}

T = TypeVar("T")

maintenance_router = APIRouter(prefix="/api/maintenance", tags=["maintenance"])


def _refused(exc: FrontDeskError) -> HTTPException:
    detail: dict = {"code": exc.code, "message": exc.message}
    if exc.rooms:
        detail["items"] = exc.rooms  # booking numbers or nights that stand in the way
    return HTTPException(status_code=exc.status_code, detail=detail)


async def _guarded(session: AsyncSession, call: Callable[[], Awaitable[T]]) -> T:
    try:
        return await call()
    except FrontDeskError as exc:
        await session.rollback()
        raise _refused(exc) from None


async def _then_board(
    session: AsyncSession, context: TenantContext, action: Callable[[Any], Awaitable[Any]]
) -> MaintBoard:
    prop = await find_property(session, context)
    await _guarded(session, lambda: action(prop))
    return await maintenance_reads.read_board(session, context, prop)


async def _can_manage(user: dict, rbac_session: AsyncSession) -> bool:
    return await _user_has_permission(int(user["user_id"]), MANAGE_CODE, rbac_session)


@maintenance_router.get("", response_model=MaintBoard)
async def board(
    context: TenantContext = Depends(get_tenant_context),
    session: AsyncSession = Depends(get_tenant_session),
    _view=VIEW,
) -> MaintBoard:
    prop = await find_property(session, context)
    await maintenance_blocks.refresh_blocks(session, context, prop)
    return await maintenance_reads.read_board(session, context, prop)


@maintenance_router.post("", response_model=MaintBoard)
async def report(
    category: Annotated[Category, Form()],
    description: Annotated[Text300, Form()],
    urgent: Annotated[bool, Form()] = False,
    unit_id: Annotated[UUID | None, Form()] = None,
    place: Annotated[Text80 | None, Form()] = None,
    photo: Annotated[UploadFile | None, File()] = None,
    context: TenantContext = Depends(get_tenant_context),
    session: AsyncSession = Depends(get_tenant_session),
    storage: DocumentStorage = Depends(get_document_storage),
    _edit=EDIT,
) -> MaintBoard:
    content = await photo.read(MAX_PROOF_UPLOAD_MB * BYTES_PER_MB + 1) if photo else b""

    async def run(prop: Any) -> None:
        document = None
        if content:
            document = await maintenance_reads.store_photo(session, storage, context, prop, content)
        try:
            await maintenance.report(
                session,
                context,
                prop,
                unit_id=unit_id,
                place=place,
                category=category,
                urgent=urgent,
                description=description,
                photo_id=document.id if document else None,
            )
        except Exception:
            if document is not None:  # the request was not saved: neither is its photo
                await maintenance_reads.discard_photo(storage, context, document.storage_key)
            raise

    return await _then_board(session, context, run)


@maintenance_router.get("/{order_id}/photo")
async def photo(
    order_id: UUID,
    context: TenantContext = Depends(get_tenant_context),
    session: AsyncSession = Depends(get_tenant_session),
    storage: DocumentStorage = Depends(get_document_storage),
    _view=VIEW,
) -> Response:
    prop = await find_property(session, context)
    content, media_type = await _guarded(
        session, lambda: maintenance_reads.read_photo(session, storage, context, prop, order_id)
    )
    return Response(content=content, media_type=media_type, headers=NO_STORE)


@maintenance_router.post("/{order_id}/start", response_model=MaintBoard)
async def start(
    order_id: UUID,
    context: TenantContext = Depends(get_tenant_context),
    session: AsyncSession = Depends(get_tenant_session),
    rbac_session: AsyncSession = Depends(get_session, use_cache=False),
    user=EDIT,
) -> MaintBoard:
    manage = await _can_manage(user, rbac_session)
    return await _then_board(
        session, context, lambda prop: maintenance.start(session, context, prop, order_id, manage)
    )


@maintenance_router.post("/{order_id}/wait", response_model=MaintBoard)
async def wait(
    order_id: UUID,
    body: WaitRequest,
    context: TenantContext = Depends(get_tenant_context),
    session: AsyncSession = Depends(get_tenant_session),
    rbac_session: AsyncSession = Depends(get_session, use_cache=False),
    user=EDIT,
) -> MaintBoard:
    manage = await _can_manage(user, rbac_session)
    return await _then_board(
        session,
        context,
        lambda prop: maintenance.wait(session, context, prop, order_id, body.note, manage),
    )


@maintenance_router.post("/{order_id}/fix", response_model=MaintBoard)
async def fix(
    order_id: UUID,
    body: FixRequest,
    context: TenantContext = Depends(get_tenant_context),
    session: AsyncSession = Depends(get_tenant_session),
    rbac_session: AsyncSession = Depends(get_session, use_cache=False),
    user=EDIT,
) -> MaintBoard:
    manage = await _can_manage(user, rbac_session)
    return await _then_board(
        session,
        context,
        lambda prop: maintenance.fix(
            session, context, prop, order_id, note=body.note, cost=body.cost, can_manage=manage
        ),
    )


@maintenance_router.post("/{order_id}/assign", response_model=MaintBoard)
async def assign(
    order_id: UUID,
    body: AssignRequest,
    context: TenantContext = Depends(get_tenant_context),
    session: AsyncSession = Depends(get_tenant_session),
    _manage=MANAGE,
) -> MaintBoard:
    return await _then_board(
        session,
        context,
        lambda prop: maintenance.assign(
            session, context, prop, order_id, staff_id=body.staff_id, vendor_name=body.vendor_name
        ),
    )


@maintenance_router.post("/{order_id}/cancel", response_model=MaintBoard)
async def cancel(
    order_id: UUID,
    body: CancelRequest,
    context: TenantContext = Depends(get_tenant_context),
    session: AsyncSession = Depends(get_tenant_session),
    _manage=MANAGE,
) -> MaintBoard:
    return await _then_board(
        session,
        context,
        lambda prop: maintenance.cancel(session, context, prop, order_id, body.reason),
    )


@maintenance_router.post("/{order_id}/off-sale", response_model=MaintBoard)
async def off_sale(
    order_id: UUID,
    body: OffSaleRequest,
    context: TenantContext = Depends(get_tenant_context),
    session: AsyncSession = Depends(get_tenant_session),
    _manage=MANAGE,
) -> MaintBoard:
    return await _then_board(
        session,
        context,
        lambda prop: maintenance_blocks.off_sale(
            session, context, prop, order_id, body.first_night, body.last_night
        ),
    )


@maintenance_router.post("/{order_id}/on-sale", response_model=MaintBoard)
async def on_sale(
    order_id: UUID,
    context: TenantContext = Depends(get_tenant_context),
    session: AsyncSession = Depends(get_tenant_session),
    _manage=MANAGE,
) -> MaintBoard:
    return await _then_board(
        session, context, lambda prop: maintenance_blocks.on_sale(session, context, prop, order_id)
    )
