"""Calendar links: a site's busy dates block ours, ours block the site's."""

import datetime as dt

import pytest
from sqlalchemy import text

from app.services import calendar_link_sync as sync
from app.services.calendar_dates import property_today
from app.services.channel_push import _context
from app.tenancy.session import bind_tenant
from tests.pg.conftest import (
    add_staff_member,
    connect_channel,
    make_rate_plan,
    make_room_type,
    make_test_listing,
    push_now,
    start_workspace,
)

pytestmark = pytest.mark.integration

LINKS = "/api/calendar-links"
AGENCY = "/api/simulator/channels/listings"


async def _setup(client, *, units: int = 1) -> dict:
    workspace = await start_workspace(client)
    room = await make_room_type(client, units=units, max_guests=2)
    plan = await make_rate_plan(client, [room], amount=500000)
    listing = await make_test_listing(client)
    return {"workspace": workspace, "room": room, "plan": plan, "hotel": listing["hotel_id"]}


def _day(ctx: dict, offset: int) -> str:
    today = property_today(ctx["workspace"]["property"]["timezone"])
    return (today + dt.timedelta(days=offset)).isoformat()


async def _site(client, ctx, days: list[str], *, broken: bool = False) -> str:
    response = await client.put(
        f"{AGENCY}/{ctx['hotel']}/calendar", json={"busy": days, "broken": broken}
    )
    assert response.status_code == 200, response.text
    return response.json()["url"]


async def _link(client, ctx, days: list[str] | None = None, label: str = "Airbnb") -> dict:
    body = {"room_type_id": ctx["room"]["id"], "label": label}
    if days is not None:
        body["import_url"] = await _site(client, ctx, days)
    response = await client.post(LINKS, json=body)
    assert response.status_code == 201, response.text
    return response.json()


async def _available(client, ctx, offset: int) -> int:
    day = _day(ctx, offset)
    response = await client.get("/api/calendar", params={"from": day, "to": day})
    assert response.status_code == 200, response.text
    return response.json()["room_types"][0]["days"][0]["available"]


async def _busy_in_export(client, created: dict) -> str:
    response = await client.get(created["export_path"])
    assert response.status_code == 200, response.text
    return response.text


def _ics(day: str) -> str:
    return f"DTSTART;VALUE=DATE:{day.replace('-', '')}"


async def test_a_busy_date_on_the_site_takes_a_unit(pg_client) -> None:
    ctx = await _setup(pg_client, units=2)
    created = await _link(pg_client, ctx, [_day(ctx, 5)])

    assert created["imports"]["busy_dates"] == 1
    assert created["imports"]["last_synced_at"] is not None
    assert await _available(pg_client, ctx, 5) == 1
    assert await _available(pg_client, ctx, 6) == 2


async def test_a_blocked_date_refuses_a_staff_booking(pg_client) -> None:
    ctx = await _setup(pg_client, units=1)
    await _link(pg_client, ctx, [_day(ctx, 5)])

    response = await pg_client.post(
        "/api/bookings",
        json={
            "arrival": _day(ctx, 5),
            "departure": _day(ctx, 6),
            "room_type_id": ctx["room"]["id"],
            "rate_plan_id": ctx["plan"]["id"],
            "guest_name": "Tamu",
        },
    )
    assert response.status_code == 409, response.text


async def test_a_removed_event_releases_the_date(pg_client) -> None:
    ctx = await _setup(pg_client)
    created = await _link(pg_client, ctx, [_day(ctx, 5), _day(ctx, 6)])

    await _site(pg_client, ctx, [_day(ctx, 6)])
    synced = await pg_client.post(f"{LINKS}/{created['id']}/sync")

    assert synced.json()["imports"]["busy_dates"] == 1
    assert await _available(pg_client, ctx, 5) == 1
    assert await _available(pg_client, ctx, 6) == 0


async def test_repeated_reads_do_not_block_twice(pg_client) -> None:
    ctx = await _setup(pg_client, units=3)
    created = await _link(pg_client, ctx, [_day(ctx, 5)])

    for _ in range(3):
        await pg_client.post(f"{LINKS}/{created['id']}/sync")

    assert await _available(pg_client, ctx, 5) == 2


async def test_a_failed_read_keeps_the_blocks_and_says_so(pg_client) -> None:
    ctx = await _setup(pg_client)
    created = await _link(pg_client, ctx, [_day(ctx, 5)])

    await _site(pg_client, ctx, [], broken=True)
    synced = (await pg_client.post(f"{LINKS}/{created['id']}/sync")).json()

    assert synced["imports"]["last_error"] == "unreachable"
    assert synced["imports"]["failing_since"] is not None
    assert await _available(pg_client, ctx, 5) == 0

    await _site(pg_client, ctx, [])  # it recovers, with the date gone
    recovered = (await pg_client.post(f"{LINKS}/{created['id']}/sync")).json()
    assert recovered["imports"]["last_error"] is None
    assert recovered["imports"]["failing_since"] is None
    assert await _available(pg_client, ctx, 5) == 1


async def test_a_long_failure_is_at_risk(pg_client, pg_session) -> None:
    ctx = await _setup(pg_client)
    created = await _link(pg_client, ctx, [_day(ctx, 5)])
    await _site(pg_client, ctx, [], broken=True)
    await pg_client.post(f"{LINKS}/{created['id']}/sync")
    await pg_session.execute(
        text("UPDATE icalfeed SET failing_since = now() - interval '25 hours' WHERE link_id = :l"),
        {"l": created["id"]},
    )
    await pg_session.commit()

    [read] = (await pg_client.get(LINKS)).json()
    assert read["imports"]["at_risk"] is True


async def test_export_shows_full_dates_only_and_nothing_private(pg_client) -> None:
    ctx = await _setup(pg_client, units=1)
    created = await _link(pg_client, ctx)
    booked = await pg_client.post(
        "/api/bookings",
        json={
            "arrival": _day(ctx, 3),
            "departure": _day(ctx, 5),
            "room_type_id": ctx["room"]["id"],
            "rate_plan_id": ctx["plan"]["id"],
            "guest_name": "Rahasia Tamu",
            "guest_phone": "+628111222333",
        },
    )
    assert booked.status_code == 201, booked.text

    body = await _busy_in_export(pg_client, created)

    assert _ics(_day(ctx, 3)) in body
    assert f"DTEND;VALUE=DATE:{_day(ctx, 5).replace('-', '')}" in body
    for secret in ("Rahasia", "628111", "500000", booked.json()["number"]):
        assert secret not in body


async def test_a_sites_own_block_is_not_sent_back_to_it(pg_client) -> None:
    ctx = await _setup(pg_client, units=1)
    created = await _link(pg_client, ctx, [_day(ctx, 5)])

    assert _ics(_day(ctx, 5)) not in await _busy_in_export(pg_client, created)


async def test_a_block_from_one_site_shows_on_the_other(pg_client) -> None:
    ctx = await _setup(pg_client, units=1)
    first = await _link(pg_client, ctx, [_day(ctx, 5)], label="Airbnb")
    second = await _link(pg_client, ctx, label="Vrbo")

    assert _ics(_day(ctx, 5)) in await _busy_in_export(pg_client, second)
    assert _ics(_day(ctx, 5)) not in await _busy_in_export(pg_client, first)


async def test_closed_dates_show_as_busy(pg_client) -> None:
    ctx = await _setup(pg_client, units=2)
    created = await _link(pg_client, ctx)
    closed = await pg_client.post(
        "/api/calendar/changes",
        json={
            "start": _day(ctx, 4),
            "end": _day(ctx, 4),
            "room_type_ids": [ctx["room"]["id"]],
            "change": {"kind": "close"},
        },
    )
    assert closed.status_code == 200, closed.text
    assert _ics(_day(ctx, 4)) in await _busy_in_export(pg_client, created)
    assert _ics(_day(ctx, 8)) not in await _busy_in_export(pg_client, created)


async def test_a_block_on_a_sold_date_is_a_conflict_and_cancels_nothing(pg_client) -> None:
    ctx = await _setup(pg_client, units=1)
    booked = await pg_client.post(
        "/api/bookings",
        json={
            "arrival": _day(ctx, 5),
            "departure": _day(ctx, 6),
            "room_type_id": ctx["room"]["id"],
            "rate_plan_id": ctx["plan"]["id"],
            "guest_name": "Tamu",
        },
    )
    assert booked.status_code == 201, booked.text

    created = await _link(pg_client, ctx, [_day(ctx, 5)])

    assert created["conflict_dates"] == [_day(ctx, 5)]
    detail = (await pg_client.get(f"/api/bookings/{booked.json()['id']}")).json()
    assert detail["status"] == "confirmed"
    assert detail["overbooking_risk"] is True


async def test_blocks_reach_a_connected_channel(pg_client, pg_session, pg_session_factory) -> None:
    ctx = await _setup(pg_client, units=2)
    connection = await connect_channel(pg_client)
    await pg_client.put(
        f"/api/channel-connections/{connection['id']}/mappings",
        json={
            "mappings": [
                {
                    "room_type_id": ctx["room"]["id"],
                    "rate_plan_id": ctx["plan"]["id"],
                    "external_room_id": "R1",
                    "external_rate_id": "P1",
                }
            ]
        },
    )
    await pg_client.post(f"/api/channel-connections/{connection['id']}/go-live")
    tenant_id = ctx["workspace"]["tenant"]["id"]
    await push_now(pg_session_factory, tenant_id)

    await _link(pg_client, ctx, [_day(ctx, 5)])
    await push_now(pg_session_factory, tenant_id)

    stored = (
        await pg_session.execute(
            text("SELECT ari FROM channelsimulatorlisting WHERE hotel_id = :h"),
            {"h": connection["external_property_id"]},
        )
    ).scalar_one()
    assert stored["R1"][_day(ctx, 5)]["available"] == 1
    assert stored["R1"][_day(ctx, 6)]["available"] == 2


async def test_removing_a_link_gives_everything_back(pg_client) -> None:
    ctx = await _setup(pg_client)
    created = await _link(pg_client, ctx, [_day(ctx, 5)])

    removed = await pg_client.delete(f"{LINKS}/{created['id']}")

    assert removed.status_code == 204
    assert await _available(pg_client, ctx, 5) == 1
    assert (await pg_client.get(LINKS)).json() == []
    assert (await pg_client.get(created["export_path"])).status_code == 404


async def test_stopping_the_import_gives_the_dates_back(pg_client) -> None:
    ctx = await _setup(pg_client)
    created = await _link(pg_client, ctx, [_day(ctx, 5)])

    patched = await pg_client.patch(f"{LINKS}/{created['id']}", json={"import_url": None})

    assert patched.status_code == 200, patched.text
    assert patched.json()["imports"] is None
    assert await _available(pg_client, ctx, 5) == 1


async def test_replacing_the_link_kills_the_old_one(pg_client) -> None:
    ctx = await _setup(pg_client)
    created = await _link(pg_client, ctx)

    replaced = (await pg_client.post(f"{LINKS}/{created['id']}/token")).json()

    assert replaced["export_path"] != created["export_path"]
    assert (await pg_client.get(created["export_path"])).status_code == 404
    assert (await pg_client.get(replaced["export_path"])).status_code == 200


async def test_lists_never_show_the_private_link_or_import_url(pg_client) -> None:
    ctx = await _setup(pg_client)
    created = await _link(pg_client, ctx, [_day(ctx, 5)])

    listed = (await pg_client.get(LINKS)).text

    assert created["export_path"] not in listed
    assert ctx["hotel"] not in listed


@pytest.mark.parametrize(
    "url",
    ["http://example.com/a.ics", "https://127.0.0.1/a.ics", "https://u:p@example.com/a.ics"],
)
async def test_unsafe_urls_are_refused(pg_client, url: str) -> None:
    ctx = await _setup(pg_client)
    response = await pg_client.post(
        LINKS, json={"room_type_id": ctx["room"]["id"], "label": "X", "import_url": url}
    )
    assert response.status_code == 422


@pytest.mark.parametrize("token", ["nope", "A" * 43])
async def test_bad_tokens_are_the_same_404(pg_client, token: str) -> None:
    response = await pg_client.get(f"/api/ical/{token}.ics")
    assert response.status_code == 404
    assert response.json()["detail"] == "Calendar link not found"


async def test_the_public_calendar_needs_no_sign_in(pg_client, other_client) -> None:
    ctx = await _setup(pg_client)
    created = await _link(pg_client, ctx)
    response = await other_client.get(created["export_path"])
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/calendar")
    assert response.headers["cache-control"] == "no-store"


async def test_links_do_not_count_toward_the_channel_limit(pg_client) -> None:
    ctx = await _setup(pg_client)
    await _link(pg_client, ctx, label="One")
    await _link(pg_client, ctx, label="Two")

    usage = (await pg_client.get("/api/channels")).json()["usage"]
    assert usage["used"] == 0
    assert await connect_channel(pg_client)


async def test_another_tenant_cannot_see_or_touch_a_link(pg_client, other_client) -> None:
    ctx = await _setup(pg_client)
    created = await _link(pg_client, ctx, [_day(ctx, 5)])
    await start_workspace(other_client)

    assert (await other_client.get(LINKS)).json() == []
    assert (await other_client.delete(f"{LINKS}/{created['id']}")).status_code == 404
    assert (await other_client.post(f"{LINKS}/{created['id']}/sync")).status_code == 404
    other_room = await make_room_type(other_client)
    foreign = await pg_client.post(LINKS, json={"room_type_id": other_room["id"], "label": "X"})
    assert foreign.status_code == 422


async def test_routes_need_their_permissions(pg_client, other_client, pg_session) -> None:
    ctx = await _setup(pg_client)
    created = await _link(pg_client, ctx)
    await add_staff_member(pg_session, other_client, ctx["workspace"], role=None)

    assert (await other_client.get(LINKS)).status_code == 403
    assert (await other_client.delete(f"{LINKS}/{created['id']}")).status_code == 403
    assert (await other_client.post(f"{LINKS}/{created['id']}/sync")).status_code == 403
    assert (
        await other_client.post(LINKS, json={"room_type_id": ctx["room"]["id"], "label": "X"})
    ).status_code == 403


async def test_the_loop_reads_only_calendars_that_are_due(
    pg_client, pg_session, pg_session_factory
) -> None:
    ctx = await _setup(pg_client, units=3)
    created = await _link(pg_client, ctx, [_day(ctx, 5)])
    tenant_id = ctx["workspace"]["tenant"]["id"]
    await _site(pg_client, ctx, [_day(ctx, 6)])

    async with pg_session_factory() as session:
        await bind_tenant(session, tenant_id)
        assert await sync.sync_tenant(session, tenant_id) == 0  # just read: not due

    await pg_session.execute(
        text(
            "UPDATE icalfeed SET last_attempt_at = now() - interval '31 minutes' "
            "WHERE link_id = :l AND direction = 'import'"
        ),
        {"l": created["id"]},
    )
    await pg_session.commit()
    async with pg_session_factory() as session:
        await bind_tenant(session, tenant_id)
        assert await sync.sync_tenant(session, tenant_id) == 1

    assert await _available(pg_client, ctx, 5) == 3
    assert await _available(pg_client, ctx, 6) == 2


async def test_a_url_changed_during_a_fetch_is_not_applied(
    pg_client, pg_session_factory, monkeypatch
) -> None:
    ctx = await _setup(pg_client, units=2)
    created = await _link(pg_client, ctx, [_day(ctx, 5)])
    tenant_id = ctx["workspace"]["tenant"]["id"]
    real = sync._read_calendar

    async def changed_meanwhile(session, tenant, url):
        raw = await real(session, tenant, url)
        async with pg_session_factory() as other:
            await bind_tenant(other, tenant)
            await other.execute(
                text(
                    "UPDATE icalfeed SET url = 'https://other.example/a.ics' WHERE link_id = :l "
                    "AND direction = 'import'"
                ),
                {"l": created["id"]},
            )
            await other.commit()
        return raw

    monkeypatch.setattr(sync, "_read_calendar", changed_meanwhile)
    await _site(pg_client, ctx, [_day(ctx, 6)])
    async with pg_session_factory() as session:
        await bind_tenant(session, tenant_id)
        feed_id = (
            await session.execute(
                text("SELECT id FROM icalfeed WHERE link_id = :l AND direction = 'import'"),
                {"l": created["id"]},
            )
        ).scalar_one()
        assert await sync.sync_feed(session, _context(tenant_id, session), feed_id) is False

    assert await _available(pg_client, ctx, 5) == 1  # the old block stands
    assert await _available(pg_client, ctx, 6) == 2


async def test_two_sites_on_two_units_each_see_the_other(pg_client) -> None:
    ctx = await _setup(pg_client, units=2)
    first = await _link(pg_client, ctx, [_day(ctx, 5)], label="Airbnb")
    second = await _link(pg_client, ctx, [_day(ctx, 5)], label="Vrbo")

    assert await _available(pg_client, ctx, 5) == 0
    # each site holds one unit itself; the other unit is taken by the other site
    assert _ics(_day(ctx, 5)) not in await _busy_in_export(pg_client, first)
    assert _ics(_day(ctx, 5)) not in await _busy_in_export(pg_client, second)


async def test_changing_units_with_blocks_keeps_them(pg_client) -> None:
    ctx = await _setup(pg_client, units=2)
    await _link(pg_client, ctx, [_day(ctx, 5)])

    grown = await pg_client.patch(f"/api/room-types/{ctx['room']['id']}", json={"units": 3})
    assert grown.status_code == 200, grown.text
    assert await _available(pg_client, ctx, 5) == 2
    shrunk = await pg_client.patch(f"/api/room-types/{ctx['room']['id']}", json={"units": 1})
    assert shrunk.status_code == 200, shrunk.text
    assert await _available(pg_client, ctx, 5) == 0


async def test_a_crash_in_the_first_read_keeps_the_private_link(pg_client, monkeypatch) -> None:
    ctx = await _setup(pg_client)
    url = await _site(pg_client, ctx, [_day(ctx, 5)])

    async def crash(*_args) -> bytes:
        raise RuntimeError("boom")

    monkeypatch.setattr(sync, "_read_calendar", crash)
    response = await pg_client.post(
        LINKS, json={"room_type_id": ctx["room"]["id"], "label": "A", "import_url": url}
    )

    assert response.status_code == 201, response.text
    assert response.json()["export_path"]
    assert response.json()["imports"]["last_error"] == "unreadable"


async def test_a_link_removed_during_sync_is_a_clean_404(
    pg_client, pg_session_factory, monkeypatch
) -> None:
    ctx = await _setup(pg_client)
    created = await _link(pg_client, ctx, [_day(ctx, 5)])
    real = sync._read_calendar

    async def removed_meanwhile(session, tenant, url):
        raw = await real(session, tenant, url)
        async with pg_session_factory() as other:
            await bind_tenant(other, tenant)
            await other.execute(
                text("DELETE FROM icalfeed WHERE link_id = :l"), {"l": created["id"]}
            )
            await other.commit()
        return raw

    monkeypatch.setattr(sync, "_read_calendar", removed_meanwhile)
    response = await pg_client.post(f"{LINKS}/{created['id']}/sync")
    assert response.status_code == 404
