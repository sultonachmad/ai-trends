"""Workspace route — the signed-in operator's property, plan and usage.

GET /api/workspace
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel.ext.asyncio.session import AsyncSession

from app.schemas.workspace import WorkspaceRead
from app.services.workspace import WorkspaceNotReadyError, get_workspace
from app.tenancy.business_settings import BusinessSettingsError
from app.tenancy.context import TenantContext, get_tenant_context
from app.tenancy.session import get_tenant_session

log = logging.getLogger(__name__)

workspace_router = APIRouter(prefix="/api/workspace", tags=["workspace"])


async def read_workspace_or_500(session: AsyncSession, context: TenantContext) -> WorkspaceRead:
    """The workspace summary; known data faults become a 500 that says what to fix."""
    try:
        return await get_workspace(session, context)
    except BusinessSettingsError:
        log.exception("Invalid stored business settings for tenant %s", context.tenant_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="This workspace has an invalid setting. Please contact support.",
        ) from None
    except WorkspaceNotReadyError:
        log.exception("Incomplete workspace data for tenant %s", context.tenant_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="This workspace is not fully set up. Please contact support.",
        ) from None


@workspace_router.get("", response_model=WorkspaceRead)
async def read_workspace(
    context: TenantContext = Depends(get_tenant_context),
    session: AsyncSession = Depends(get_tenant_session),
) -> WorkspaceRead:
    return await read_workspace_or_500(session, context)
