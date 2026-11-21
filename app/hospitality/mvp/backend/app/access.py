"""One rule for which check guards a prefab route (ADR-0058).

`require_access(code, description)` returns a FastAPI `Depends`. Which check it is depends on
what the app installed, decided once when this module is imported:

- rbac installed: rbac's `require_permission(code, description)` (the code is also seeded);
- else auth-session installed: a session, `Depends(get_current_user)` (401 without one);
- else: nothing. The app has no login, so there is no session to check (leave-open,
  ADR-0058 Decision 2).

Presence is probed on the package with `find_spec`, never with `except ImportError`: an
import error inside an installed rbac must stop the app, not drop it to login only.
"""

import importlib.util
from typing import Any

from fastapi import Depends

FEATURES_USE = "features:use"
FEATURES_USE_DESCRIPTION = "Use the sample features (RAG, LLM, email, extract, upload, sample items)"
FEATURES_DELETE = "features:delete"
FEATURES_DELETE_DESCRIPTION = "Delete data through the sample features"


async def _allow() -> None:
    """No login prefab is installed: let the request through."""
    return None


if importlib.util.find_spec("app.rbac") is not None:
    from app.rbac.dependencies import require_permission

    def require_access(code: str, description: str) -> Any:
        """Check `code` through rbac (and register it for the startup seed)."""
        return require_permission(code, description)

elif importlib.util.find_spec("app.session") is not None:
    from app.session.dependencies import get_current_user

    def require_access(code: str, description: str) -> Any:
        """No rbac: a session is enough."""
        return Depends(get_current_user)

else:

    def require_access(code: str, description: str) -> Any:
        """No login: nothing to check."""
        return Depends(_allow)
