"""Deciding a transfer proof: approve (with the two-person rule) or reject.

Lock order is link, then payment, then proof — the same as gateway notifications
(app/services/gateway_events.py) — so a staff decision and a gateway "paid" notice
for the same link cannot deadlock, and the link is paid at most once.
"""

import datetime as dt
import logging
from uuid import UUID

from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.tenant import Document, Payment, PaymentLink, Property, TransferProof
from app.services import inbox
from app.services.booking_holds import settle_paid_link
from app.services.gateway_events import capture_payment
from app.services.payment_links import cancel_pending_payments, effective_status
from app.services.transfer_proofs import (
    APPROVED,
    PENDING,
    REJECTED,
    ProofAlreadyDecidedError,
    SameApproverError,
    actor_key,
    get_proof,
    needs_second_approval,
    state_for_people,
)
from app.tenancy.business_settings import PropertySettings, resolve_property_settings
from app.tenancy.context import TenantContext

log = logging.getLogger(__name__)


class LinkAlreadyPaidError(Exception):
    """The link was paid another way; this transfer needs a refund, not an approval."""


class LinkCancelledError(Exception):
    """The link was cancelled; it cannot be marked paid."""


async def _lock_link(session: AsyncSession, proof: TransferProof) -> PaymentLink | None:
    if proof.payment_link_id is None:
        return None
    return (
        await session.exec(
            select(PaymentLink)
            .where(
                col(PaymentLink.tenant_id) == proof.tenant_id,
                col(PaymentLink.id) == proof.payment_link_id,
            )
            .with_for_update()
            .execution_options(populate_existing=True)
        )
    ).one()


async def _lock_payment(session: AsyncSession, proof: TransferProof) -> Payment | None:
    if proof.payment_id is None:
        return None
    return (
        await session.exec(
            select(Payment)
            .where(col(Payment.tenant_id) == proof.tenant_id, col(Payment.id) == proof.payment_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
    ).first()


async def _lock_for_decision(
    session: AsyncSession, context: TenantContext, property_id: UUID, proof_id: UUID
) -> tuple[TransferProof, PaymentLink | None, Payment | None]:
    """Lock link, payment and proof (in that order) and insist the proof is undecided."""
    unlocked = await get_proof(session, context, property_id, proof_id)
    link = await _lock_link(session, unlocked)
    payment = await _lock_payment(session, unlocked)
    proof = await get_proof(session, context, property_id, proof_id, lock=True)
    if proof.match_status != PENDING:
        decided_as = state_for_people(proof)  # read before rollback expires the row
        await session.rollback()
        raise ProofAlreadyDecidedError(decided_as)
    return proof, link, payment


async def _schedule_image_deletion(
    session: AsyncSession, proof: TransferProof, settings: PropertySettings, today: dt.date
) -> None:
    document = (
        await session.exec(
            select(Document).where(
                col(Document.tenant_id) == proof.tenant_id, col(Document.id) == proof.document_id
            )
        )
    ).one()
    document.retention_until = today + dt.timedelta(days=settings.proof_retention_days)
    session.add(document)


def _record_decision(
    proof: TransferProof, status: str, context: TenantContext, now: dt.datetime
) -> None:
    proof.match_status = status
    proof.reviewed_by = actor_key(context)
    proof.reviewed_at = now
    proof.updated_by = str(context.user_id)


async def approve(
    session: AsyncSession, context: TenantContext, prop: Property, proof_id: UUID
) -> TransferProof:
    """Approve a proof. Commits.

    Above the threshold a non-owner's approval is recorded as the first of two and
    the proof stays awaiting; a different staff member (or the owner) completes it.
    """
    proof, link, payment = await _lock_for_decision(session, context, prop.id, proof_id)
    if link is not None and link.status == "paid":
        await session.rollback()
        raise LinkAlreadyPaidError
    if link is not None and link.status == "cancelled":
        await session.rollback()
        raise LinkCancelledError

    settings = resolve_property_settings(prop.settings)
    actor = actor_key(context)
    now = dt.datetime.now(dt.UTC)
    if needs_second_approval(proof.amount, settings) and not context.is_owner:
        if proof.first_approved_by is None:
            proof.first_approved_by = actor
            proof.first_approved_at = now
            session.add(proof)
            await session.commit()
            log.info("Transfer proof first approval proof=%s", proof.id)
            return proof
        if proof.first_approved_by == actor:
            await session.rollback()
            raise SameApproverError

    if payment is not None:
        capture_payment(payment, now)
        session.add(payment)
    if link is not None:
        link.status = "paid"  # also for a link that lapsed while the proof waited
        link.paid_at = now
        session.add(link)
        await session.flush()
        await cancel_pending_payments(session, link)
        if payment is not None:
            await settle_paid_link(session, context.tenant_id, link, payment)
    _record_decision(proof, APPROVED, context, now)
    session.add(proof)
    await _schedule_image_deletion(session, proof, settings, now.date())
    await session.commit()
    log.info("Transfer proof approved proof=%s link=%s", proof.id, proof.payment_link_id)
    return proof


def rejection_message(proof: TransferProof, reason: str, *, can_resend: bool) -> str:
    """Chat message telling the guest (Bahasa Indonesia, the guest default).

    `can_resend` is false when the pay link no longer takes a proof (already paid,
    cancelled or expired) or there never was one: asking for a new upload would mislead.
    """
    subject = f" untuk {proof.description}" if proof.description else ""
    refusal = f"Mohon maaf, bukti transfer{subject} belum dapat kami terima: {reason}"
    if can_resend:
        return f"{refusal}\nSilakan kirim ulang bukti transfer melalui tautan pembayaran yang sama."
    return f"{refusal}\nSilakan balas pesan ini bila ada pertanyaan."


async def _tell_guest_in_chat(
    session: AsyncSession, context: TenantContext, proof: TransferProof, text: str
) -> bool:
    """Best effort: the pay page shows the rejection whether or not this succeeds."""
    if proof.conversation_id is None:
        return False
    try:
        message = await inbox.send_reply(
            session,
            context,
            proof.property_id,
            proof.conversation_id,
            text,
        )
    except (inbox.ConversationResolvedError, inbox.ReplyWindowClosedError):
        return False
    except Exception:  # noqa: BLE001 — the rejection is already saved
        log.exception("Could not tell the guest about a rejected proof proof=%s", proof.id)
        await session.rollback()
        return False
    return message.status != "failed"


async def reject(
    session: AsyncSession, context: TenantContext, prop: Property, proof_id: UUID, reason: str
) -> TransferProof:
    """Reject a proof with a reason. Commits. The link stays payable."""
    proof, link, payment = await _lock_for_decision(session, context, prop.id, proof_id)
    now = dt.datetime.now(dt.UTC)
    can_resend = link is not None and effective_status(link, now) == "active"
    if payment is not None:
        payment.status = "failed"
        payment.failure_reason = "proof_rejected"
        session.add(payment)
    _record_decision(proof, REJECTED, context, now)
    proof.rejection_reason = reason
    session.add(proof)
    await _schedule_image_deletion(
        session, proof, resolve_property_settings(prop.settings), now.date()
    )
    await session.commit()
    log.info("Transfer proof rejected proof=%s", proof.id)
    notice = rejection_message(proof, reason, can_resend=can_resend)
    await _tell_guest_in_chat(session, context, proof, notice)
    return proof
