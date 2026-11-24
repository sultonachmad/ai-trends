"""Guest bills.

GET  /api/bills/{booking_id}                     the bill
POST /api/bills/{booking_id}/charges             an extra
POST /api/bills/{booking_id}/discounts           money off, with a reason
POST /api/bills/{booking_id}/corrections         an earlier day's mistake, with a reason
POST /api/bills/{booking_id}/lines/{id}/void     cancel one of today's lines
POST /api/bills/{booking_id}/payments            money received at the desk
GET  /api/bills/receipts/{receipt_id}            a receipt, as issued
"""

from collections.abc import Awaitable, Callable
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel.ext.asyncio.session import AsyncSession

from app.database import get_session
from app.models.tenant import Property, Reservation
from app.rbac.dependencies import _user_has_permission, require_permission
from app.schemas.bills import (
    BillRead,
    ChargeRequest,
    CorrectionRequest,
    DiscountRequest,
    ReceiptRead,
    VoidRequest,
)
from app.schemas.bookings import PaymentRecordRequest
from app.services import bill_reads, bills, receipts
from app.services import booking_payments as payments
from app.services import bookings as booking_service
from app.services.front_desk_errors import FrontDeskError, PricePermissionError
from app.services.workspace import find_property
from app.tenancy.context import TenantContext, get_tenant_context
from app.tenancy.session import get_tenant_session

VIEW = require_permission("bills:view", "See guest bills and receipts")

EDIT = require_permission("bills:edit", "Add charges, discounts and payments to guest bills")

BOOKING_EDIT = "bookings:edit"  # discounts and corrections change the price

bills_router = APIRouter(prefix="/api/bills", tags=["bills"])


async def _may_change_price(user: dict, rbac_session: AsyncSession) -> None:
    if not await _user_has_permission(int(user["user_id"]), BOOKING_EDIT, rbac_session):
        raise _refused(PricePermissionError())


_PAYMENT_ERRORS: dict[type[Exception], tuple[int, str]] = {
    booking_service.BookingNotFoundError: (status.HTTP_404_NOT_FOUND, "Booking not found"),
    booking_service.BookingHeldError: (
        status.HTTP_409_CONFLICT,
        "This booking is waiting for the guest's online payment.",
    ),
    payments.PaymentDateError: (
        status.HTTP_422_UNPROCESSABLE_ENTITY,
        "The date received must be today or earlier, within the last year.",
    ),
    payments.TooManyPaymentsError: (
        status.HTTP_409_CONFLICT,
        "This booking has too many payment entries. Remove wrong ones first.",
    ),
}


def _refused(exc: FrontDeskError) -> HTTPException:
    return HTTPException(
        status_code=exc.status_code, detail={"code": exc.code, "message": exc.message}
    )


async def _bill(session: AsyncSession, context: TenantContext, prop: Property, booking_id: UUID):
    try:
        return await bill_reads.read_bill(session, context, prop, booking_id)
    except FrontDeskError as exc:
        raise _refused(exc) from None


async def _change(
    session: AsyncSession,
    context: TenantContext,
    prop: Property,
    booking_id: UUID,
    call: Callable[[], Awaitable[Reservation]],
) -> BillRead:
    try:
        await call()
    except FrontDeskError as exc:
        await session.rollback()
        raise _refused(exc) from None
    except tuple(_PAYMENT_ERRORS) as exc:
        await session.rollback()
        code, detail = _PAYMENT_ERRORS[type(exc)]
        raise HTTPException(status_code=code, detail=detail) from None
    return await _bill(session, context, prop, booking_id)


@bills_router.get("/receipts/{receipt_id}", response_model=ReceiptRead)
async def read_receipt(
    receipt_id: UUID,
    context: TenantContext = Depends(get_tenant_context),
    session: AsyncSession = Depends(get_tenant_session),
    _view=VIEW,
) -> ReceiptRead:
    prop = await find_property(session, context)
    try:
        return await receipts.read_receipt(session, context, prop, receipt_id)
    except FrontDeskError as exc:
        raise _refused(exc) from None


@bills_router.get("/{booking_id}", response_model=BillRead)
async def read_bill(
    booking_id: UUID,
    context: TenantContext = Depends(get_tenant_context),
    session: AsyncSession = Depends(get_tenant_session),
    _view=VIEW,
) -> BillRead:
    prop = await find_property(session, context)
    return await _bill(session, context, prop, booking_id)


@bills_router.post("/{booking_id}/charges", response_model=BillRead)
async def post_charge(
    booking_id: UUID,
    body: ChargeRequest,
    context: TenantContext = Depends(get_tenant_context),
    session: AsyncSession = Depends(get_tenant_session),
    _edit=EDIT,
) -> BillRead:
    prop = await find_property(session, context)
    return await _change(
        session,
        context,
        prop,
        booking_id,
        lambda: bills.post_charge(session, context, prop, booking_id, body),
    )


@bills_router.post("/{booking_id}/discounts", response_model=BillRead)
async def give_discount(
    booking_id: UUID,
    body: DiscountRequest,
    context: TenantContext = Depends(get_tenant_context),
    session: AsyncSession = Depends(get_tenant_session),
    rbac_session: AsyncSession = Depends(get_session, use_cache=False),
    user: dict = EDIT,
) -> BillRead:
    await _may_change_price(user, rbac_session)
    prop = await find_property(session, context)
    return await _change(
        session,
        context,
        prop,
        booking_id,
        lambda: bills.give_discount(session, context, prop, booking_id, body),
    )


@bills_router.post("/{booking_id}/corrections", response_model=BillRead)
async def correct(
    booking_id: UUID,
    body: CorrectionRequest,
    context: TenantContext = Depends(get_tenant_context),
    session: AsyncSession = Depends(get_tenant_session),
    rbac_session: AsyncSession = Depends(get_session, use_cache=False),
    user: dict = EDIT,
) -> BillRead:
    await _may_change_price(user, rbac_session)
    prop = await find_property(session, context)
    return await _change(
        session,
        context,
        prop,
        booking_id,
        lambda: bills.correct(session, context, prop, booking_id, body),
    )


@bills_router.post("/{booking_id}/lines/{line_id}/void", response_model=BillRead)
async def void_line(
    booking_id: UUID,
    line_id: UUID,
    body: VoidRequest,
    context: TenantContext = Depends(get_tenant_context),
    session: AsyncSession = Depends(get_tenant_session),
    _edit=EDIT,
) -> BillRead:
    prop = await find_property(session, context)
    return await _change(
        session,
        context,
        prop,
        booking_id,
        lambda: bills.void_line(session, context, prop, booking_id, line_id, body),
    )


@bills_router.post("/{booking_id}/payments", response_model=BillRead)
async def record_payment(
    booking_id: UUID,
    body: PaymentRecordRequest,
    context: TenantContext = Depends(get_tenant_context),
    session: AsyncSession = Depends(get_tenant_session),
    _edit=EDIT,
) -> BillRead:
    prop = await find_property(session, context)
    return await _change(
        session,
        context,
        prop,
        booking_id,
        lambda: payments.record_payment(session, context, prop, booking_id, body),
    )
