"""Reading and changing a property's bank account details (manual transfer)."""

import logging

from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.tenant import Property
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
    locked = (
        await session.exec(
            select(Property)
            .where(col(Property.tenant_id) == context.tenant_id, col(Property.id) == prop.id)
            .with_for_update()
        )
    ).one()
    locked.settings = with_property_overrides(
        locked.settings,
        {
            "bank_name": update.bank_name,
            "bank_account_number": update.account_number,
            "bank_account_holder": update.account_holder,
        },
    )
    session.add(locked)
    await session.commit()
    log.info("Bank account details changed property=%s by user=%s", locked.id, context.user_id)
    return read_bank_account(locked, context)
