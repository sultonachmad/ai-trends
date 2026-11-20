"""Onboarding routes — a signed-in account creates its workspace.

GET  /api/onboarding/status   does this account have a workspace?
POST /api/onboarding          create it (once)
"""

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlmodel.ext.asyncio.session import AsyncSession

from app.database import get_session
from app.routers.workspace import read_workspace_or_500
from app.schemas.workspace import OnboardingRequest, OnboardingStatus, WorkspaceRead
from app.services.onboarding import (
    AccountNotFoundError,
    ProvisioningError,
    WorkspaceExistsError,
    create_workspace,
)
from app.session.dependencies import get_current_user
from app.tenancy.context import find_tenant_context

log = logging.getLogger(__name__)

onboarding_router = APIRouter(prefix="/api/onboarding", tags=["onboarding"])


@onboarding_router.get("/status", response_model=OnboardingStatus)
async def onboarding_status(
    user: dict[str, Any] = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> OnboardingStatus:
    context = await find_tenant_context(session, int(user["user_id"]), str(user.get("email", "")))
    return OnboardingStatus(has_workspace=context is not None)


@onboarding_router.post("", response_model=WorkspaceRead, status_code=status.HTTP_201_CREATED)
async def onboard(
    body: OnboardingRequest,
    user: dict[str, Any] = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> WorkspaceRead:
    try:
        context = await create_workspace(session, int(user["user_id"]), body)
    except WorkspaceExistsError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="This account already has a workspace"
        ) from None
    except AccountNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Account no longer exists"
        ) from None
    except IntegrityError:
        # e.g. two sign-ups raced for the same workspace code; nothing was saved.
        log.warning("Onboarding hit a uniqueness conflict for user_id=%s", user["user_id"])
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Could not create the workspace just now. Please try again.",
        ) from None
    except ProvisioningError:
        log.exception("Onboarding failed: platform seed data is missing")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Workspace setup is temporarily unavailable. Please try again later.",
        ) from None
    return await read_workspace_or_500(session, context)
