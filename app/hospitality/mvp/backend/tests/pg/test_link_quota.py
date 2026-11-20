"""Free plan: a monthly limit on payment links, shown to staff and enforced on create."""

import asyncio
import datetime as dt
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import text

from app.services.link_quota import next_month_start_utc
from tests.pg.conftest import guest_says, make_link, set_link_limit, start_workspace

pytestmark = pytest.mark.integration

LINKS = "/api/payment-links"


async def _usage(client) -> dict:
    return (await client.get("/api/workspace")).json()["usage"]


async def _workspace_with_limit(client, session, limit: int | None, **more: object) -> dict:
    workspace = await start_workspace(client)
    await set_link_limit(
        session, workspace["tenant"]["id"], {"payment_links_per_month": limit, **more}
    )
    return workspace


async def _link_count(session, tenant_id: str) -> int:
    result = await session.execute(
        text("SELECT count(*) FROM paymentlink WHERE tenant_id = :t"), {"t": tenant_id}
    )
    return int(result.scalar_one())


# ---- what staff see ---------------------------------------------------------------------


async def test_new_workspace_shows_the_free_plan_limit(pg_client) -> None:
    workspace = await start_workspace(pg_client)

    usage = await _usage(pg_client)

    assert (usage["payment_links_used"], usage["payment_links_limit"]) == (0, 30)
    assert (usage["payment_links_warning"], usage["payment_links_limit_reached"]) == (False, False)
    resets_at = dt.datetime.fromisoformat(usage["payment_links_resets_at"])
    zone = workspace["property"]["timezone"]
    assert resets_at == next_month_start_utc(dt.datetime.now(dt.UTC), zone)
    local = resets_at.astimezone(ZoneInfo(zone)).date()
    assert usage["payment_links_resets_on"] == local.isoformat()
    assert local.day == 1


async def test_warning_starts_at_eighty_percent(pg_client, pg_session) -> None:
    await _workspace_with_limit(pg_client, pg_session, 5)
    states = []
    for _ in range(5):
        await make_link(pg_client)
        usage = await _usage(pg_client)
        states.append((usage["payment_links_warning"], usage["payment_links_limit_reached"]))

    assert states == [(False, False)] * 3 + [(True, False), (False, True)]


async def test_warning_percentage_is_a_plan_value(pg_client, pg_session) -> None:
    await _workspace_with_limit(pg_client, pg_session, 4, usage_warning_percent=50)
    await make_link(pg_client)
    before = await _usage(pg_client)
    await make_link(pg_client)

    assert before["payment_links_warning"] is False
    assert (await _usage(pg_client))["payment_links_warning"] is True


async def test_unlimited_plan_never_warns(pg_client, pg_session) -> None:
    await _workspace_with_limit(pg_client, pg_session, None)
    await make_link(pg_client)

    usage = await _usage(pg_client)

    assert usage["payment_links_limit"] is None
    assert (usage["payment_links_warning"], usage["payment_links_limit_reached"]) == (False, False)


# ---- enforcement ------------------------------------------------------------------------


async def test_the_last_link_succeeds_and_the_next_is_refused(pg_client, pg_session) -> None:
    workspace = await _workspace_with_limit(pg_client, pg_session, 2)
    await make_link(pg_client)
    last = await pg_client.post(LINKS, json={"amount": 100000, "description": "ke-2"})

    refused = await pg_client.post(LINKS, json={"amount": 100000, "description": "ke-3"})

    assert last.status_code == 201
    assert refused.status_code == 403
    detail = refused.json()["detail"]
    assert "limit of 2 payment links" in detail
    zone = ZoneInfo(workspace["property"]["timezone"])
    local_date = next_month_start_utc(dt.datetime.now(dt.UTC), zone.key).astimezone(zone).date()
    assert local_date.isoformat() in detail
    assert await _link_count(pg_session, workspace["tenant"]["id"]) == 2


async def test_cancelled_and_expired_links_still_count(pg_client, pg_session) -> None:
    workspace = await _workspace_with_limit(pg_client, pg_session, 2)
    first = await make_link(pg_client)
    await make_link(pg_client)
    await pg_client.post(f"{LINKS}/{first['link']['id']}/cancel")
    await pg_session.execute(
        text("UPDATE paymentlink SET expires_at = now() - interval '1 hour' WHERE tenant_id = :t"),
        {"t": workspace["tenant"]["id"]},
    )
    await pg_session.commit()

    refused = await pg_client.post(LINKS, json={"amount": 100000, "description": "lagi"})

    assert refused.status_code == 403


async def test_last_months_links_do_not_count(pg_client, pg_session) -> None:
    workspace = await _workspace_with_limit(pg_client, pg_session, 1)
    await make_link(pg_client)
    await pg_session.execute(
        text(
            "UPDATE paymentlink SET created_at = created_at - interval '40 days' "
            "WHERE tenant_id = :t"
        ),
        {"t": workspace["tenant"]["id"]},
    )
    await pg_session.commit()

    response = await pg_client.post(LINKS, json={"amount": 100000, "description": "bulan baru"})

    assert response.status_code == 201
    assert (await _usage(pg_client))["payment_links_used"] == 1


async def test_unlimited_plan_is_not_stopped(pg_client, pg_session) -> None:
    await _workspace_with_limit(pg_client, pg_session, None)

    statuses = [
        (await pg_client.post(LINKS, json={"amount": 100000, "description": f"no {n}"})).status_code
        for n in range(3)
    ]

    assert statuses == [201, 201, 201]


@pytest.mark.parametrize("limits", [{"payment_links_per_month": 0}, None])
async def test_plan_without_payment_links_refuses_with_its_own_message(
    pg_client, pg_session, limits
) -> None:
    workspace = await start_workspace(pg_client)
    await set_link_limit(pg_session, workspace["tenant"]["id"], limits)

    refused = await pg_client.post(LINKS, json={"amount": 100000, "description": "x"})

    assert refused.status_code == 403
    assert refused.json()["detail"] == "Payment links are not part of your plan."


async def test_simultaneous_requests_cannot_pass_the_limit(pg_client, pg_session) -> None:
    workspace = await _workspace_with_limit(pg_client, pg_session, 3)
    await make_link(pg_client)

    responses = await asyncio.gather(
        *(
            pg_client.post(LINKS, json={"amount": 100000, "description": f"bersamaan {n}"})
            for n in range(6)
        )
    )

    assert sorted(r.status_code for r in responses) == [201, 201, 403, 403, 403, 403]
    assert await _link_count(pg_session, workspace["tenant"]["id"]) == 3


async def test_a_refused_link_sends_nothing_to_the_chat(pg_client, pg_session) -> None:
    await _workspace_with_limit(pg_client, pg_session, 1)
    conversation_id = (await guest_says(pg_client, "Halo"))["conversation_id"]
    await make_link(pg_client)
    before = (await pg_client.get(f"/api/conversations/{conversation_id}/messages")).json()

    refused = await pg_client.post(
        LINKS, json={"amount": 100000, "description": "x", "conversation_id": conversation_id}
    )

    after = (await pg_client.get(f"/api/conversations/{conversation_id}/messages")).json()
    assert refused.status_code == 403
    assert len(after) == len(before)


async def test_invalid_input_is_reported_before_the_limit(pg_client, pg_session) -> None:
    await _workspace_with_limit(pg_client, pg_session, 0)

    response = await pg_client.post(LINKS, json={"amount": 1, "description": "x"})

    assert response.status_code == 422


async def test_another_tenants_links_do_not_count(pg_client, other_client, pg_session) -> None:
    await _workspace_with_limit(pg_client, pg_session, 1)
    await _workspace_with_limit(other_client, pg_session, 1)
    await make_link(other_client)

    mine = await pg_client.post(LINKS, json={"amount": 100000, "description": "milik saya"})
    theirs = await other_client.post(LINKS, json={"amount": 100000, "description": "lagi"})

    assert (mine.status_code, theirs.status_code) == (201, 403)
    assert (await _usage(pg_client))["payment_links_used"] == 1


# ---- month boundary ---------------------------------------------------------------------


@pytest.mark.parametrize(
    ("now", "zone", "expected"),
    [
        # 30 Nov 23:30 UTC is already 1 Dec 07:30 in Bali: the reset is 1 Jan local.
        ("2026-11-30T23:30:00+00:00", "Asia/Makassar", "2026-12-31T16:00:00+00:00"),
        ("2026-11-30T15:59:00+00:00", "Asia/Makassar", "2026-11-30T16:00:00+00:00"),
        ("2026-12-15T05:00:00+00:00", "Asia/Jakarta", "2026-12-31T17:00:00+00:00"),
        ("2026-01-31T12:00:00+00:00", "UTC", "2026-02-01T00:00:00+00:00"),
        ("2026-06-10T00:00:00+00:00", "Not/AZone", "2026-07-01T00:00:00+00:00"),
    ],
)
def test_next_month_start(now: str, zone: str, expected: str) -> None:
    result = next_month_start_utc(dt.datetime.fromisoformat(now), zone)

    assert result == dt.datetime.fromisoformat(expected)
