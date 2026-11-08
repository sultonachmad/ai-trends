"""Sample protected routes — demonstrates session-based auth guard.

Every route in this router requires an active session. Unauthenticated
requests receive a 401 response. Delete this file once you've built your
own protected routes — it exists only as a working reference.
"""

from fastapi import APIRouter, Depends

from app.session.dependencies import get_current_user

router = APIRouter(prefix="/protected", tags=["protected"])


@router.get("/profile")
async def get_profile(user=Depends(get_current_user)) -> dict:
    """Return the current user's profile from the session."""
    return {
        "message": "You are authenticated",
        "user": user,
    }


@router.get("/dashboard-data")
async def get_dashboard_data(user=Depends(get_current_user)) -> dict:
    """Sample endpoint that returns data only for logged-in users."""
    return {
        "greeting": f"Welcome back, {user.get('email', 'user')}",
        "items_count": 42,
    }
