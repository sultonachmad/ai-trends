"""The cancellation and payment terms records a rate plan points at.

Staff choose between "free cancellation until N days before arrival" and
"non-refundable". Each distinct choice is one `cancellationpolicy` row per property,
found or created on demand and shared by every plan with the same terms. All plans of
a property share one deposit `paymentpolicy`; the deposit share itself is a property
setting, read when a booking is made.
"""

from dataclasses import dataclass
from uuid import UUID

from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.tenant import CancellationPolicy, PaymentPolicy
from app.tenancy.context import TenantContext

NON_REFUNDABLE_CODE = "non_refundable"
DEPOSIT_CODE = "deposit"
FULL_REFUND_PERCENT = 100


@dataclass(frozen=True)
class CancellationTerms:
    """What staff chose. `free_days` is None exactly when the plan is non-refundable."""

    non_refundable: bool
    free_days: int | None


def terms_of(policy: CancellationPolicy) -> CancellationTerms:
    """Read the staff-facing terms back from a stored policy."""
    if policy.is_non_refundable:
        return CancellationTerms(non_refundable=True, free_days=None)
    first_rule = policy.rules[0] if policy.rules else {}
    return CancellationTerms(
        non_refundable=False, free_days=int(first_rule.get("days_before_arrival", 0))
    )


def _policy_for(terms: CancellationTerms, tenant_id: UUID, property_id: UUID) -> CancellationPolicy:
    if terms.non_refundable:
        return CancellationPolicy(
            tenant_id=tenant_id,
            property_id=property_id,
            code=NON_REFUNDABLE_CODE,
            name="Non-refundable",
            is_non_refundable=True,
        )
    return CancellationPolicy(
        tenant_id=tenant_id,
        property_id=property_id,
        code=f"free_until_{terms.free_days}d",
        name=f"Free cancellation until {terms.free_days} days before arrival",
        rules=[{"days_before_arrival": terms.free_days, "refund_percent": FULL_REFUND_PERCENT}],
    )


async def cancellation_policy_for(
    session: AsyncSession, context: TenantContext, property_id: UUID, terms: CancellationTerms
) -> CancellationPolicy:
    """The property's policy row for these terms, created on first use (flushed, not committed).

    The caller holds the property's row lock, so two requests cannot create it twice.
    """
    wanted = _policy_for(terms, context.tenant_id, property_id)
    existing = (
        await session.exec(
            select(CancellationPolicy).where(
                col(CancellationPolicy.tenant_id) == context.tenant_id,
                col(CancellationPolicy.property_id) == property_id,
                col(CancellationPolicy.code) == wanted.code,
            )
        )
    ).first()
    if existing is not None:
        return existing
    session.add(wanted)
    await session.flush()
    return wanted


async def deposit_policy_for(
    session: AsyncSession, context: TenantContext, property_id: UUID
) -> PaymentPolicy:
    """The property's deposit payment policy, created on first use (flushed, not committed)."""
    existing = (
        await session.exec(
            select(PaymentPolicy).where(
                col(PaymentPolicy.tenant_id) == context.tenant_id,
                col(PaymentPolicy.property_id) == property_id,
                col(PaymentPolicy.code) == DEPOSIT_CODE,
            )
        )
    ).first()
    if existing is not None:
        return existing
    policy = PaymentPolicy(
        tenant_id=context.tenant_id,
        property_id=property_id,
        code=DEPOSIT_CODE,
        name="Deposit when booking, balance at the property",
        guarantee_kind="deposit",
    )
    session.add(policy)
    await session.flush()
    return policy


async def policies_by_id(
    session: AsyncSession, context: TenantContext, policy_ids: set[UUID]
) -> dict[UUID, CancellationPolicy]:
    if not policy_ids:
        return {}
    rows = await session.exec(
        select(CancellationPolicy).where(
            col(CancellationPolicy.tenant_id) == context.tenant_id,
            col(CancellationPolicy.id).in_(policy_ids),
        )
    )
    return {policy.id: policy for policy in rows.all()}
