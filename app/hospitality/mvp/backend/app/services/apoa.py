"""Recording what staff did in APOA: checked in, checked out, not required, undone.

Staff submit in the official APOA app; here they record that they did, with an optional
APOA receipt reference. Each mark stores what was reported (never the full number) and
goes into the booking's history. Writes lock the property, then the booking, like every
other booking change.
"""

import datetime as dt
import logging
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.tenant import (
    ForeignGuestReport,
    Guest,
    GuestDocument,
    Property,
    ReservationGuest,
)
from app.schemas.apoa import MarkRequest, ReasonRequest
from app.services import apoa_errors as errors
from app.services import calendar_dates as dates_of
from app.services import tenant_audit
from app.services.apoa_reads import (
    APOA,
    ARRIVAL,
    DEPARTURE,
    DONE,
    NOT_REQUIRED,
    PENDING,
    SUBMITTED,
    Stay,
    is_foreign,
    load_stays,
    reports_of,
)
from app.services.bookings import BookingNotFoundError, get_for_update, lock_property
from app.services.front_desk_errors import NotFoundError
from app.services.guest_id_reads import documents_of
from app.services.stay_status import CHECKED_OUT, IN_HOUSE
from app.tenancy.business_settings import resolve_property_settings
from app.tenancy.context import TenantContext

log = logging.getLogger(__name__)

ENTITY = "reservation"
MANUAL = "manual"  # staff submit in the APOA app themselves


@dataclass(frozen=True)
class _Target:
    stay: Stay
    guest: Guest
    document: GuestDocument
    report: ForeignGuestReport | None
    other: ForeignGuestReport | None  # the report of the other step
    link: ReservationGuest | None  # the guest's row on this booking, if any
    links: list[ReservationGuest]  # every guest row on this booking


async def _locked_stay(
    session: AsyncSession, context: TenantContext, prop: Property, booking_id: UUID
) -> Stay:
    await lock_property(session, context, prop.id)
    try:
        booking = await get_for_update(session, context, prop.id, booking_id)
    except BookingNotFoundError:
        raise NotFoundError from None
    [stay] = await load_stays(session, context, [booking])
    return stay


async def _links(
    session: AsyncSession, context: TenantContext, stay: Stay
) -> list[ReservationGuest]:
    """The booking's guest rows, primary first, then oldest: the same order every time."""
    return list(
        (
            await session.exec(
                select(ReservationGuest)
                .where(
                    col(ReservationGuest.tenant_id) == context.tenant_id,
                    col(ReservationGuest.reservation_unit_id).in_([ln.id for ln in stay.lines]),
                )
                .order_by(
                    col(ReservationGuest.is_primary).desc(),
                    col(ReservationGuest.created_at),
                    col(ReservationGuest.id),
                )
            )
        ).all()
    )


async def _new_link(
    session: AsyncSession, context: TenantContext, stay: Stay, guest_id: UUID, rows: list
) -> ReservationGuest:
    """A row for a returning booker who has none on this booking yet (made only on a mark)."""
    link = ReservationGuest(
        tenant_id=context.tenant_id,
        reservation_unit_id=stay.lines[0].id,
        guest_id=guest_id,
        is_primary=guest_id == stay.booking.booker_guest_id
        and not any(row.is_primary for row in rows),
        registration_status="registered",
        created_by=str(context.user_id),
    )
    session.add(link)
    await session.flush()
    return link


async def _report(
    session: AsyncSession, context: TenantContext, link_id: UUID | None, step: str
) -> ForeignGuestReport | None:
    if link_id is None:
        return None
    return (
        await session.exec(
            select(ForeignGuestReport)
            .where(
                col(ForeignGuestReport.tenant_id) == context.tenant_id,
                col(ForeignGuestReport.reservation_guest_id) == link_id,
                col(ForeignGuestReport.report_system) == APOA,
                col(ForeignGuestReport.report_kind) == step,
            )
            .with_for_update()
            .execution_options(populate_existing=True)
        )
    ).first()


async def _guest(session: AsyncSession, context: TenantContext, guest_id: UUID) -> Guest:
    guest = (
        await session.exec(
            select(Guest).where(
                col(Guest.tenant_id) == context.tenant_id, col(Guest.id) == guest_id
            )
        )
    ).first()
    if guest is None:
        raise errors.NotOnBookingError
    return guest


async def _target(
    session: AsyncSession,
    context: TenantContext,
    prop: Property,
    request: MarkRequest | ReasonRequest,
) -> _Target:
    """What the request is about. Reads only: nothing is written here."""
    stay = await _locked_stay(session, context, prop, request.booking_id)
    if request.guest_id not in stay.guest_ids or not stay.lines:
        raise errors.NotOnBookingError
    today = dates_of.property_today(prop.timezone)
    document = (await documents_of(session, context, [request.guest_id], today)).get(
        request.guest_id
    )
    if document is None or not is_foreign(document):
        raise errors.NotForeignError
    rows = await _links(session, context, stay)
    link = next((row for row in rows if row.guest_id == request.guest_id), None)
    link_id = link.id if link else None
    other = DEPARTURE if request.step == ARRIVAL else ARRIVAL
    return _Target(
        stay=stay,
        guest=await _guest(session, context, request.guest_id),
        document=document,
        report=await _report(session, context, link_id, request.step),
        other=await _report(session, context, link_id, other),
        link=link,
        links=rows,
    )


def _check_order(target: _Target, step: str) -> None:
    booking = target.stay.booking
    if booking.status not in (IN_HOUSE, CHECKED_OUT) or target.stay.checked_in_at is None:
        raise errors.NotCheckedInError
    if target.report is not None and target.report.status in DONE:
        raise errors.AlreadyMarkedError
    if step == DEPARTURE:
        if booking.status != CHECKED_OUT:
            raise errors.NotCheckedOutError
        if target.other is not None and target.other.status == NOT_REQUIRED:
            raise errors.ArrivalSkippedError
        if target.other is None or target.other.status != SUBMITTED:
            raise errors.ArrivalFirstError


def _snapshot(target: _Target) -> dict:
    """What was reported, as the property saw it. Never the full number."""
    document, stay = target.document, target.stay
    return {
        "full_name": target.guest.full_name,
        "nationality": document.issuing_country,
        "doc_type": document.doc_type,
        "last4": document.doc_number_last4,
        "visa_type": document.visa_type,
        "entry_date": document.entry_stamp_date.isoformat() if document.entry_stamp_date else None,
        "arrival_date": stay.booking.arrival_date.isoformat(),
        "departure_date": stay.booking.departure_date.isoformat(),
    }


def _due(target: _Target, step: str, prop: Property) -> dt.datetime:
    hours = resolve_property_settings(prop.settings).apoa_deadline_hours
    start = target.stay.checked_out_at if step == DEPARTURE else target.stay.checked_in_at
    return (start or dt.datetime.now(dt.UTC)) + dt.timedelta(hours=hours)


async def _save(
    session: AsyncSession,
    context: TenantContext,
    target: _Target,
    report: ForeignGuestReport,
    event: str,
    detail: dict,
) -> None:
    session.add(report)
    await tenant_audit.record(
        session,
        context,
        event,
        property_id=target.stay.booking.property_id,
        entity_table=ENTITY,
        entity_id=target.stay.booking.id,
        payload={"guest_id": str(target.guest.id), "step": report.report_kind, **detail},
    )
    try:
        await session.commit()
    except IntegrityError:  # two marks of the same step at the same moment
        await session.rollback()
        raise errors.AlreadyMarkedError from None
    log.info("%s booking=%s guest=%s", event, target.stay.booking.id, target.guest.id)


async def _close_step(
    session: AsyncSession,
    context: TenantContext,
    prop: Property,
    request: MarkRequest | ReasonRequest,
    status: str,
) -> tuple[_Target, ForeignGuestReport]:
    """Check the order first; only then add the guest's row and the report."""
    target = await _target(session, context, prop, request)
    _check_order(target, request.step)
    link = target.link or await _new_link(
        session, context, target.stay, target.guest.id, target.links
    )
    report = target.report or ForeignGuestReport(
        tenant_id=context.tenant_id,
        property_id=prop.id,
        reservation_guest_id=link.id,
        guest_id=target.guest.id,
        report_system=APOA,
        report_kind=request.step,
        created_by=str(context.user_id),
    )
    report.due_at = _due(target, request.step, prop)  # from today's check-in or check-out
    report.status, report.method = status, MANUAL
    report.submitted_at = dt.datetime.now(dt.UTC)
    report.submitted_by = str(context.user_id)
    report.guest_document_id = target.document.id
    report.updated_by = str(context.user_id)
    return target, report


async def mark(
    session: AsyncSession, context: TenantContext, prop: Property, request: MarkRequest
) -> None:
    """Staff checked the guest in to (or out of) APOA. Commits."""
    target, report = await _close_step(session, context, prop, request, SUBMITTED)
    report.external_reference = request.reference
    report.payload = _snapshot(target)
    await _save(session, context, target, report, "apoa.marked", {"reference": request.reference})


async def not_required(
    session: AsyncSession, context: TenantContext, prop: Property, request: ReasonRequest
) -> None:
    """This step does not apply to this guest, and why. Commits."""
    target, report = await _close_step(session, context, prop, request, NOT_REQUIRED)
    report.external_reference = None
    report.payload = {**_snapshot(target), "reason": request.reason}
    await _save(session, context, target, report, "apoa.not_required", {"reason": request.reason})


async def undo(
    session: AsyncSession, context: TenantContext, prop: Property, request: ReasonRequest
) -> None:
    """Take back a mark, with a reason. The history keeps both. Commits."""
    target = await _target(session, context, prop, request)
    report = target.report
    if report is None or report.status not in DONE:
        raise errors.NotMarkedError
    if request.step == ARRIVAL and target.other is not None and target.other.status in DONE:
        raise errors.DepartureFirstError
    report.status = PENDING
    report.submitted_at = report.submitted_by = report.external_reference = None
    report.payload = {}
    report.updated_by = str(context.user_id)
    await _save(session, context, target, report, "apoa.undone", {"reason": request.reason})


async def release_for_front_desk_undo(
    session: AsyncSession, context: TenantContext, booking_id: UUID, undoing: str
) -> None:
    """Before the desk takes back a check-in or check-out. Flushed, not committed.

    A recorded APOA step must be undone in APOA's list first, or the record would no
    longer match the stay. Taking back a check-in also clears pending records, so the
    next check-in starts clean.
    """
    reports = (await reports_of(session, context, [booking_id])).values()
    blocking = DEPARTURE if undoing == DEPARTURE else None
    if any(r.status in DONE and (blocking is None or r.report_kind == blocking) for r in reports):
        raise errors.ApoaMarkedError
    if undoing == ARRIVAL:
        for report in reports:
            await session.delete(report)
        await session.flush()
