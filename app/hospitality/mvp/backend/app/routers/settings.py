"""Property settings routes.

GET /api/settings/bank-account     where guests send a manual transfer (any member)
PUT /api/settings/bank-account     set or clear it (property owner only)
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel.ext.asyncio.session import AsyncSession

from app.schemas.transfer_proofs import BankAccountRead, BankAccountUpdate
from app.services import property_settings
from app.services.workspace import find_property
from app.tenancy.context import TenantContext, get_tenant_context
from app.tenancy.session import get_tenant_session

settings_router = APIRouter(prefix="/api/settings", tags=["settings"])


@settings_router.get("/bank-account", response_model=BankAccountRead)
async def read_bank_account(
    context: TenantContext = Depends(get_tenant_context),
    session: AsyncSession = Depends(get_tenant_session),
) -> BankAccountRead:
    prop = await find_property(session, context)
    return property_settings.read_bank_account(prop, context)


@settings_router.put("/bank-account", response_model=BankAccountRead)
async def update_bank_account(
    body: BankAccountUpdate,
    context: TenantContext = Depends(get_tenant_context),
    session: AsyncSession = Depends(get_tenant_session),
) -> BankAccountRead:
    prop = await find_property(session, context)
    try:
        return await property_settings.update_bank_account(session, context, prop, body)
    except property_settings.OwnerOnlyError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the property owner can change the bank account.",
        ) from None
    except property_settings.IncompleteBankAccountError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                "Fill in the bank, the account number and the account holder, "
                "or leave all three empty."
            ),
        ) from None
