"""The team: join links, joining, roles, removal, and one workspace never seeing another's."""

import uuid

import pytest
from sqlalchemy import text

from tests.pg.conftest import PASSWORD, sign_up_and_in, start_workspace

pytestmark = pytest.mark.integration

STAFF = "/api/staff"
JOIN = "/api/join"


def _email() -> str:
    return f"staff-{uuid.uuid4().hex[:10]}@example.com"


async def _sign_up(client, email: str) -> None:
    created = await client.post("/api/auth/signup", json={"email": email, "password": PASSWORD})
    assert created.status_code == 201, created.text
    logged_in = await client.post("/session/login", json={"email": email, "password": PASSWORD})
    assert logged_in.status_code == 200, logged_in.text


async def _invite(client, email: str, role: str = "housekeeper", name: str = "Wayan") -> dict:
    response = await client.post(
        f"{STAFF}/invites", json={"name": name, "email": email, "role": role}
    )
    assert response.status_code == 200, response.text
    return response.json()


async def _joined(owner, member, role: str = "housekeeper") -> dict:
    email = _email()
    created = await _invite(owner, email, role)
    await _sign_up(member, email)
    joined = await member.post(f"{JOIN}/{created['token']}")
    assert joined.status_code == 200, joined.text
    return {"email": email, "invite": created}


def _code(response) -> str:
    return response.json()["detail"]["code"]


async def _team(client) -> dict:
    response = await client.get(STAFF)
    assert response.status_code == 200, response.text
    return response.json()


async def test_a_housekeeper_joins_with_the_link_and_gets_housekeeping_only(
    pg_client, other_client
) -> None:
    await start_workspace(pg_client)
    joined = await _joined(pg_client, other_client)

    board = await other_client.get("/api/housekeeping/board")
    desk = await other_client.get("/api/front-desk/today")
    team = await _team(pg_client)

    assert board.status_code == 200, board.text
    assert desk.status_code == 403
    member = next(m for m in team["members"] if m["email"] == joined["email"])
    assert (member["name"], member["role"], member["is_owner"]) == ("Wayan", "housekeeper", False)
    assert team["invites"] == []  # used links are no longer open


async def test_the_link_shows_what_it_is_for_without_revealing_the_email(pg_client) -> None:
    await start_workspace(pg_client)
    created = await _invite(pg_client, "wayan.sudarsana@example.com")

    preview = await pg_client.get(f"{JOIN}/{created['token']}")
    unknown = await pg_client.get(f"{JOIN}/{'x' * 43}")

    assert preview.status_code == 200, preview.text
    body = preview.json()
    assert (body["workspace"], body["state"], body["role"]) == (
        "Villa Senja Ubud",
        "open",
        "housekeeper",
    )
    assert body["email_hint"] == "w***@example.com"
    assert (unknown.status_code, _code(unknown)) == (404, "invite_not_found")


async def test_only_the_stored_hash_of_the_token_is_kept(pg_client, pg_session) -> None:
    await start_workspace(pg_client)
    created = await _invite(pg_client, _email())

    stored = (
        await pg_session.execute(
            text("SELECT token_hash FROM tenantinvitation WHERE id = :i"),
            {"i": created["invite"]["id"]},
        )
    ).scalar_one()

    assert created["token"] not in stored and len(stored) == 64


async def test_a_link_works_only_for_the_invited_email(pg_client, other_client) -> None:
    await start_workspace(pg_client)
    created = await _invite(pg_client, _email())
    await sign_up_and_in(other_client)  # another address

    refused = await other_client.post(f"{JOIN}/{created['token']}")

    assert (refused.status_code, _code(refused)) == (403, "wrong_email")
    assert len((await _team(pg_client))["invites"]) == 1  # still open


async def test_a_link_works_once(pg_client, other_client, third_client) -> None:
    await start_workspace(pg_client)
    joined = await _joined(pg_client, other_client)
    await _sign_up(third_client, _email())

    again = await other_client.post(f"{JOIN}/{joined['invite']['token']}")

    assert (again.status_code, _code(again)) == (410, "invite_used")


async def test_expired_and_cancelled_links_are_refused(pg_client, other_client, pg_session) -> None:
    await start_workspace(pg_client)
    email = _email()
    expired = await _invite(pg_client, email)
    await pg_session.execute(
        text("UPDATE tenantinvitation SET expires_at = now() - interval '1 minute' WHERE id = :i"),
        {"i": expired["invite"]["id"]},
    )
    await pg_session.commit()
    cancelled = await _invite(pg_client, email)  # the expired one no longer blocks a new link
    revoked = await pg_client.post(f"{STAFF}/invites/{cancelled['invite']['id']}/revoke")
    await _sign_up(other_client, email)

    late = await other_client.post(f"{JOIN}/{expired['token']}")
    gone = await other_client.post(f"{JOIN}/{cancelled['token']}")
    preview = await other_client.get(f"{JOIN}/{cancelled['token']}")

    assert revoked.status_code == 200, revoked.text
    assert (late.status_code, _code(late)) == (410, "invite_expired")
    assert (gone.status_code, _code(gone)) == (410, "invite_revoked")
    assert preview.json()["state"] == "revoked"


async def test_someone_with_their_own_workspace_cannot_join(pg_client, other_client) -> None:
    await start_workspace(pg_client)
    other = await start_workspace(other_client)
    created = await _invite(pg_client, other["staff"]["email"])

    refused = await other_client.post(f"{JOIN}/{created['token']}")

    assert (refused.status_code, _code(refused)) == (409, "already_member")


async def test_an_email_already_invited_or_on_the_team_is_refused(pg_client, other_client) -> None:
    await start_workspace(pg_client)
    joined = await _joined(pg_client, other_client)
    email = _email()
    await _invite(pg_client, email)

    twice = await pg_client.post(
        f"{STAFF}/invites", json={"name": "Made", "email": email.upper(), "role": "housekeeper"}
    )
    member = await pg_client.post(
        f"{STAFF}/invites", json={"name": "Made", "email": joined["email"], "role": "manager"}
    )

    assert (twice.status_code, _code(twice)) == (409, "already_invited")
    assert (member.status_code, _code(member)) == (409, "already_invited")


async def test_the_owner_changes_a_role_and_removes_a_member(pg_client, other_client) -> None:
    await start_workspace(pg_client)
    joined = await _joined(pg_client, other_client)
    staff_id = next(
        m["staff_id"] for m in (await _team(pg_client))["members"] if m["email"] == joined["email"]
    )

    changed = await pg_client.put(f"{STAFF}/{staff_id}/role", json={"role": "front_desk"})
    desk = await other_client.get("/api/front-desk/today")
    removed = await pg_client.post(f"{STAFF}/{staff_id}/remove")
    after = await other_client.get("/api/housekeeping/board")

    assert changed.status_code == 200, changed.text
    assert desk.status_code == 200, desk.text
    assert removed.status_code == 200, removed.text
    assert all(m["email"] != joined["email"] for m in removed.json()["members"])
    assert after.status_code == 403


async def test_a_removed_member_can_join_again_with_a_new_link(pg_client, other_client) -> None:
    await start_workspace(pg_client)
    joined = await _joined(pg_client, other_client)
    staff_id = next(
        m["staff_id"] for m in (await _team(pg_client))["members"] if m["email"] == joined["email"]
    )
    await pg_client.post(f"{STAFF}/{staff_id}/remove")

    again = await _invite(pg_client, joined["email"], role="front_desk")
    rejoined = await other_client.post(f"{JOIN}/{again['token']}")
    member = next(m for m in (await _team(pg_client))["members"] if m["email"] == joined["email"])

    assert rejoined.status_code == 200, rejoined.text
    assert (member["staff_id"], member["role"]) == (staff_id, "front_desk")


async def test_the_owner_and_yourself_cannot_be_changed(pg_client, other_client) -> None:
    await start_workspace(pg_client)
    await _joined(pg_client, other_client, role="manager")
    owner_id = next(m["staff_id"] for m in (await _team(pg_client))["members"] if m["is_owner"])
    me = next(m["staff_id"] for m in (await _team(other_client))["members"] if m["is_me"])

    owner = await other_client.post(f"{STAFF}/{owner_id}/remove")
    myself = await other_client.put(f"{STAFF}/{me}/role", json={"role": "housekeeper"})

    assert (owner.status_code, _code(owner)) == (409, "cannot_change_owner")
    assert (myself.status_code, _code(myself)) == (409, "cannot_change_self")


async def test_a_housekeeper_cannot_see_or_invite_staff(pg_client, other_client) -> None:
    await start_workspace(pg_client)
    await _joined(pg_client, other_client)

    listed = await other_client.get(STAFF)
    invited = await other_client.post(
        f"{STAFF}/invites", json={"name": "X", "email": _email(), "role": "manager"}
    )

    assert listed.status_code == 403
    assert invited.status_code == 403


async def test_one_workspace_cannot_touch_another_s_team(
    pg_client, other_client, third_client
) -> None:
    await start_workspace(pg_client)
    joined = await _joined(pg_client, other_client)
    team = await _team(pg_client)
    staff_id = next(m["staff_id"] for m in team["members"] if m["email"] == joined["email"])
    pending = await _invite(pg_client, _email())
    await start_workspace(third_client)

    theirs = await _team(third_client)
    remove = await third_client.post(f"{STAFF}/{staff_id}/remove")
    revoke = await third_client.post(f"{STAFF}/invites/{pending['invite']['id']}/revoke")

    assert [m["email"] for m in theirs["members"]] != [joined["email"]]
    assert all(m["email"] != joined["email"] for m in theirs["members"])
    assert theirs["invites"] == []
    assert (remove.status_code, _code(remove)) == (404, "staff_not_found")
    assert (revoke.status_code, _code(revoke)) == (404, "invite_not_found")


async def test_joining_and_team_changes_are_in_the_history(
    pg_client, other_client, pg_session
) -> None:
    workspace = await start_workspace(pg_client)
    await _joined(pg_client, other_client)

    events = (
        (
            await pg_session.execute(
                text(
                    "SELECT event_id FROM tenantauditentry WHERE tenant_id = :t "
                    "ORDER BY occurred_at"
                ),
                {"t": workspace["tenant"]["id"]},
            )
        )
        .scalars()
        .all()
    )

    assert "staff.invited" in events and "staff.joined" in events


async def test_only_the_owner_or_a_manager_can_make_a_manager(
    pg_client, other_client, pg_session
) -> None:
    from tests.pg.test_feature_access import _give_role

    await start_workspace(pg_client)
    joined = await _joined(pg_client, other_client)
    user_id = (
        await pg_session.execute(
            text('SELECT id FROM "user" WHERE email = :e'), {"e": joined["email"]}
        )
    ).scalar_one()
    await _give_role(pg_session, user_id, "team_admin_test", ["staff:view", "staff:edit"])
    await pg_session.commit()

    manager = await other_client.post(
        f"{STAFF}/invites", json={"name": "X", "email": _email(), "role": "manager"}
    )
    housekeeper = await other_client.post(
        f"{STAFF}/invites", json={"name": "Y", "email": _email(), "role": "housekeeper"}
    )

    assert (manager.status_code, _code(manager)) == (403, "manager_only")
    assert housekeeper.status_code == 200, housekeeper.text


async def test_removing_someone_gives_their_unfinished_rooms_back(
    pg_client, other_client, pg_session
) -> None:
    workspace = await start_workspace(pg_client)
    joined = await _joined(pg_client, other_client)
    room = (
        await pg_client.post(
            "/api/room-types", json={"name": "Deluxe", "kind": "room", "units": 1, "max_guests": 2}
        )
    ).json()
    await pg_session.execute(
        text("UPDATE unit SET hk_status = 'dirty' WHERE id = :u"), {"u": room["units"][0]["id"]}
    )
    await pg_session.commit()
    task = (await other_client.get("/api/housekeeping/board")).json()["tasks"][0]
    await other_client.post(f"/api/housekeeping/tasks/{task['id']}/start")
    staff_id = next(
        m["staff_id"] for m in (await _team(pg_client))["members"] if m["email"] == joined["email"]
    )

    await pg_client.post(f"{STAFF}/{staff_id}/remove")
    after = (await pg_client.get("/api/housekeeping/board")).json()["tasks"][0]

    assert workspace["tenant"]["id"]
    assert (after["status"], after["assigned_staff_id"]) == ("paused", None)
