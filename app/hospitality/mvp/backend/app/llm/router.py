import logging

import litellm
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.access import FEATURES_USE, FEATURES_USE_DESCRIPTION, require_access
from app.config import settings

log = logging.getLogger(__name__)

# Every endpoint checks features:use through app.access (ADR-0058): rbac's permission when
# rbac is installed, else the session (auth-session is a hard `requires` of this prefab).
router = APIRouter(
    prefix="/api/llm",
    tags=["llm"],
    dependencies=[require_access(FEATURES_USE, FEATURES_USE_DESCRIPTION)],
)


class Message(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    model: str | None = None
    messages: list[Message]
    max_tokens: int = 1000


class UsageInfo(BaseModel):
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


class ChatResponse(BaseModel):
    content: str
    model: str
    usage: UsageInfo | None = None


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    """Send messages to the configured LLM and return the completion."""
    try:
        response = await litellm.acompletion(
            model=request.model or settings.LLM_MODEL,
            messages=[msg.model_dump() for msg in request.messages],
            max_tokens=request.max_tokens,
        )
        usage = None
        if response.usage:
            usage = UsageInfo(
                prompt_tokens=response.usage.prompt_tokens,
                completion_tokens=response.usage.completion_tokens,
                total_tokens=response.usage.total_tokens,
            )
        return ChatResponse(
            content=response.choices[0].message.content,
            model=response.model,
            usage=usage,
        )
    except Exception:
        log.exception("LLM chat request failed")
        raise HTTPException(status_code=502, detail="LLM request failed")
