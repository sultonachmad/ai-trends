"""Who still needs reporting to APOA, and the register of what was reported.

APOA (Imigrasi) reads the passport itself, in its own app. This module only tracks two
steps per foreign guest and stay: checked in to APOA after check-in, and checked out of
APOA after check-out. A foreign guest is one whose confirmed document is a passport of
another country than Indonesia.

Every query here is batched over the stays on the list; nothing runs per guest.
"""

import datetime as dt
from collections import defaultdict
from dataclasses import dataclass
from uuid import UUID

from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.tenant import (
    Document,
    ForeignGuestReport,
    Guest,
    GuestDocument,
    Property,
    Reservation,
    ReservationGuest,
    ReservationUnit,
    Unit,
)
from app.schemas.apoa import ApoaCounts, ApoaItem, ApoaList, StepState, Unregistered
from app.services import calendar_dates as dates_of
from app.services.bookings import lines_of
from app.services.guest_id_reads import documents_of, staff_names
from app.services.id_validation import INDONESIA, PASSPORT
from app.services.room_assignment import room_name
from app.services.stay_status import CHECKED_OUT, IN_HOUSE
from app.tenancy.business_settings import resolve_property_settings
from app.tenancy.context import TenantContext

APOA = "apoa"
ARRIVAL, DEPARTURE = "arrival", "departure"
PENDING, SUBMITTED, NOT_REQUIRED = "pending", "submitted", "not_required"
DONE = (SUBMITTED, NOT_REQUIRED)
RECENT_DAYS = 30  # checked-out stays stay on the list this long
MAX_STAYS = 1000  # more than a month of stays at a large property; flagged if reached
_HIDDEN = "•" * 4

ReportKey = tuple[UUID, UUID, str]  # booking, guest, step


def is_foreign(document: GuestDocument | None) -> bool:
    return (
        document is not None
        and document.doc_type == PASSPORT
        and document.issuing_country not in (None, INDONESIA)
    )


def masked(last4: str | None) -> str | None:
    return f"{_HIDDEN}{last4}" if last4 else None


@dataclass(frozen=True)
class Stay:
    booking: Reservation
    lines: list[ReservationUnit]
    guest_ids: list[UUID]  # main guest first

    @property
    def checked_in_at(self) -> dt.datetime | None:
        times = [line.checked_in_at for line in self.lines if line.checked_in_at]
        return min(times) if times else None

    @property
    def checked_out_at(self) -> dt.datetime | None:
        if self.booking.status != CHECKED_OUT:
            return None
        times = [line.checked_out_at for line in self.lines if line.checked_out_at]
        return max(times) if times else None


# ---- loading ----------------------------------------------------------------------------


async def _bookings(
    session: AsyncSession, context: TenantContext, prop: Property, today: dt.date
) -> list[Reservation]:
    """In-house stays first, then recent check-outs, newest first (`MAX_STAYS` + 1 at most)."""
    recent = today - dt.timedelta(days=RECENT_DAYS)
    in_house = col(Reservation.status) == IN_HOUSE
    rows = await session.exec(
        select(Reservation)
        .where(
            col(Reservation.tenant_id) == context.tenant_id,
            col(Reservation.property_id) == prop.id,
            col(Reservation.status).in_((IN_HOUSE, CHECKED_OUT)),
            in_house | (col(Reservation.departure_date) >= recent),
        )
        .order_by(in_house.desc(), col(Reservation.departure_date).desc(), col(Reservation.id))
        .limit(MAX_STAYS + 1)
    )
    return list(rows.all())


async def _guest_ids(
    session: AsyncSession, context: TenantContext, bookings: list[Reservation], lines: dict
) -> dict[UUID, list[UUID]]:
    """Guest ids per booking, the main guest (booker, else primary) first."""
    booking_of = {line.id: booking_id for booking_id, rows in lines.items() for line in rows}
    rows = await session.exec(
        select(
            ReservationGuest.reservation_unit_id,
            ReservationGuest.guest_id,
            ReservationGuest.is_primary,
        )
        .where(
            col(ReservationGuest.tenant_id) == context.tenant_id,
            col(ReservationGuest.reservation_unit_id).in_(list(booking_of)),
        )
        .order_by(
            col(ReservationGuest.is_primary).desc(),
            col(ReservationGuest.created_at),
            col(ReservationGuest.id),
        )
    )
    linked: dict[UUID, list[UUID]] = defaultdict(list)
    for unit_id, guest_id, _ in rows.all():
        linked[booking_of[unit_id]].append(guest_id)
    return {
        b.id: list(dict.fromkeys(g for g in [b.booker_guest_id, *linked[b.id]] if g))
        for b in bookings
    }


async def load_stays(
    session: AsyncSession, context: TenantContext, bookings: list[Reservation]
) -> list[Stay]:
    lines: dict[UUID, list[ReservationUnit]] = defaultdict(list)
    for line in await lines_of(session, context, [b.id for b in bookings]):
        lines[line.reservation_id].append(line)
    guests = await _guest_ids(session, context, bookings, lines)
    return [Stay(b, lines[b.id], guests[b.id]) for b in bookings]


async def reports_of(
    session: AsyncSession, context: TenantContext, booking_ids: list[UUID]
) -> dict[ReportKey, ForeignGuestReport]:
    if not booking_ids:
        return {}
    rows = await session.exec(
        select(ForeignGuestReport, ReservationUnit.reservation_id)
        .join(
            ReservationGuest,
            (col(ReservationGuest.tenant_id) == col(ForeignGuestReport.tenant_id))
            & (col(ReservationGuest.id) == col(ForeignGuestReport.reservation_guest_id)),
        )
        .join(
            ReservationUnit,
            (col(ReservationUnit.tenant_id) == col(ReservationGuest.tenant_id))
            & (col(ReservationUnit.id) == col(ReservationGuest.reservation_unit_id)),
        )
        .where(
            col(ForeignGuestReport.tenant_id) == context.tenant_id,
            col(ForeignGuestReport.report_system) == APOA,
            col(ReservationUnit.reservation_id).in_(booking_ids),
        )
    )
    return {(b, r.guest_id, r.report_kind): r for r, b in rows.all()}


async def _names(session: AsyncSession, context: TenantContext, ids: set[UUID], model) -> dict:  # noqa: ANN001
    if not ids:
        return {}
    rows = await session.exec(
        select(model).where(col(model.tenant_id) == context.tenant_id, col(model.id).in_(ids))
    )
    return {row.id: row for row in rows.all()}


async def _live_scans(session: AsyncSession, context: TenantContext, ids: set) -> set:
    if not ids:
        return set()
    rows = await session.exec(
        select(Document.id).where(
            col(Document.tenant_id) == context.tenant_id,
            col(Document.id).in_(ids),
            col(Document.purged_at).is_(None),
        )
    )
    return set(rows.all())


# ---- building ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _Lookups:
    documents: dict[UUID, GuestDocument]
    guests: dict[UUID, Guest]
    units: dict[UUID, Unit]
    reports: dict[ReportKey, ForeignGuestReport]
    scans: set
    names: dict[str, str]
    hours: int
    now: dt.datetime


def _state(report: ForeignGuestReport | None, names: dict[str, str]) -> StepState:
    if report is None:
        return StepState(status=PENDING)
    return StepState(
        status=report.status,
        at=report.submitted_at,
        by=names.get(report.submitted_by or "", report.submitted_by),
        reference=report.external_reference,
        reason=report.payload.get("reason") if report.status == NOT_REQUIRED else None,
    )


def _next_step(stay: Stay, arrival: str, departure: str) -> str | None:
    if arrival not in DONE:
        return ARRIVAL
    if arrival == SUBMITTED and departure not in DONE and stay.checked_out_at is not None:
        return DEPARTURE
    return None


def _item(stay: Stay, guest_id: UUID, look: _Lookups) -> ApoaItem:
    document, guest = look.documents[guest_id], look.guests[guest_id]
    arrival = look.reports.get((stay.booking.id, guest_id, ARRIVAL))
    departure = look.reports.get((stay.booking.id, guest_id, DEPARTURE))
    step = _next_step(stay, *(r.status if r else PENDING for r in (arrival, departure)))
    start = stay.checked_out_at if step == DEPARTURE else stay.checked_in_at
    due = start + dt.timedelta(hours=look.hours) if step and start else None
    unit = look.units.get(stay.lines[0].unit_id) if stay.lines and stay.lines[0].unit_id else None
    return ApoaItem(
        booking_id=stay.booking.id,
        booking_number=stay.booking.confirmation_no,
        guest_id=guest_id,
        document_id=document.id,
        full_name=guest.full_name,
        nationality=document.issuing_country or "",
        masked_number=masked(document.doc_number_last4 if document.doc_number_encrypted else None),
        visa_type=document.visa_type,
        room=room_name(unit) if unit else None,
        checked_in_at=stay.checked_in_at or look.now,
        checked_out_at=stay.checked_out_at,
        step=step,
        due_at=due,
        overdue=due is not None and due < look.now,
        has_image=document.scan_document_id in look.scans,
        arrival=_state(arrival, look.names),
        departure=_state(departure, look.names),
    )


def _foreign_of(stay: Stay, documents: dict[UUID, GuestDocument]) -> list[UUID]:
    return [g for g in stay.guest_ids if is_foreign(documents.get(g))]


def _unregistered(stay: Stay, foreign: list[UUID], guests: dict) -> Unregistered | None:
    expected = stay.booking.adults + stay.booking.children
    if stay.booking.status != IN_HOUSE or not foreign or len(stay.guest_ids) >= expected:
        return None
    main = guests.get(stay.guest_ids[0])
    return Unregistered(
        booking_id=stay.booking.id,
        booking_number=stay.booking.confirmation_no,
        guest_name=main.full_name if main else "",
        listed=len(stay.guest_ids),
        expected=expected,
    )


async def _lookups(
    session: AsyncSession, context: TenantContext, stays: list[Stay], hours: int, today: dt.date
) -> _Lookups:
    guest_ids = list({g for stay in stays for g in stay.guest_ids})
    documents = await documents_of(session, context, guest_ids, today)
    reports = await reports_of(session, context, [s.booking.id for s in stays])
    return _Lookups(
        documents=documents,
        guests=await _names(session, context, set(guest_ids), Guest),
        units=await _names(
            session, context, {ln.unit_id for s in stays for ln in s.lines if ln.unit_id}, Unit
        ),
        reports=reports,
        scans=await _live_scans(
            session, context, {d.scan_document_id for d in documents.values() if d.scan_document_id}
        ),
        names=await staff_names(session, context, {r.submitted_by or "" for r in reports.values()}),
        hours=hours,
        now=dt.datetime.now(dt.UTC),
    )


async def read_worklist(session: AsyncSession, context: TenantContext, prop: Property) -> ApoaList:
    today = dates_of.property_today(prop.timezone)
    hours = resolve_property_settings(prop.settings).apoa_deadline_hours
    bookings = await _bookings(session, context, prop, today)
    stays = await load_stays(session, context, bookings[:MAX_STAYS])
    look = await _lookups(session, context, stays, hours, today)
    items, flags = [], []
    for stay in stays:
        foreign = _foreign_of(stay, look.documents)
        items.extend(_item(stay, g, look) for g in foreign if stay.checked_in_at)
        flag = _unregistered(stay, foreign, look.guests)
        if flag:
            flags.append(flag)
    by_due = sorted(items, key=lambda i: (i.due_at or look.now, i.full_name))
    return ApoaList(
        date=today,
        deadline_hours=hours,
        to_report=[i for i in by_due if i.step == ARRIVAL],
        to_check_out=[i for i in by_due if i.step == DEPARTURE],
        done=[i for i in items if i.step is None],
        unregistered=flags,
        truncated=len(bookings) > MAX_STAYS,
    )


async def counts(session: AsyncSession, context: TenantContext, prop: Property) -> ApoaCounts:
    """What is due and overdue in APOA, for the front desk banner. No guest details loaded."""
    today = dates_of.property_today(prop.timezone)
    hours = dt.timedelta(hours=resolve_property_settings(prop.settings).apoa_deadline_hours)
    bookings = await _bookings(session, context, prop, today)
    stays = await load_stays(session, context, bookings[:MAX_STAYS])
    guest_ids = list({g for stay in stays for g in stay.guest_ids})
    documents = await documents_of(session, context, guest_ids, today)
    reports = await reports_of(session, context, [s.booking.id for s in stays])
    now, due, overdue = dt.datetime.now(dt.UTC), 0, 0
    for stay in stays:
        for guest_id in _foreign_of(stay, documents) if stay.checked_in_at else []:
            states = (
                reports.get((stay.booking.id, guest_id, step)) for step in (ARRIVAL, DEPARTURE)
            )
            step = _next_step(stay, *(r.status if r else PENDING for r in states))
            start = stay.checked_out_at if step == DEPARTURE else stay.checked_in_at
            if step and start:
                due += 1
                overdue += start + hours < now
    return ApoaCounts(due=due, overdue=overdue)
