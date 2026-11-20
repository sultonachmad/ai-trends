"""Inbox routes — the caller's property conversations.

GET  /api/inbox/summary
GET  /api/conversations?status=open|resolved&limit=&cursor=
GET  /api/conversations/{id}
GET  /api/conversations/{id}/messages?after=<message id>
POST /api/conversations/{id}/messages      reply
POST /api/conversations/{id}/read
POST /api/conversations/{id}/resolve
POST /api/conversations/{id}/reopen
"""

from collections.abc import Awaitable, Callable
from typing import TypeVar
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlmodel.ext.asyncio.session import AsyncSession

from app.rbac.dependencies import require_permission
from app.schemas.inbox import (
    ConversationFilter,
    ConversationPage,
    ConversationRead,
    InboxSummary,
    MessageRead,
    ReplyRequest,
)
from app.services import inbox
from app.services.workspace import find_property, unread_conversation_count
from app.tenancy.context import TenantContext, get_tenant_context
from app.tenancy.session import get_tenant_session

VIEW = require_permission("inbox:view", "Read guest conversations")

EDIT = require_permission("inbox:edit", "Reply to guests and manage conversations")

inbox_router = APIRouter(tags=["inbox"])

NOT_FOUND = "Conversation not found"
T = TypeVar("T")


async def _guarded(call: Callable[[], Awaitable[T]]) -> T:
    """Run an inbox service call, turning its domain errors into HTTP answers."""
    try:
        return await call()
    except inbox.ConversationNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=NOT_FOUND) from None
    except inbox.ConversationResolvedError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This conversation is resolved. Reopen it to reply.",
        ) from None
    except inbox.ReplyWindowClosedError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "WhatsApp's 24-hour reply window has closed. "
                "You can reply again once the guest sends a new message."
            ),
        ) from None
    except inbox.ReopenConflictError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This guest already has a newer open conversation.",
        ) from None
    except inbox.InvalidCursorError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid cursor"
        ) from None


@inbox_router.get("/api/inbox/summary", response_model=InboxSummary)
async def inbox_summary(
    context: TenantContext = Depends(get_tenant_context),
    session: AsyncSession = Depends(get_tenant_session),
    _view=VIEW,
) -> InboxSummary:
    prop = await find_property(session, context)
    return InboxSummary(
        unread_conversations=await unread_conversation_count(session, context, prop.id)
    )


@inbox_router.get("/api/conversations", response_model=ConversationPage)
async def list_conversations(
    status_filter: ConversationFilter = Query(default="open", alias="status"),
    limit: int = Query(default=inbox.DEFAULT_PAGE_SIZE, ge=1, le=inbox.MAX_PAGE_SIZE),
    cursor: str | None = Query(default=None, max_length=100),
    context: TenantContext = Depends(get_tenant_context),
    session: AsyncSession = Depends(get_tenant_session),
    _view=VIEW,
) -> ConversationPage:
    prop = await find_property(session, context)
    return await _guarded(
        lambda: inbox.list_conversations(session, context, prop.id, status_filter, limit, cursor)
    )


@inbox_router.get("/api/conversations/{conversation_id}", response_model=ConversationRead)
async def read_conversation(
    conversation_id: UUID,
    context: TenantContext = Depends(get_tenant_context),
    session: AsyncSession = Depends(get_tenant_session),
    _view=VIEW,
) -> ConversationRead:
    prop = await find_property(session, context)
    return await _guarded(
        lambda: inbox.read_conversation(session, context, prop.id, conversation_id)
    )


@inbox_router.get("/api/conversations/{conversation_id}/messages", response_model=list[MessageRead])
async def list_messages(
    conversation_id: UUID,
    after: UUID | None = Query(default=None, description="Only messages newer than this one"),
    context: TenantContext = Depends(get_tenant_context),
    session: AsyncSession = Depends(get_tenant_session),
    _view=VIEW,
) -> list[MessageRead]:
    prop = await find_property(session, context)
    return await _guarded(
        lambda: inbox.list_messages(session, context, prop.id, conversation_id, after)
    )


@inbox_router.post(
    "/api/conversations/{conversation_id}/messages",
    response_model=MessageRead,
    status_code=status.HTTP_201_CREATED,
)
async def reply(
    conversation_id: UUID,
    body: ReplyRequest,
    context: TenantContext = Depends(get_tenant_context),
    session: AsyncSession = Depends(get_tenant_session),
    _edit=EDIT,
) -> MessageRead:
    prop = await find_property(session, context)
    return await _guarded(
        lambda: inbox.send_reply(session, context, prop.id, conversation_id, body.body)
    )


@inbox_router.post("/api/conversations/{conversation_id}/read", response_model=ConversationRead)
async def mark_read(
    conversation_id: UUID,
    context: TenantContext = Depends(get_tenant_context),
    session: AsyncSession = Depends(get_tenant_session),
    _view=VIEW,
) -> ConversationRead:
    prop = await find_property(session, context)
    return await _guarded(lambda: inbox.mark_read(session, context, prop.id, conversation_id))


@inbox_router.post("/api/conversations/{conversation_id}/resolve", response_model=ConversationRead)
async def resolve(
    conversation_id: UUID,
    context: TenantContext = Depends(get_tenant_context),
    session: AsyncSession = Depends(get_tenant_session),
    _edit=EDIT,
) -> ConversationRead:
    prop = await find_property(session, context)
    return await _guarded(
        lambda: inbox.set_resolved(session, context, prop.id, conversation_id, resolved=True)
    )


@inbox_router.post("/api/conversations/{conversation_id}/reopen", response_model=ConversationRead)
async def reopen(
    conversation_id: UUID,
    context: TenantContext = Depends(get_tenant_context),
    session: AsyncSession = Depends(get_tenant_session),
    _edit=EDIT,
) -> ConversationRead:
    prop = await find_property(session, context)
    return await _guarded(
        lambda: inbox.set_resolved(session, context, prop.id, conversation_id, resolved=False)
    )
