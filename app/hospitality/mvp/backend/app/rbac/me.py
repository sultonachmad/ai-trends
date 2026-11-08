"""GET /api/me — single source of truth for the logged-in user's RBAC context.

After login the frontend fetches this endpoint once and stores the result in
`RbacProvider`. Everything the frontend needs to make access decisions — role
names, permission codes, and the nav menu items to render — is returned here.
The frontend NEVER computes privilege itself; it only reads from this payload.

Menus are loaded from ``backend/docs/rbac-spec.yaml`` (not from the database).
To add, remove, or reorder menu items, edit that file and restart the server,
or call ``POST /api/me/reload-menus`` (needs the ``menus:reload`` permission).
Set ``active: false`` on a menu entry to hide it (useful for WIP features).
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import yaml
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlmodel.ext.asyncio.session import AsyncSession

from app.database import get_session
from app.rbac.dependencies import (
    _is_admin,
    get_user_permissions,
    get_user_roles,
    require_permission,
)
from app.session.dependencies import get_current_user

log = logging.getLogger(__name__)

me_router = APIRouter(tags=["me"])

# app/rbac/me.py -> parents[2] is the backend root: `<workspace>/backend`
# locally, `/app` in the preview/SIT container (its compose bind-mounts
# `backend/` there), and wherever the app's own Dockerfile copies `backend/`.
_BACKEND_ROOT = Path(__file__).resolve().parents[2]
_SPEC = _BACKEND_ROOT / "docs" / "rbac-spec.yaml"
# Pre-BDAI-1912 workspaces keep the spec at `<workspace>/docs/`. Still read it
# so their menus don't vanish, but warn. Only probed for a local
# `<workspace>/backend` root; in the container it sits outside the mount.
_LEGACY_SPEC = (
    _BACKEND_ROOT.parent / "docs" / "rbac-spec.yaml" if _BACKEND_ROOT.name == "backend" else None
)
_CWD_SPEC = Path("docs/rbac-spec.yaml")
_menu_cache: list[dict[str, Any]] | None = None


def _find_spec() -> Path | None:
    if _SPEC.is_file():
        return _SPEC
    # Legacy before the cwd fallback: run from the workspace root, the cwd
    # path IS the legacy file and must not load it without the warning.
    if _LEGACY_SPEC is not None and _LEGACY_SPEC.is_file():
        log.warning(
            "rbac-spec.yaml loaded from legacy path %s — move it to backend/docs/rbac-spec.yaml",
            _LEGACY_SPEC,
        )
        return _LEGACY_SPEC
    if _CWD_SPEC.is_file():
        return _CWD_SPEC
    return None


def _load_menus() -> list[dict[str, Any]]:
    """Read the menus section from rbac-spec.yaml (cached after first load)."""
    global _menu_cache
    if _menu_cache is not None:
        return _menu_cache
    spec_path = _find_spec()
    if spec_path is None:
        tried = [p for p in (_SPEC, _LEGACY_SPEC, _CWD_SPEC.resolve()) if p is not None]
        log.warning(
            "rbac-spec.yaml not found (tried %s) — no menus loaded", ", ".join(map(str, tried))
        )
        _menu_cache = []
        return _menu_cache
    log.info("Loading menus from %s", spec_path)
    with open(spec_path, encoding="utf-8") as f:
        spec = yaml.safe_load(f)
    _menu_cache = spec.get("menus") or []
    return _menu_cache


def _flatten_menus(
    groups: list[dict[str, Any]],
    permissions: list[str],
    is_admin: bool,
) -> list[dict[str, Any]]:
    """Flatten the nested yaml menu tree into a flat list for the frontend.

    Filters by ``active`` flag and permission codes. Admin users see all
    active menus regardless of permission. A top-level entry with its own
    ``permission`` is hidden from users who lack it, and so is everything
    under it (like ``active: false``): a child is shown only when the user
    holds both the group's and the child's permission. A parent group with
    children is included only if at least one of its children is visible.
    """
    result: list[dict[str, Any]] = []
    counter = 0

    for group in sorted(groups, key=lambda g: g.get("order", 0)):
        if not group.get("active", True):
            continue

        group_perm = group.get("permission")
        if group_perm and not is_admin and group_perm not in permissions:
            continue

        children_defs = group.get("children") or []
        visible_children: list[dict[str, Any]] = []

        for child in sorted(children_defs, key=lambda c: c.get("order", 0)):
            if not child.get("active", True):
                continue
            perm = child.get("permission")
            if perm and not is_admin and perm not in permissions:
                continue
            counter += 1
            visible_children.append({
                "id": counter,
                "name": child["name"],
                "path": child.get("path"),
                "icon": child.get("icon"),
                "order": child.get("order", 0),
                "parent_id": None,
            })

        if children_defs and not visible_children:
            continue

        counter += 1
        parent_id = counter
        result.append({
            "id": parent_id,
            "name": group["name"],
            "path": group.get("path"),
            "icon": group.get("icon"),
            "order": group.get("order", 0),
            "parent_id": None,
        })

        for child in visible_children:
            child["parent_id"] = parent_id
            result.append(child)

    return result


class MenuItem(BaseModel):
    id: int
    name: str
    path: str | None
    icon: str | None
    order: int
    parent_id: int | None


class MeResponse(BaseModel):
    id: int
    email: str
    roles: list[str]
    permissions: list[str]
    menus: list[MenuItem]


@me_router.get("/api/me", response_model=MeResponse)
async def get_me(
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
) -> MeResponse:
    user_id = int(user["user_id"])
    email = user.get("email", "")

    roles = await get_user_roles(user_id, db)
    permissions = await get_user_permissions(user_id, db)
    admin = await _is_admin(user_id, db)

    raw_menus = _load_menus()
    flat = _flatten_menus(raw_menus, permissions, admin)

    menus = [
        MenuItem(
            id=m["id"],
            name=m["name"],
            path=m["path"],
            icon=m["icon"],
            order=m["order"],
            parent_id=m["parent_id"],
        )
        for m in flat
    ]

    return MeResponse(
        id=user_id,
        email=email,
        roles=roles,
        permissions=permissions,
        menus=menus,
    )


@me_router.post("/api/me/reload-menus")
async def reload_menus(
    user: dict = require_permission("menus:reload", "Reload menus from rbac-spec.yaml"),
) -> dict[str, str]:
    """Force reload menus from rbac-spec.yaml (no restart required).

    Needs `menus:reload`; admins hold every permission.
    """
    global _menu_cache
    _menu_cache = None
    _load_menus()
    return {"status": "ok", "count": str(len(_menu_cache or []))}
