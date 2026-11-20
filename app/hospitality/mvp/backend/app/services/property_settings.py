"""Reading and changing a property's bank account details (manual transfer)."""

import logging

from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.tenant import Property
from app.schemas.property_settings import BookingTermsRead, BookingTermsUpdate
from app.schemas.transfer_proofs import BankAccountRead, BankAccountUpdate
from app.tenancy.business_settings import resolve_property_settings, with_property_overrides
from app.tenancy.context import TenantContext

log = logging.getLogger(__name__)


class OwnerOnlyError(PermissionError):
    """Only the property owner may change this."""


class IncompleteBankAccountError(ValueError):
    """Bank name, account number and holder must be given together."""


def read_bank_account(prop: Property, context: TenantContext) -> BankAccountRead:
    settings = resolve_property_settings(prop.settings)
    return BankAccountRead(
        bank_name=settings.bank_name,
        account_number=settings.bank_account_number,
        account_holder=settings.bank_account_holder,
        can_edit=context.is_owner,
    )


async def update_bank_account(
    session: AsyncSession, context: TenantContext, prop: Property, update: BankAccountUpdate
) -> BankAccountRead:
    """Set or clear the bank details. Owner only. Commits."""
    if not context.is_owner:
        raise OwnerOnlyError
    values = (update.bank_name, update.account_number, update.account_holder)
    if any(values) and not all(values):
        raise IncompleteBankAccountError
    locked = await _save_overrides(
        session,
        context,
        prop,
        {
            "bank_name": update.bank_name,
            "bank_account_number": update.account_number,
            "bank_account_holder": update.account_holder,
        },
    )
    log.info("Bank account details changed property=%s by user=%s", locked.id, context.user_id)
    return read_bank_account(locked, context)


async def _save_overrides(
    session: AsyncSession, context: TenantContext, prop: Property, changes: dict[str, object]
) -> Property:
    """Merge `changes` into the property's business settings under its row lock. Commits."""
    locked = (
        await session.exec(
            select(Property)
            .where(col(Property.tenant_id) == context.tenant_id, col(Property.id) == prop.id)
            .with_for_update()
        )
    ).one()
    locked.settings = with_property_overrides(locked.settings, changes)
    session.add(locked)
    await session.commit()
    return locked


def read_booking_terms(prop: Property, context: TenantContext) -> BookingTermsRead:
    settings = resolve_property_settings(prop.settings)
    return BookingTermsRead(
        deposit_percent=settings.direct_deposit_percent, can_edit=context.is_owner
    )


async def update_booking_terms(
    session: AsyncSession, context: TenantContext, prop: Property, update: BookingTermsUpdate
) -> BookingTermsRead:
    """Set the deposit share for direct bookings. Owner only. Commits."""
    if not context.is_owner:
        raise OwnerOnlyError
    locked = await _save_overrides(
        session, context, prop, {"direct_deposit_percent": update.deposit_percent}
    )
    log.info("Booking terms changed property=%s by user=%s", locked.id, context.user_id)
    return read_booking_terms(locked, context)
