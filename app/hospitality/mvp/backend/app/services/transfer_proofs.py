"""Transfer proofs ("bukti transfer"): submit, list, review.

A proof is a screenshot of a bank transfer plus the amount staff expect. It is
`pending` until a person decides: approved (`manually_confirmed`) marks its pay link
paid by bank transfer; `rejected` keeps the link payable and tells the guest why.

Rules
* Images only, judged by content; size and "awaiting per link" are property settings.
* An image already used by another proof in the tenant is flagged, never blocked.
* Above the property's threshold, approval takes two different staff members; the
  owner may approve alone.
* A link may be approved while pending or expired, not when cancelled or paid.
* Locks are taken link first, then payment, then proof — the same order as gateway
  notifications, so the two cannot deadlock.

Every query filters on `tenant_id` and the property explicitly, on top of
row-level security.
"""

import datetime as dt
import logging
import uuid
from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, tuple_
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.documents.images import content_hash, detect_image_type
from app.documents.storage import DocumentStorage
from app.models.tenant import (
    Conversation,
    Document,
    Guest,
    Payment,
    PaymentLink,
    Property,
    StaffMember,
    TransferProof,
)
from app.schemas.inbox import GuestSummary
from app.schemas.transfer_proofs import DuplicateOf, ProofFilter, ProofPage, ProofRead, PublicProof
from app.services.payment_links import (
    AmountOutOfRangeError,
    effective_status,
    money,
)
from app.tenancy.business_settings import PropertySettings, resolve_property_settings
from app.tenancy.context import TenantContext

log = logging.getLogger(__name__)

PENDING = "pending"
APPROVED = "manually_confirmed"
REJECTED = "rejected"
BANK_TRANSFER = "bank_transfer"
AWAITING_VERIFICATION = "awaiting_verification"
GUEST_UPLOAD = "portal"
STAFF_UPLOAD = "staff_upload"
DEFAULT_PAGE_SIZE = 30
MAX_PAGE_SIZE = 50
BYTES_PER_MB = 1024 * 1024
_CURSOR_SEPARATOR = "|"
_FILTER_STATUS = {"awaiting": PENDING, "approved": APPROVED, "rejected": REJECTED}


class ProofNotFoundError(LookupError):
    """No such transfer proof in the caller's property."""


class ProofLinkNotFoundError(LookupError):
    """The pay link named for the proof does not exist in the caller's property."""


class ProofConversationNotFoundError(LookupError):
    """The conversation named for the proof does not exist in the caller's property."""


class EmptyFileError(ValueError):
    """The upload has no content."""


class NotAnImageError(ValueError):
    """The upload is not a JPEG, PNG or WebP image."""


class FileTooLargeError(ValueError):
    def __init__(self, limit_mb: int) -> None:
        super().__init__(f"file is larger than {limit_mb} MB")
        self.limit_mb = limit_mb


class TooManyProofsError(Exception):
    """This link already has the allowed number of proofs waiting for review."""


class LinkNotOpenForProofError(Exception):
    """The link is paid or cancelled (or, for a guest, expired)."""

    def __init__(self, state: str) -> None:
        super().__init__(state)
        self.state = state


class ProofAlreadyDecidedError(Exception):
    def __init__(self, state: str) -> None:
        super().__init__(state)
        self.state = state


class SameApproverError(Exception):
    """The second approval must come from a different staff member."""


class InvalidCursorError(ValueError):
    """The paging cursor is malformed."""


class ProofImageGoneError(Exception):
    """The image was deleted after its retention period."""


@dataclass(frozen=True)
class ProofUpload:
    content: bytes
    original_name: str | None


def actor_key(context: TenantContext) -> str:
    """How a staff member is recorded on a decision."""
    return str(context.staff_member_id) if context.staff_member_id else f"user:{context.user_id}"


def state_for_people(proof: TransferProof) -> str:
    if proof.match_status == APPROVED:
        return "approved"
    if proof.match_status == REJECTED:
        return "rejected"
    return "awaiting_second" if proof.first_approved_by else "awaiting"


def needs_second_approval(amount: Decimal | None, settings: PropertySettings) -> bool:
    return amount is not None and amount > settings.second_approver_threshold_idr


# ---------------------------------------------------------------------------- submitting


def _check_upload(upload: ProofUpload, settings: PropertySettings) -> tuple[str, str, str]:
    """(content type, extension, sha256) of an acceptable image, or a named error."""
    if not upload.content:
        raise EmptyFileError
    if len(upload.content) > settings.proof_max_upload_mb * BYTES_PER_MB:
        raise FileTooLargeError(settings.proof_max_upload_mb)
    image = detect_image_type(upload.content)
    if image is None:
        raise NotAnImageError
    return image.content_type, image.extension, content_hash(upload.content)


async def _earlier_proof_with_image(
    session: AsyncSession, tenant_id: UUID, sha256: str
) -> UUID | None:
    statement = (
        select(TransferProof.id)
        .join(
            Document,
            (col(Document.tenant_id) == col(TransferProof.tenant_id))
            & (col(Document.id) == col(TransferProof.document_id)),
        )
        .where(col(TransferProof.tenant_id) == tenant_id, col(Document.sha256) == sha256)
        .order_by(col(TransferProof.created_at), col(TransferProof.id))
        .limit(1)
    )
    return (await session.exec(statement)).first()


@dataclass(frozen=True)
class _ProofTarget:
    """What a new proof is for."""

    tenant_id: UUID
    property_id: UUID
    amount: Decimal
    description: str | None
    payment_link_id: UUID | None
    guest_id: UUID | None
    conversation_id: UUID | None


async def _store_proof(
    session: AsyncSession,
    storage: DocumentStorage,
    target: _ProofTarget,
    upload: ProofUpload,
    settings: PropertySettings,
    *,
    submitted_via: str,
    uploaded_by: str | None,
    consent_at: dt.datetime | None,
) -> TransferProof:
    """Save the image and record document, payment-awaiting-review and proof. Commits."""
    content_type, extension, sha256 = _check_upload(upload, settings)
    duplicate_of = await _earlier_proof_with_image(session, target.tenant_id, sha256)
    storage_key = await storage.save(target.tenant_id, upload.content, extension)
    try:
        document = Document(
            tenant_id=target.tenant_id,
            property_id=target.property_id,
            kind="transfer_proof",
            classification="financial",
            storage_key=storage_key,
            original_name=None,  # a client-chosen name is neither needed nor trusted
            content_type=content_type,
            size_bytes=len(upload.content),
            sha256=sha256,
            uploaded_by=uploaded_by,
            # Deleted on time even if nobody ever reviews it; a decision restarts the clock.
            retention_until=dt.datetime.now(dt.UTC).date()
            + dt.timedelta(days=settings.proof_retention_days),
        )
        session.add(document)
        proof_id = uuid.uuid4()
        payment = Payment(
            tenant_id=target.tenant_id,
            property_id=target.property_id,
            payment_link_id=target.payment_link_id,
            direction="inbound",
            method=BANK_TRANSFER,
            status=AWAITING_VERIFICATION,
            amount=target.amount,
            idempotency_key=f"proof:{proof_id}",
        )
        session.add(payment)
        await session.flush()
        proof = TransferProof(
            id=proof_id,
            tenant_id=target.tenant_id,
            property_id=target.property_id,
            payment_id=payment.id,
            document_id=document.id,
            submitted_via=submitted_via,
            match_status=PENDING,
            payment_link_id=target.payment_link_id,
            guest_id=target.guest_id,
            conversation_id=target.conversation_id,
            amount=target.amount,
            description=target.description,
            duplicate_of_proof_id=duplicate_of,
            consent_at=consent_at,
            created_by=uploaded_by,
        )
        session.add(proof)
        await session.commit()
    except Exception:
        await session.rollback()
        await _discard_file(storage, target.tenant_id, storage_key)
        raise
    log.info("Transfer proof submitted proof=%s via=%s", proof.id, submitted_via)
    return proof


async def _discard_file(storage: DocumentStorage, tenant_id: UUID, storage_key: str) -> None:
    """Remove an image whose record was not saved; a failure here must not hide the cause."""
    try:
        await storage.delete(tenant_id, storage_key)
    except Exception:
        log.exception("Could not remove unrecorded proof image key=%s", storage_key)


async def _awaiting_count(session: AsyncSession, link: PaymentLink) -> int:
    statement = (
        select(func.count())
        .select_from(TransferProof)
        .where(
            col(TransferProof.tenant_id) == link.tenant_id,
            col(TransferProof.payment_link_id) == link.id,
            col(TransferProof.match_status) == PENDING,
        )
    )
    return int((await session.exec(statement)).one())


def _target_for_link(link: PaymentLink) -> _ProofTarget:
    return _ProofTarget(
        tenant_id=link.tenant_id,
        property_id=link.property_id,
        amount=link.amount,
        description=link.description,
        payment_link_id=link.id,
        guest_id=link.guest_id,
        conversation_id=link.conversation_id,
    )


async def submit_for_link(
    session: AsyncSession,
    storage: DocumentStorage,
    link: PaymentLink,
    prop: Property,
    upload: ProofUpload,
    *,
    by_guest: bool,
    uploaded_by: str | None,
) -> TransferProof:
    """Attach a proof to `link`, whose row the caller has locked.

    A guest may only add to a link that is still pending; staff may also add to an
    expired one (the guest paid in time, the screenshot arrived later).
    """
    status = effective_status(link, dt.datetime.now(dt.UTC))
    open_states = {"active"} if by_guest else {"active", "expired"}
    if status not in open_states:
        await session.rollback()
        raise LinkNotOpenForProofError({"active": "pending"}.get(status, status))
    settings = resolve_property_settings(prop.settings)
    if await _awaiting_count(session, link) >= settings.proof_max_awaiting_per_link:
        await session.rollback()
        raise TooManyProofsError
    link_id, tenant_id = link.id, link.tenant_id
    proof = await _store_proof(
        session,
        storage,
        _target_for_link(link),
        upload,
        settings,
        submitted_via=GUEST_UPLOAD if by_guest else STAFF_UPLOAD,
        uploaded_by=uploaded_by,
        consent_at=dt.datetime.now(dt.UTC) if by_guest else None,
    )
    from app.services.booking_holds import extend_for_proof

    await extend_for_proof(session, link_id, tenant_id)
    return proof


async def submit_by_staff(
    session: AsyncSession,
    storage: DocumentStorage,
    context: TenantContext,
    prop: Property,
    upload: ProofUpload,
    *,
    payment_link_id: UUID | None,
    amount: Decimal | None,
    description: str | None,
    conversation_id: UUID | None,
) -> TransferProof:
    """Staff record a proof: for a pay link, or for a transfer that had no link."""
    if payment_link_id is not None:
        link = (
            await session.exec(
                select(PaymentLink)
                .where(
                    col(PaymentLink.tenant_id) == context.tenant_id,
                    col(PaymentLink.property_id) == prop.id,
                    col(PaymentLink.id) == payment_link_id,
                )
                .with_for_update()
            )
        ).first()
        if link is None:
            raise ProofLinkNotFoundError
        return await submit_for_link(
            session, storage, link, prop, upload, by_guest=False, uploaded_by=actor_key(context)
        )

    settings = resolve_property_settings(prop.settings)
    low, high = settings.payment_link_min_amount_idr, settings.payment_link_max_amount_idr
    if amount is None or not low <= amount <= high:
        raise AmountOutOfRangeError(low, high)
    guest_id = None
    if conversation_id is not None:
        conversation = (
            await session.exec(
                select(Conversation).where(
                    col(Conversation.tenant_id) == context.tenant_id,
                    col(Conversation.property_id) == prop.id,
                    col(Conversation.id) == conversation_id,
                )
            )
        ).first()
        if conversation is None:
            raise ProofConversationNotFoundError
        guest_id = conversation.guest_id
    target = _ProofTarget(
        tenant_id=context.tenant_id,
        property_id=prop.id,
        amount=amount,
        description=description,
        payment_link_id=None,
        guest_id=guest_id,
        conversation_id=conversation_id,
    )
    return await _store_proof(
        session,
        storage,
        target,
        upload,
        settings,
        submitted_via=STAFF_UPLOAD,
        uploaded_by=actor_key(context),
        consent_at=None,
    )


# ------------------------------------------------------------------------------- reading


@dataclass(frozen=True)
class _Related:
    guests: dict[UUID, Guest]
    staff_names: dict[str, str]
    documents: dict[UUID, Document]
    earlier: dict[UUID, TransferProof]


async def _related(session: AsyncSession, tenant_id: UUID, proofs: list[TransferProof]) -> _Related:
    """Everything a page of proofs refers to — a fixed number of queries, not per row."""
    guest_ids = {p.guest_id for p in proofs if p.guest_id}
    guests: dict[UUID, Guest] = {}
    if guest_ids:
        rows = await session.exec(
            select(Guest).where(col(Guest.tenant_id) == tenant_id, col(Guest.id).in_(guest_ids))
        )
        guests = {g.id: g for g in rows.all()}

    staff_ids: set[UUID] = set()
    for proof in proofs:
        for key in (proof.created_by, proof.first_approved_by, proof.reviewed_by):
            try:
                staff_ids.add(UUID(key or ""))
            except ValueError:
                continue
    staff_names: dict[str, str] = {}
    if staff_ids:
        rows = await session.exec(
            select(StaffMember.id, StaffMember.display_name).where(
                col(StaffMember.tenant_id) == tenant_id, col(StaffMember.id).in_(staff_ids)
            )
        )
        staff_names = {str(staff_id): name for staff_id, name in rows.all()}

    documents: dict[UUID, Document] = {}
    if proofs:
        rows = await session.exec(
            select(Document).where(
                col(Document.tenant_id) == tenant_id,
                col(Document.id).in_([p.document_id for p in proofs]),
            )
        )
        documents = {d.id: d for d in rows.all()}

    earlier_ids = {p.duplicate_of_proof_id for p in proofs if p.duplicate_of_proof_id}
    earlier: dict[UUID, TransferProof] = {}
    if earlier_ids:
        rows = await session.exec(
            select(TransferProof).where(
                col(TransferProof.tenant_id) == tenant_id, col(TransferProof.id).in_(earlier_ids)
            )
        )
        earlier = {p.id: p for p in rows.all()}
    return _Related(guests=guests, staff_names=staff_names, documents=documents, earlier=earlier)


def _to_read(proof: TransferProof, related: _Related, settings: PropertySettings) -> ProofRead:
    guest = related.guests.get(proof.guest_id) if proof.guest_id else None
    document = related.documents.get(proof.document_id)
    earlier = (
        related.earlier.get(proof.duplicate_of_proof_id) if proof.duplicate_of_proof_id else None
    )
    by_guest = proof.submitted_via == GUEST_UPLOAD
    return ProofRead(
        id=proof.id,
        state=state_for_people(proof),  # type: ignore[arg-type]
        amount=money(proof.amount) if proof.amount is not None else None,
        description=proof.description,
        guest=(
            GuestSummary(id=guest.id, name=guest.full_name, phone=guest.whatsapp_phone)
            if guest
            else None
        ),
        payment_link_id=proof.payment_link_id,
        conversation_id=proof.conversation_id,
        submitted_by_guest=by_guest,
        uploaded_by_name=None if by_guest else related.staff_names.get(proof.created_by or ""),
        created_at=proof.created_at,
        needs_second_approval=needs_second_approval(proof.amount, settings),
        first_approved_by_name=related.staff_names.get(proof.first_approved_by or ""),
        reviewed_by_name=related.staff_names.get(proof.reviewed_by or ""),
        reviewed_at=proof.reviewed_at,
        rejection_reason=proof.rejection_reason,
        duplicate_of=(
            DuplicateOf(
                id=earlier.id, description=earlier.description, created_at=earlier.created_at
            )
            if earlier
            else None
        ),
        image_available=document is not None and document.purged_at is None,
    )


async def read_one(session: AsyncSession, proof: TransferProof, prop: Property) -> ProofRead:
    related = await _related(session, proof.tenant_id, [proof])
    return _to_read(proof, related, resolve_property_settings(prop.settings))


def encode_cursor(proof: TransferProof) -> str:
    return f"{proof.created_at.isoformat()}{_CURSOR_SEPARATOR}{proof.id}"


def decode_cursor(cursor: str) -> tuple[dt.datetime, UUID]:
    try:
        stamp, identifier = cursor.split(_CURSOR_SEPARATOR, 1)
        moment, proof_id = dt.datetime.fromisoformat(stamp), UUID(identifier)
    except ValueError as exc:
        raise InvalidCursorError("invalid cursor") from exc
    if moment.tzinfo is None:
        raise InvalidCursorError("invalid cursor")
    return moment, proof_id


async def list_proofs(
    session: AsyncSession,
    context: TenantContext,
    prop: Property,
    state: ProofFilter = "awaiting",
    limit: int = DEFAULT_PAGE_SIZE,
    cursor: str | None = None,
) -> ProofPage:
    limit = max(1, min(limit, MAX_PAGE_SIZE))
    statement = select(TransferProof).where(
        col(TransferProof.tenant_id) == context.tenant_id,
        col(TransferProof.property_id) == prop.id,
        col(TransferProof.match_status) == _FILTER_STATUS[state],
    )
    if cursor:
        statement = statement.where(
            tuple_(col(TransferProof.created_at), col(TransferProof.id)) < decode_cursor(cursor)
        )
    statement = statement.order_by(
        col(TransferProof.created_at).desc(), col(TransferProof.id).desc()
    ).limit(limit + 1)
    rows = list((await session.exec(statement)).all())
    page, has_more = rows[:limit], len(rows) > limit
    related = await _related(session, context.tenant_id, page)
    settings = resolve_property_settings(prop.settings)
    return ProofPage(
        items=[_to_read(proof, related, settings) for proof in page],
        next_cursor=encode_cursor(page[-1]) if has_more else None,
    )


async def awaiting_review_count(
    session: AsyncSession, context: TenantContext, property_id: UUID
) -> int:
    statement = (
        select(func.count())
        .select_from(TransferProof)
        .where(
            col(TransferProof.tenant_id) == context.tenant_id,
            col(TransferProof.property_id) == property_id,
            col(TransferProof.match_status) == PENDING,
        )
    )
    return int((await session.exec(statement)).one())


async def get_proof(
    session: AsyncSession,
    context: TenantContext,
    property_id: UUID,
    proof_id: UUID,
    *,
    lock: bool = False,
) -> TransferProof:
    statement = select(TransferProof).where(
        col(TransferProof.tenant_id) == context.tenant_id,
        col(TransferProof.property_id) == property_id,
        col(TransferProof.id) == proof_id,
    )
    if lock:
        statement = statement.with_for_update().execution_options(populate_existing=True)
    proof = (await session.exec(statement)).first()
    if proof is None:
        raise ProofNotFoundError
    return proof


async def read_image(
    session: AsyncSession,
    storage: DocumentStorage,
    context: TenantContext,
    property_id: UUID,
    proof_id: UUID,
) -> tuple[bytes, str]:
    """The proof's image bytes and content type, for staff of the owning tenant only."""
    proof = await get_proof(session, context, property_id, proof_id)
    document = (
        await session.exec(
            select(Document).where(
                col(Document.tenant_id) == context.tenant_id,
                col(Document.id) == proof.document_id,
            )
        )
    ).one()
    if document.purged_at is not None:
        raise ProofImageGoneError
    try:
        content = await storage.read(context.tenant_id, document.storage_key)
    except FileNotFoundError:
        log.error("Transfer proof file missing on disk proof=%s", proof.id)
        raise ProofImageGoneError from None
    return content, document.content_type


async def latest_public_proof(session: AsyncSession, link: PaymentLink) -> PublicProof | None:
    """What the guest may see about the newest proof on their link."""
    proof = (
        await session.exec(
            select(TransferProof)
            .where(
                col(TransferProof.tenant_id) == link.tenant_id,
                col(TransferProof.payment_link_id) == link.id,
                col(TransferProof.match_status).in_((PENDING, REJECTED)),
            )
            .order_by(col(TransferProof.created_at).desc(), col(TransferProof.id).desc())
            .limit(1)
        )
    ).first()
    if proof is None:
        return None
    if proof.match_status == PENDING:
        return PublicProof(state="checking", reason=None)
    return PublicProof(state="rejected", reason=proof.rejection_reason)
