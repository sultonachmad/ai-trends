"""Auth routes: current-user lookup and standalone token verification."""

from typing import Annotated, Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.auth.dependencies import get_current_user
from app.auth.jwt import verify_token

router = APIRouter(prefix="/api/auth", tags=["auth"])


class TokenVerifyRequest(BaseModel):
    token: str


@router.get("/me")
async def get_me(user: Annotated[dict[str, Any], Depends(get_current_user)]) -> dict[str, Any]:
    """Return the current authenticated user's token payload."""
    return user


@router.post("/verify")
async def verify(body: TokenVerifyRequest) -> dict[str, Any]:
    """Verify an arbitrary token and return its decoded payload."""
    return verify_token(body.token)
