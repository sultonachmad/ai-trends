"""FastAPI dependencies for session-based authentication.

Usage in any route handler:

    from app.session.dependencies import get_current_user

    @router.get("/my-stuff")
    async def my_stuff(user=Depends(get_current_user)):
        return {"message": f"Hello {user['email']}"}

The session middleware (installed by this prefab) resolves the session cookie
into ``request.state.user`` on every request. This dependency wraps that into
a standard ``Depends(...)`` so protected routes follow the same pattern as
auth-oauth2's JWT-based ``get_current_user``.
"""

from typing import Any

from fastapi import HTTPException, Request, status


async def get_current_user(request: Request) -> dict[str, Any]:
    """Return the authenticated user from the session, or raise 401."""
    user = getattr(request.state, "user", None)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )
    return user
