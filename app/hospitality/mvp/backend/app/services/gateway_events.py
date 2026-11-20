"""Applying payment notifications from a gateway.

`handle_gateway_event` is the single entry point: the simulator calls it today and
the real gateway webhook will call it later.

Rules
* Every event is stored once (unique per gateway account and event id); a repeat
  changes nothing.
* A "paid" event must match a payment we created and its exact amount.
* The link's row is locked while the event is applied, so a link is paid once.
  Locks are always taken link first, then payments.
* Money that arrives for a link that is already paid, expired or cancelled is
  recorded on the payment and flagged for a person to refund — never applied.
"""

import datetime as dt
import logging
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.tenant import Payment, PaymentEvent, PaymentLink
from app.services.payment_links import (
    NEEDS_REFUND_FLAG,
    cancel_pending_payments,
    effective_status,
)

log = logging.getLogger(__name__)

PAID_EVENT = "payment.paid"


@dataclass(frozen=True)
class GatewayEvent:
    gateway_event_id: str
    event_type: str
    gateway_reference: str
    amount: Decimal
    signature_valid: bool
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class EventOutcome:
    """applied | duplicate | ignored, with the reason when not applied."""

    result: str
    reason: str | None = None


async def _store_event(
    session: AsyncSession, tenant_id: UUID, account_id: UUID, event: GatewayEvent
) -> PaymentEvent | None:
    """Insert the raw event; None when this event id was already stored."""
    stored = PaymentEvent(
        tenant_id=tenant_id,
        gateway_account_id=account_id,
        gateway_event_id=event.gateway_event_id,
        event_type=event.event_type,
        raw=event.raw,
        signature_valid=event.signature_valid,
    )
    try:
        async with session.begin_nested():
            session.add(stored)
        return stored
    except IntegrityError:
        return None


async def _finish(
    session: AsyncSession, stored: PaymentEvent, status: str, outcome: EventOutcome
) -> EventOutcome:
    stored.status = status
    stored.processed_at = dt.datetime.now(dt.UTC)
    session.add(stored)
    await session.commit()
    return outcome


def capture_payment(payment: Payment, now: dt.datetime) -> None:
    """Mark `payment` as received in full."""
    payment.status = "captured"
    payment.authorized_amount = payment.amount
    payment.captured_amount = payment.amount
    payment.captured_at = now
    payment.version = payment.version + 1


async def handle_gateway_event(
    session: AsyncSession, tenant_id: UUID, account_id: UUID, event: GatewayEvent
) -> EventOutcome:
    """Apply one gateway event. Commits. Safe to call again with the same event id."""
    stored = await _store_event(session, tenant_id, account_id, event)
    if stored is None:
        await session.commit()
        return EventOutcome("duplicate")
    if not event.signature_valid:
        return await _finish(session, stored, "rejected", EventOutcome("ignored", "bad_signature"))
    if event.event_type != PAID_EVENT:
        return await _finish(session, stored, "ignored", EventOutcome("ignored", "unknown_type"))

    # Lock order is always link first, then its payments (the same as starting a
    # payment and cancelling a link), so concurrent events for one link cannot deadlock.
    payment_filter = (
        col(Payment.tenant_id) == tenant_id,
        col(Payment.gateway_account_id) == account_id,
        col(Payment.gateway_reference) == event.gateway_reference,
    )
    link_id = (await session.exec(select(Payment.payment_link_id).where(*payment_filter))).first()
    if link_id is None:
        return await _finish(session, stored, "ignored", EventOutcome("ignored", "unknown_payment"))
    link = (
        await session.exec(
            select(PaymentLink)
            .where(col(PaymentLink.tenant_id) == tenant_id, col(PaymentLink.id) == link_id)
            .with_for_update()
        )
    ).one()
    payment = (await session.exec(select(Payment).where(*payment_filter).with_for_update())).one()
    stored.payment_id = payment.id
    if payment.status == "captured":
        return await _finish(session, stored, "ignored", EventOutcome("duplicate"))
    if event.amount != payment.amount:
        payment.failure_reason = "amount_mismatch"
        session.add(payment)
        log.warning("Gateway amount mismatch payment=%s", payment.id)
        return await _finish(
            session, stored, "rejected", EventOutcome("ignored", "amount_mismatch")
        )

    now = dt.datetime.now(dt.UTC)
    capture_payment(payment, now)
    status = effective_status(link, now)
    if status != "active":
        # Money arrived for a link that can no longer be paid: keep the record, flag it.
        payment.metadata_ = {**(payment.metadata_ or {}), NEEDS_REFUND_FLAG: f"link_{status}"}
        session.add(payment)
        if link.status == "active":  # it lapsed and nothing had written that yet
            link.status = "expired"
            session.add(link)
        await session.flush()
        await cancel_pending_payments(session, link)
        log.error(
            "REFUND REVIEW: payment %s captured for a %s link %s", payment.id, status, link.id
        )
        return await _finish(session, stored, "flagged", EventOutcome("ignored", f"link_{status}"))

    session.add(payment)
    link.status = "paid"
    link.paid_at = now
    session.add(link)
    await session.flush()
    await cancel_pending_payments(session, link)
    log.info("Payment link paid link=%s payment=%s", link.id, payment.id)
    return await _finish(session, stored, "applied", EventOutcome("applied"))
