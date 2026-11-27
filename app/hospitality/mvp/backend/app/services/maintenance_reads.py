"""What staff see of repair requests, the front desk's notices, and request photos."""

import datetime as dt
import logging
from uuid import UUID

from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.documents.images import content_hash, detect_image_type
from app.documents.storage import DocumentStorage
from app.models.tenant import Document, Property, StaffMember, Unit, UnitBlock, WorkOrder
from app.schemas.maintenance import MaintBoard, MaintNotice, MaintRequest, MaintRoom, OffSale
from app.services import calendar_dates as dates_of
from app.services import maintenance_errors as errors
from app.services.maintenance import FROM_HOUSEKEEPING, LIVE, URGENT
from app.services.room_assignment import room_name
from app.services.room_blocks import ACTIVE, nights_of
from app.tenancy.business_settings import resolve_property_settings
from app.tenancy.context import TenantContext

log = logging.getLogger(__name__)

BYTES_PER_MB = 1024 * 1024
DONE_DAYS = 14  # fixed or cancelled requests stay on the list this long
MAX_ROWS = 300
PHOTO_KIND = "photo"


async def _requests(
    session: AsyncSession, context: TenantContext, prop: Property, since: dt.datetime
) -> list[WorkOrder]:
    rows = await session.exec(
        select(WorkOrder)
        .where(
            col(WorkOrder.tenant_id) == context.tenant_id,
            col(WorkOrder.property_id) == prop.id,
            (col(WorkOrder.status).in_(LIVE)) | (col(WorkOrder.updated_at) >= since),
        )
        .order_by(col(WorkOrder.created_at).desc())
        .limit(MAX_ROWS)
    )
    return list(rows.all())


async def _blocks(
    session: AsyncSession, context: TenantContext, order_ids: list[UUID]
) -> dict[UUID, UnitBlock]:
    if not order_ids:
        return {}
    rows = await session.exec(
        select(UnitBlock).where(
            col(UnitBlock.tenant_id) == context.tenant_id,
            col(UnitBlock.work_order_id).in_(order_ids),
            col(UnitBlock.status) == ACTIVE,
        )
    )
    return {block.work_order_id: block for block in rows.all()}


async def _units(session: AsyncSession, context: TenantContext, prop: Property) -> list[Unit]:
    rows = await session.exec(
        select(Unit)
        .where(
            col(Unit.tenant_id) == context.tenant_id,
            col(Unit.property_id) == prop.id,
            col(Unit.is_active).is_(True),
        )
        .order_by(col(Unit.sort_order), col(Unit.code))
    )
    return list(rows.all())


async def _staff(session: AsyncSession, context: TenantContext) -> list[StaffMember]:
    rows = await session.exec(
        select(StaffMember)
        .where(
            col(StaffMember.tenant_id) == context.tenant_id,
            col(StaffMember.status) == "active",
            col(StaffMember.user_id).is_not(None),
        )
        .order_by(col(StaffMember.display_name))
    )
    return list(rows.all())


def _read(
    order: WorkOrder,
    units: dict[UUID, Unit],
    names: dict[UUID, str],
    block: UnitBlock | None,
    context: TenantContext,
    timezone: str,
) -> MaintRequest:
    unit = units.get(order.unit_id) if order.unit_id else None
    off_sale = None
    if block is not None:
        first, last = nights_of(block, timezone)
        off_sale = OffSale(first_night=first, last_night=last)
    return MaintRequest(
        id=order.id,
        number=order.number,
        unit_id=order.unit_id,
        room_name=room_name(unit) if unit else None,
        place=order.place,
        category=order.category,
        urgent=order.priority == URGENT,
        description=order.description or order.title,
        status=order.status,
        status_note=order.status_note,
        reported_by_name=names.get(order.reported_by_staff_id)
        if order.reported_by_staff_id
        else None,
        reported_at=order.created_at,
        from_housekeeping=order.source == FROM_HOUSEKEEPING,
        assigned_staff_id=order.assigned_staff_id,
        assigned_name=names.get(order.assigned_staff_id) if order.assigned_staff_id else None,
        vendor_name=order.vendor_name,
        mine=order.assigned_staff_id is not None
        and order.assigned_staff_id == context.staff_member_id,
        has_photo=bool(order.photo_document_ids),
        off_sale=off_sale,
        cost=order.parts_cost,
        completed_at=order.completed_at,
    )


async def read_board(session: AsyncSession, context: TenantContext, prop: Property) -> MaintBoard:
    since = dt.datetime.now(dt.UTC) - dt.timedelta(days=DONE_DAYS)
    orders = await _requests(session, context, prop, since)
    units = await _units(session, context, prop)
    staff = await _staff(session, context)
    by_unit = {unit.id: unit for unit in units}
    names = {member.id: member.display_name for member in staff}
    names.update(await _names_of(session, context, orders, set(names)))
    blocks = await _blocks(session, context, [order.id for order in orders])
    return MaintBoard(
        today=dates_of.property_today(prop.timezone),
        requests=[
            _read(o, by_unit, names, blocks.get(o.id), context, prop.timezone) for o in orders
        ],
        rooms=[MaintRoom(id=unit.id, name=room_name(unit)) for unit in units],
        staff=[MaintRoom(id=member.id, name=member.display_name) for member in staff],
    )


async def _names_of(
    session: AsyncSession, context: TenantContext, orders: list[WorkOrder], known: set[UUID]
) -> dict[UUID, str]:
    """Names of reporters and assignees who have since left."""
    ids = {
        staff_id
        for order in orders
        for staff_id in (order.reported_by_staff_id, order.assigned_staff_id)
        if staff_id and staff_id not in known
    }
    if not ids:
        return {}
    rows = await session.exec(
        select(StaffMember.id, StaffMember.display_name).where(
            col(StaffMember.tenant_id) == context.tenant_id, col(StaffMember.id).in_(ids)
        )
    )
    return dict(rows.all())


async def notices(
    session: AsyncSession, context: TenantContext, prop: Property
) -> list[MaintNotice]:
    """For the front desk: urgent repairs not yet fixed, and rooms off sale."""
    orders = (
        await session.exec(
            select(WorkOrder).where(
                col(WorkOrder.tenant_id) == context.tenant_id,
                col(WorkOrder.property_id) == prop.id,
                col(WorkOrder.status).in_(LIVE),
            )
        )
    ).all()
    blocks = await _blocks(session, context, [order.id for order in orders])
    shown = [o for o in orders if o.priority == URGENT or o.id in blocks]
    units = {u.id: u for u in await _units(session, context, prop)}
    return [
        MaintNotice(
            id=order.id,
            number=order.number,
            room_name=room_name(units[order.unit_id]) if order.unit_id in units else None,
            place=order.place,
            category=order.category,
            urgent=order.priority == URGENT,
            off_sale_until=nights_of(blocks[order.id], prop.timezone)[1]
            if order.id in blocks
            else None,
        )
        for order in sorted(shown, key=lambda o: o.number)
    ]


async def store_photo(
    session: AsyncSession,
    storage: DocumentStorage,
    context: TenantContext,
    prop: Property,
    content: bytes,
) -> Document:
    """Check and save a repair photo; the caller adds it to the request and commits."""
    limit_mb = resolve_property_settings(prop.settings).id_max_upload_mb
    image = detect_image_type(content) if content else None
    if image is None or len(content) > limit_mb * BYTES_PER_MB:
        raise errors.PhotoError
    key = await storage.save(context.tenant_id, content, image.extension)
    try:
        return await _record_photo(session, context, prop, key, content, image.content_type)
    except Exception:
        await discard_photo(storage, context, key)
        raise


async def discard_photo(storage: DocumentStorage, context: TenantContext, key: str) -> None:
    """Remove a photo whose request was not saved; a failure here must not hide the cause."""
    try:
        await storage.delete(context.tenant_id, key)
    except Exception:
        log.exception("Could not remove an unsaved repair photo key=%s", key)


async def _record_photo(
    session: AsyncSession,
    context: TenantContext,
    prop: Property,
    key: str,
    content: bytes,
    content_type: str,
) -> Document:
    document = Document(
        tenant_id=context.tenant_id,
        property_id=prop.id,
        kind=PHOTO_KIND,
        classification="internal",
        storage_key=key,
        content_type=content_type,
        size_bytes=len(content),
        sha256=content_hash(content),
        uploaded_by=str(context.user_id),
    )
    session.add(document)
    await session.flush()
    return document


async def read_photo(
    session: AsyncSession,
    storage: DocumentStorage,
    context: TenantContext,
    prop: Property,
    order_id: UUID,
) -> tuple[bytes, str]:
    order = (
        await session.exec(
            select(WorkOrder).where(
                col(WorkOrder.tenant_id) == context.tenant_id,
                col(WorkOrder.property_id) == prop.id,
                col(WorkOrder.id) == order_id,
            )
        )
    ).first()
    if order is None or not order.photo_document_ids:
        raise errors.RequestNotFoundError
    document = (
        await session.exec(
            select(Document).where(
                col(Document.tenant_id) == context.tenant_id,
                col(Document.id) == order.photo_document_ids[0],
            )
        )
    ).first()
    if document is None or getattr(document, "purged_at", None) is not None:
        raise errors.RequestNotFoundError
    try:
        return await storage.read(context.tenant_id, document.storage_key), document.content_type
    except FileNotFoundError:
        log.error("Repair photo missing on disk order=%s", order.id)
        raise errors.RequestNotFoundError from None
