"""Property settings routes.

GET /api/settings/bank-account     where guests send a manual transfer (any member)
PUT /api/settings/bank-account     set or clear it (property owner only)
GET /api/settings/booking-terms    deposit share for direct bookings (any member)
PUT /api/settings/booking-terms    change it (property owner only)
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel.ext.asyncio.session import AsyncSession

from app.rbac.dependencies import require_permission
from app.schemas.property_settings import BookingTermsRead, BookingTermsUpdate
from app.schemas.taxes import TaxSettingsRead, TaxSettingsUpdate
from app.schemas.transfer_proofs import BankAccountRead, BankAccountUpdate
from app.services import property_settings, tax_rules
from app.services.workspace import find_property
from app.tenancy.context import TenantContext, get_tenant_context
from app.tenancy.session import get_tenant_session

VIEW = require_permission("settings:view", "See property settings")

EDIT = require_permission("settings:edit", "Change property settings")

settings_router = APIRouter(prefix="/api/settings", tags=["settings"])


@settings_router.get("/bank-account", response_model=BankAccountRead)
async def read_bank_account(
    context: TenantContext = Depends(get_tenant_context),
    session: AsyncSession = Depends(get_tenant_session),
    _view=VIEW,
) -> BankAccountRead:
    prop = await find_property(session, context)
    return property_settings.read_bank_account(prop, context)


@settings_router.put("/bank-account", response_model=BankAccountRead)
async def update_bank_account(
    body: BankAccountUpdate,
    context: TenantContext = Depends(get_tenant_context),
    session: AsyncSession = Depends(get_tenant_session),
    _edit=EDIT,
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


@settings_router.get("/booking-terms", response_model=BookingTermsRead)
async def read_booking_terms(
    context: TenantContext = Depends(get_tenant_context),
    session: AsyncSession = Depends(get_tenant_session),
    _view=VIEW,
) -> BookingTermsRead:
    prop = await find_property(session, context)
    return property_settings.read_booking_terms(prop, context)


@settings_router.put("/booking-terms", response_model=BookingTermsRead)
async def update_booking_terms(
    body: BookingTermsUpdate,
    context: TenantContext = Depends(get_tenant_context),
    session: AsyncSession = Depends(get_tenant_session),
    _edit=EDIT,
) -> BookingTermsRead:
    prop = await find_property(session, context)
    try:
        return await property_settings.update_booking_terms(session, context, prop, body)
    except property_settings.OwnerOnlyError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the property owner can change the booking terms.",
        ) from None


@settings_router.get("/taxes", response_model=TaxSettingsRead)
async def read_taxes(
    context: TenantContext = Depends(get_tenant_context),
    session: AsyncSession = Depends(get_tenant_session),
    _view=VIEW,
) -> TaxSettingsRead:
    prop = await find_property(session, context)
    return await tax_rules.read_settings(session, context, prop)


@settings_router.put("/taxes", response_model=TaxSettingsRead)
async def update_taxes(
    body: TaxSettingsUpdate,
    context: TenantContext = Depends(get_tenant_context),
    session: AsyncSession = Depends(get_tenant_session),
    _edit=EDIT,
) -> TaxSettingsRead:
    prop = await find_property(session, context)
    try:
        return await tax_rules.save_settings(session, context, prop, body)
    except tax_rules.TaxOwnerOnlyError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the property owner can change taxes.",
        ) from None
    except tax_rules.TaxDateError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="New rates can start today or within a year.",
        ) from None
