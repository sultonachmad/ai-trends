"""The public pay page: show a link, start a payment, give payment instructions.

Runs on a session scoped to the link's tenant (see app/tenancy/public.py). Every
query still filters on `tenant_id` and the token fingerprint explicitly.

A payment attempt is recorded first, then the gateway is asked for instructions with
no database lock held — the same order as sending a chat reply.
"""

import datetime as dt
import logging
from uuid import UUID

from sqlalchemy import func
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.config import settings as app_settings
from app.documents.storage import DocumentStorage
from app.models.tenant import (
    Payment,
    PaymentGatewayAccount,
    PaymentLink,
    Property,
)
from app.payments.gateway import (
    VA_BANKS,
    VIRTUAL_ACCOUNT,
    ChargeInstructions,
    ChargeRequest,
    GatewayError,
    get_gateway,
)
from app.schemas.payment_links import PaymentInstructions, PublicPaymentLink
from app.schemas.transfer_proofs import ManualTransfer
from app.services.gateway_accounts import get_or_create_gateway_account
from app.services.payment_links import (
    cancel_pending_payments,
    effective_status,
    money,
    state_for_people,
)
from app.services.transfer_proofs import (
    BANK_TRANSFER,
    ProofUpload,
    latest_public_proof,
    submit_for_link,
)
from app.tenancy.business_settings import bank_account, resolve_property_settings
from app.tenancy.public import PublicLinkScope

log = logging.getLogger(__name__)

# Failed attempts each cost a gateway call; a link never needs more than a handful.
MAX_ATTEMPTS_PER_LINK = 20


class PublicLinkNotFoundError(LookupError):
    """The token resolved to a tenant but the link is gone."""


class LinkNotPayableError(Exception):
    """The link is paid, expired or cancelled."""

    def __init__(self, state: str) -> None:
        super().__init__(state)
        self.state = state


class BankRequiredError(ValueError):
    """A virtual account payment needs one of the supported banks."""


class MethodNotAllowedError(ValueError):
    """This link does not accept the chosen payment method."""


class NoOpenPaymentError(Exception):
    """Nothing to simulate: the guest has not chosen a payment method yet."""


class ManualTransferUnavailableError(Exception):
    """The property has not given bank details, so it takes no manual transfers."""


class TooManyAttemptsError(Exception):
    """This link has used up its payment attempts (guards the gateway from a token holder)."""


class GatewayUnavailableError(Exception):
    """The gateway could not give payment instructions; the attempt is kept as failed."""


async def find_link(scope: PublicLinkScope, *, lock: bool = False) -> PaymentLink:
    statement = select(PaymentLink).where(
        col(PaymentLink.tenant_id) == scope.tenant_id,
        col(PaymentLink.token_hash) == scope.token_hash,
    )
    if lock:
        statement = statement.with_for_update()
    link = (await scope.session.exec(statement)).first()
    if link is None:
        raise PublicLinkNotFoundError
    return link


def _instructions(payment: Payment) -> PaymentInstructions | None:
    details = payment.metadata_ or {}
    if not payment.gateway_reference:
        return None
    return PaymentInstructions(
        reference=payment.gateway_reference,
        method=payment.method,
        qris_payload=details.get("qris_payload"),
        va_bank=details.get("va_bank"),
        va_number=details.get("va_number"),
    )


async def _latest_pending(
    session: AsyncSession, link: PaymentLink, reference: str | None = None
) -> Payment | None:
    """The link's newest open attempt that has instructions (or the one named `reference`)."""
    statement = select(Payment).where(
        col(Payment.tenant_id) == link.tenant_id,
        col(Payment.payment_link_id) == link.id,
        col(Payment.status) == "pending",
        col(Payment.gateway_reference).is_not(None),
    )
    if reference is not None:
        statement = statement.where(col(Payment.gateway_reference) == reference)
    statement = statement.order_by(col(Payment.created_at).desc(), col(Payment.id).desc())
    return (await session.exec(statement.limit(1))).first()


def _manual_transfer(prop: Property) -> ManualTransfer | None:
    settings = resolve_property_settings(prop.settings)
    account = bank_account(settings)
    if account is None:
        return None
    return ManualTransfer(
        bank_name=account.bank_name,
        account_number=account.account_number,
        account_holder=account.account_holder,
        max_upload_mb=settings.proof_max_upload_mb,
    )


async def submit_proof(
    scope: PublicLinkScope, storage: DocumentStorage, upload: ProofUpload
) -> PublicPaymentLink:
    """A guest uploads a transfer screenshot for their link (consent already checked)."""
    session = scope.session
    link = await find_link(scope, lock=True)
    prop = (
        await session.exec(
            select(Property).where(
                col(Property.tenant_id) == scope.tenant_id, col(Property.id) == link.property_id
            )
        )
    ).one()
    if _manual_transfer(prop) is None:
        await session.rollback()
        raise ManualTransferUnavailableError
    await submit_for_link(session, storage, link, prop, upload, by_guest=True, uploaded_by=None)
    return await public_view(scope)


async def property_upload_limit_mb(scope: PublicLinkScope) -> int:
    """The largest proof image this link's property accepts."""
    link = await find_link(scope)
    prop = (
        await scope.session.exec(
            select(Property).where(
                col(Property.tenant_id) == scope.tenant_id, col(Property.id) == link.property_id
            )
        )
    ).one()
    return resolve_property_settings(prop.settings).proof_max_upload_mb


async def public_view(scope: PublicLinkScope) -> PublicPaymentLink:
    """What the pay page shows. No ids, no guest details."""
    session = scope.session
    link = await find_link(scope)
    prop = (
        await session.exec(
            select(Property).where(
                col(Property.tenant_id) == scope.tenant_id, col(Property.id) == link.property_id
            )
        )
    ).one()
    now = dt.datetime.now(dt.UTC)
    payable = effective_status(link, now) == "active"
    pending = await _latest_pending(session, link) if payable else None
    return PublicPaymentLink(
        property_name=prop.name,
        description=link.description,
        amount=money(link.amount),
        total_amount=money(link.deposit_of_total) if link.deposit_of_total is not None else None,
        currency=link.currency,
        expires_at=link.expires_at,
        state=state_for_people(link, now),  # type: ignore[arg-type]
        paid_at=link.paid_at,
        methods=list(link.allowed_methods),
        banks=list(VA_BANKS),
        instructions=_instructions(pending) if pending else None,
        simulator_enabled=app_settings.PAYMENT_SIMULATOR_ENABLED,
        manual_transfer=_manual_transfer(prop) if payable else None,
        proof=await latest_public_proof(session, link) if payable else None,
    )


async def _existing_attempts(
    session: AsyncSession, link: PaymentLink, method: str, bank: str | None
) -> list[Payment]:
    statement = select(Payment).where(
        col(Payment.tenant_id) == link.tenant_id,
        col(Payment.payment_link_id) == link.id,
        col(Payment.method) == method,
    )
    statement = (
        statement.where(col(Payment.method_detail).is_(None))
        if bank is None
        else statement.where(col(Payment.method_detail) == bank)
    )
    return list((await session.exec(statement.order_by(col(Payment.created_at)))).all())


async def _attempt_count(session: AsyncSession, link: PaymentLink) -> int:
    statement = (
        select(func.count())
        .select_from(Payment)
        .where(
            col(Payment.tenant_id) == link.tenant_id,
            col(Payment.payment_link_id) == link.id,
            # transfer proofs have their own cap and never reach the gateway
            col(Payment.method) != BANK_TRANSFER,
        )
    )
    return int((await session.exec(statement)).one())


async def _record_attempt(
    scope: PublicLinkScope, method: str, bank: str | None
) -> tuple[Payment, PaymentGatewayAccount | None, PaymentLink]:
    """Under the link's row lock: reuse the open attempt for this method or record a new one.

    Returns the gateway account only when the gateway still has to be asked.
    Commits (releases the lock).
    """
    session = scope.session
    link = await find_link(scope, lock=True)
    status = effective_status(link, dt.datetime.now(dt.UTC))
    if status != "active":
        if status == "expired" and link.status == "active":
            link.status = "expired"
            session.add(link)
            await cancel_pending_payments(session, link)
            await session.commit()
        else:
            await session.rollback()
        raise LinkNotPayableError({"active": "pending"}.get(status, status))
    if method not in link.allowed_methods:
        await session.rollback()
        raise MethodNotAllowedError

    attempts = await _existing_attempts(session, link, method, bank)
    open_attempt = next((p for p in attempts if p.status == "pending"), None)
    if open_attempt is not None:
        # One open attempt per method: a double-tap or a second tab reuses it instead of
        # creating a second charge. If it has no instructions yet (another request is
        # asking the gateway right now), ask again — the gateway call is keyed on the
        # payment id, so both get the same charge.
        account = None
        if not open_attempt.gateway_reference:
            account = (
                await session.exec(
                    select(PaymentGatewayAccount).where(
                        col(PaymentGatewayAccount.tenant_id) == scope.tenant_id,
                        col(PaymentGatewayAccount.id) == open_attempt.gateway_account_id,
                    )
                )
            ).one()
        await session.commit()
        return open_attempt, account, link
    if await _attempt_count(session, link) >= MAX_ATTEMPTS_PER_LINK:
        await session.rollback()
        raise TooManyAttemptsError

    prop = (
        await session.exec(
            select(Property).where(
                col(Property.tenant_id) == scope.tenant_id, col(Property.id) == link.property_id
            )
        )
    ).one()
    account = await get_or_create_gateway_account(session, prop)
    payment = Payment(
        tenant_id=scope.tenant_id,
        property_id=link.property_id,
        gateway_account_id=account.id,
        payment_link_id=link.id,
        direction="inbound",
        method=method,
        method_detail=bank,
        status="pending",
        amount=link.amount,
        currency=link.currency,
        idempotency_key=f"link:{link.id}:{method}:{bank or '-'}:{len(attempts)}",
    )
    session.add(payment)
    await session.commit()
    return payment, account, link


async def _ask_gateway(
    account: PaymentGatewayAccount, payment: Payment, link: PaymentLink
) -> ChargeInstructions:
    return await get_gateway(account.provider).create_charge(
        ChargeRequest(
            reference=str(payment.id),
            amount=payment.amount,
            currency=payment.currency,
            method=payment.method,
            bank=payment.method_detail,
            description=link.description or "",
            expires_at=link.expires_at,
        )
    )


async def start_payment(
    scope: PublicLinkScope, method: str, bank: str | None
) -> PaymentInstructions:
    """Give the guest instructions for `method`. Asking again returns the same ones."""
    if method == VIRTUAL_ACCOUNT and bank not in VA_BANKS:
        raise BankRequiredError("choose a bank for the virtual account")
    if method != VIRTUAL_ACCOUNT:
        bank = None

    payment, account, link = await _record_attempt(scope, method, bank)
    if account is None:
        return _instructions(payment)  # type: ignore[return-value]

    session = scope.session
    try:
        charge = await _ask_gateway(account, payment, link)
    except Exception as exc:  # noqa: BLE001 — any gateway fault must leave a record
        if not isinstance(exc, GatewayError):
            log.exception("Gateway call failed payment=%s", payment.id)
        payment.status = "failed"
        payment.failure_reason = "gateway_unavailable"
        session.add(payment)
        await session.commit()
        raise GatewayUnavailableError from None

    payment.gateway_reference = charge.gateway_reference
    payment.metadata_ = {
        "qris_payload": charge.qris_payload,
        "va_bank": charge.va_bank,
        "va_number": charge.va_number,
    }
    session.add(payment)
    await session.commit()
    log.info("Payment attempt ready payment=%s method=%s", payment.id, payment.method)
    return _instructions(payment)  # type: ignore[return-value]


async def payment_awaiting_simulation(
    scope: PublicLinkScope, reference: str | None = None
) -> tuple[Payment, UUID]:
    """The open attempt a simulated "paid" notice should target, and its gateway account.

    `reference` names the attempt the guest is looking at; without it, the latest one.
    """
    link = await find_link(scope)
    status = effective_status(link, dt.datetime.now(dt.UTC))
    if status != "active":
        raise LinkNotPayableError({"active": "pending"}.get(status, status))
    payment = await _latest_pending(scope.session, link, reference)
    if payment is None or payment.gateway_account_id is None:
        raise NoOpenPaymentError
    return payment, payment.gateway_account_id
