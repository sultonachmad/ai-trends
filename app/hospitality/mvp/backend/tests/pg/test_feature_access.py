"""Feature access runs through RBAC permissions: configured roles decide who sees and does what."""

import pytest
from sqlalchemy import text

from tests.pg.conftest import add_staff_member, start_workspace

pytestmark = pytest.mark.integration

# a sample of routes per module: (method, path, code needed)
VIEW_ROUTES = [
    ("get", "/api/room-types"),
    ("get", "/api/rate-plans"),
    ("get", "/api/calendar?from=2030-01-01&to=2030-01-02"),
    ("get", "/api/bookings?tab=upcoming"),
    ("get", "/api/payment-links"),
    ("get", "/api/transfer-proofs"),
    ("get", "/api/channels"),
    ("get", "/api/settings/bank-account"),
    ("get", "/api/conversations"),
]
EDIT_ROUTES = [
    ("post", "/api/room-types", {"name": "X", "kind": "room", "units": 1, "max_guests": 2}),
    ("post", "/api/calendar/changes", None),  # body wrong on purpose: 422 proves we got in
    ("post", "/api/bookings/quote", None),
    ("post", "/api/payment-links", None),
    ("post", "/api/transfer-proofs", None),
    ("post", "/api/channel-connections", None),
    ("put", "/api/settings/bank-account", {}),
]


async def _call(client, method, path, body):
    return await getattr(client, method)(path, json=body)


async def _give_role(session, user_id: int, name: str, codes: list[str]) -> None:
    """Create (or reuse) a role with exactly `codes` and assign it to the user."""
    await session.execute(
        text(
            "INSERT INTO role (created_at, updated_at, created_by, updated_by, name, description) "
            "VALUES (now(), now(), 'test', 'test', :n, 'test role') "
            "ON CONFLICT DO NOTHING"
        ),
        {"n": name},
    )
    role_id = (
        await session.execute(text("SELECT id FROM role WHERE name = :n"), {"n": name})
    ).scalar_one()
    for code in codes:
        await session.execute(
            text(
                "INSERT INTO role_permissions (role_id, permission_id) "
                "SELECT :r, id FROM permission WHERE code = :c "
                "ON CONFLICT DO NOTHING"
            ),
            {"r": role_id, "c": code},
        )
    await session.execute(
        text("INSERT INTO user_roles (user_id, role_id) VALUES (:u, :r) ON CONFLICT DO NOTHING"),
        {"u": user_id, "r": role_id},
    )
    await session.commit()


async def test_the_owner_who_creates_the_workspace_is_manager(pg_client, pg_session) -> None:
    workspace = await start_workspace(pg_client)
    owner_id = (
        await pg_session.execute(
            text("SELECT user_id FROM tenantmembership WHERE tenant_id = :t AND is_tenant_owner"),
            {"t": workspace["tenant"]["id"]},
        )
    ).scalar_one()

    roles = (
        (
            await pg_session.execute(
                text(
                    "SELECT r.name FROM user_roles ur JOIN role r ON r.id = ur.role_id "
                    "WHERE ur.user_id = :u"
                ),
                {"u": owner_id},
            )
        )
        .scalars()
        .all()
    )
    granted = (
        await pg_session.execute(
            text(
                "SELECT count(*) FROM role_permissions rp JOIN role r ON r.id = rp.role_id "
                "JOIN permission p ON p.id = rp.permission_id "
                "WHERE r.name = 'manager' AND p.code NOT LIKE 'users:%' "
                "AND p.code NOT LIKE 'roles:%' AND p.code NOT LIKE 'permissions:%' "
                "AND p.code NOT LIKE 'menus:%'"
            ),
        )
    ).scalar_one()

    assert roles == ["manager"]
    assert int(granted) == 19  # every application permission


async def test_a_member_without_configured_access_sees_and_does_nothing(
    pg_client, other_client, pg_session
) -> None:
    workspace = await start_workspace(pg_client)
    await add_staff_member(pg_session, other_client, workspace, role=None)

    for method, path, *_ in VIEW_ROUTES + [(m, p) for m, p, _ in EDIT_ROUTES]:
        response = await getattr(other_client, method)(path)
        assert response.status_code == 403, (method, path, response.status_code)

    me = (await other_client.get("/api/me")).json()
    named = [item.get("label") or item.get("name") for item in me.get("menus", [])]
    assert not any(
        label
        in {
            "Inbox",
            "Payment links",
            "Transfer proofs",
            "Bookings",
            "Calendar",
            "Rooms & rates",
            "Channels",
            "Settings",
        }
        for label in named
    ), named
    # the owner still has everything
    for method, path, *_ in VIEW_ROUTES:
        assert (await getattr(pg_client, method)(path)).status_code == 200


async def test_a_narrow_role_sees_but_cannot_change(pg_client, other_client, pg_session) -> None:
    workspace = await start_workspace(pg_client)
    staff = await add_staff_member(pg_session, other_client, workspace, role=None)
    await _give_role(pg_session, staff["user_id"], "front_desk", ["bookings:view", "inbox:view"])

    bookings = await other_client.get("/api/bookings?tab=upcoming")
    inbox = await other_client.get("/api/conversations")
    me = (await other_client.get("/api/me")).json()

    assert (bookings.status_code, inbox.status_code) == (200, 200)
    assert (await other_client.get("/api/room-types")).status_code == 403
    quote = await other_client.post(
        "/api/bookings/quote",
        json={
            "arrival": "2030-01-01",
            "departure": "2030-01-02",
            "room_type_id": "00000000-0000-0000-0000-000000000000",
            "rate_plan_id": "00000000-0000-0000-0000-000000000000",
        },
    )
    create = await other_client.post(
        "/api/bookings",
        json={
            "arrival": "2030-01-01",
            "departure": "2030-01-02",
            "room_type_id": "00000000-0000-0000-0000-000000000000",
            "rate_plan_id": "00000000-0000-0000-0000-000000000000",
            "guest_name": "X",
        },
    )
    assert (quote.status_code, create.status_code) == (422, 403)
    named = [item.get("label") or item.get("name") for item in me.get("menus", [])]
    assert any(label == "Bookings" for label in named), named
    assert not any(label == "Calendar" for label in named), named


async def test_the_public_pay_page_needs_no_permission_at_all(pg_client, guest) -> None:
    """The token in the URL is the credential; RBAC never applies to guests."""
    from tests.pg.conftest import make_link, pay, token_of

    await start_workspace(pg_client)
    created = await make_link(pg_client)
    token = token_of(created)

    response = await guest.get(f"/api/pay/{token}")
    assert response.status_code == 200
    assert (await pay(guest, token)).status_code == 200
