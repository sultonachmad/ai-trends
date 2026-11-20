"""Connecting a sales channel: start, test, settings, go live, pause, resume, disconnect."""

import asyncio

import pytest
from sqlalchemy import text

from app.channels import provider as channel_provider
from app.config import settings
from tests.pg.conftest import (
    connect_channel,
    make_rate_plan,
    make_room_type,
    make_test_listing,
    start_workspace,
)

pytestmark = pytest.mark.integration

CHANNELS = "/api/channels"
CONNECTIONS = "/api/channel-connections"
MISSING = "00000000-0000-0000-0000-000000000000"


async def _property(client) -> dict:
    """A workspace with two rooms and a rate plan selling both."""
    workspace = await start_workspace(client)
    deluxe = await make_room_type(client, name="Deluxe", max_guests=2)
    suite = await make_room_type(client, name="Suite", max_guests=4)
    plan = await make_rate_plan(client, [deluxe, suite])
    return {"workspace": workspace, "deluxe": deluxe, "suite": suite, "plan": plan}


def _pair(ctx: dict, room: str, external_room: str, external_rate: str) -> dict:
    return {
        "room_type_id": ctx[room]["id"],
        "rate_plan_id": ctx["plan"]["id"],
        "external_room_id": external_room,
        "external_rate_id": external_rate,
    }


async def _post(client, connection: dict, action: str):
    return await client.post(f"{CONNECTIONS}/{connection['id']}/{action}")


async def _set_limit(session, tenant_id: str, limit: int | None) -> None:
    await session.execute(
        text(
            "UPDATE tenantentitlement SET limits = CAST(:limits AS jsonb) "
            "WHERE tenant_id = :t AND module_code = 'channel_manager'"
        ),
        {
            "t": tenant_id,
            "limits": '{"connected_channels": %s}' % ("null" if limit is None else limit),
        },
    )
    await session.commit()


# ---- catalogue and plan limit ----------------------------------------------------------


async def test_requires_sign_in(pg_client) -> None:
    assert (await pg_client.get(CHANNELS)).status_code == 401
    assert (await pg_client.get(CONNECTIONS)).status_code == 401


async def test_catalogue_shows_what_can_be_connected_and_what_is_coming(pg_client) -> None:
    await start_workspace(pg_client)

    overview = (await pg_client.get(CHANNELS)).json()

    by_code = {channel["code"]: channel for channel in overview["channels"]}
    assert overview["usage"] == {"used": 0, "limit": 1, "limit_reached": False}
    assert by_code["simulator"]["state"] == "connectable"
    assert overview["channels"][0]["code"] == "simulator"  # connectable ones come first
    for code in ("traveloka", "tiket", "agoda", "booking_com", "airbnb", "google_hotels", "ical"):
        assert by_code[code]["state"] == "coming_soon"
    assert "ari_push" in by_code["booking_com"]["features"]
    assert not {"walk_in", "whatsapp", "direct_web", "direct_phone"} & set(by_code)


async def test_the_simulated_agency_is_hidden_when_its_switch_is_off(
    pg_client, monkeypatch
) -> None:
    await start_workspace(pg_client)
    listing = await make_test_listing(pg_client)
    monkeypatch.setattr(settings, "CHANNEL_SIMULATOR_ENABLED", False)

    overview = (await pg_client.get(CHANNELS)).json()
    connect = await pg_client.post(
        CONNECTIONS, json={"channel_code": "simulator", "external_property_id": listing["hotel_id"]}
    )
    panel = await pg_client.post("/api/simulator/channels/listings")

    assert "simulator" not in [channel["code"] for channel in overview["channels"]]
    assert (connect.status_code, panel.status_code) == (422, 404)


@pytest.mark.parametrize("code", ["traveloka", "ical", "walk_in", "nonsense"])
async def test_channels_that_are_not_ready_cannot_be_connected(pg_client, code) -> None:
    await start_workspace(pg_client)

    response = await pg_client.post(
        CONNECTIONS, json={"channel_code": code, "external_property_id": "12345"}
    )

    assert response.status_code == 422
    assert "cannot be connected yet" in response.json()["detail"]


# ---- the path to live -------------------------------------------------------------------


async def test_start_test_match_and_go_live(pg_client) -> None:
    ctx = await _property(pg_client)
    listing = await make_test_listing(pg_client)

    created = await pg_client.post(
        CONNECTIONS, json={"channel_code": "simulator", "external_property_id": listing["hotel_id"]}
    )
    draft = created.json()
    tested = (await _post(pg_client, draft, "test")).json()
    matched = (
        await pg_client.put(
            f"{CONNECTIONS}/{draft['id']}/mappings",
            json={"mappings": [_pair(ctx, "deluxe", "R1", "P1")]},
        )
    ).json()
    live = await _post(pg_client, draft, "go-live")

    assert created.status_code == 201, created.text
    assert (draft["status"], draft["channel_name"]) == ("draft", "Simulated agency (test)")
    assert (draft["external_property_id"], draft["mapped_pairs"]) == (listing["hotel_id"], 0)
    assert (tested["status"], tested["problem"]) == ("testing", None)
    assert tested["channel_property_name"] == listing["name"]
    assert [room["id"] for room in tested["products"]["rooms"]] == ["R1", "R2", "R3"]
    assert tested["last_tested_at"] is not None
    assert matched["mapped_pairs"] == 1
    assert (live.status_code, live.json()["status"]) == (200, "live")
    usage = (await pg_client.get(CHANNELS)).json()
    assert usage["usage"] == {"used": 1, "limit": 1, "limit_reached": True}
    assert [c["connected"] for c in usage["channels"] if c["code"] == "simulator"] == [True]
    assert [c["id"] for c in (await pg_client.get(CONNECTIONS)).json()] == [draft["id"]]


async def test_a_wrong_property_id_fails_the_test_and_can_be_retried(pg_client) -> None:
    await _property(pg_client)
    created = (
        await pg_client.post(
            CONNECTIONS, json={"channel_code": "simulator", "external_property_id": "SIM-WRONG1"}
        )
    ).json()

    failed = (await _post(pg_client, created, "test")).json()
    go_live = await _post(pg_client, created, "go-live")
    again = (await _post(pg_client, created, "test")).json()

    assert (failed["status"], failed["problem"]) == ("error", "unknown_property")
    assert failed["products"] is None
    assert go_live.status_code == 409
    assert again["status"] == "error"


async def test_a_channel_that_does_not_answer_leaves_things_as_they_were(
    pg_client, monkeypatch
) -> None:
    ctx = await _property(pg_client)
    draft = await connect_channel(pg_client, tested=False)
    live = await connect_channel_live(pg_client, ctx, draft)

    class Down:
        async def fetch_property(self, call, property_id):
            raise channel_provider.ChannelUnavailableError("timeout")

    monkeypatch.setitem(channel_provider._PROVIDERS, "simulator", Down())

    tested = (await _post(pg_client, live, "test")).json()
    products = await pg_client.get(f"{CONNECTIONS}/{live['id']}/products")

    assert (tested["status"], tested["problem"]) == ("live", "channel_unavailable")
    assert tested["products"] is not None  # what we knew is kept
    assert products.status_code == 502


async def connect_channel_live(client, ctx: dict, draft: dict) -> dict:
    await _post(client, draft, "test")
    await client.put(
        f"{CONNECTIONS}/{draft['id']}/mappings",
        json={"mappings": [_pair(ctx, "deluxe", "R1", "P1")]},
    )
    response = await _post(client, draft, "go-live")
    assert response.status_code == 200, response.text
    return response.json()


async def test_a_draft_that_cannot_reach_the_channel_stays_a_draft(pg_client, monkeypatch) -> None:
    await _property(pg_client)
    draft = await connect_channel(pg_client, tested=False)

    class Down:
        async def fetch_property(self, call, property_id):
            raise channel_provider.ChannelUnavailableError("timeout")

    monkeypatch.setitem(channel_provider._PROVIDERS, "simulator", Down())

    tested = (await _post(pg_client, draft, "test")).json()

    assert (tested["status"], tested["problem"]) == ("draft", "channel_unavailable")


async def test_going_live_needs_a_passed_test_and_something_matched(pg_client) -> None:
    await _property(pg_client)
    draft = await connect_channel(pg_client, tested=False)

    untested = await _post(pg_client, draft, "go-live")
    await _post(pg_client, draft, "test")
    unmatched = await _post(pg_client, draft, "go-live")

    assert (untested.status_code, unmatched.status_code) == (409, 409)
    assert "draft" in untested.json()["detail"]
    assert "Match at least one" in unmatched.json()["detail"]


# ---- pause, resume, disconnect ----------------------------------------------------------


async def test_pause_resume_and_disconnect(pg_client) -> None:
    ctx = await _property(pg_client)
    live = await connect_channel_live(
        pg_client, ctx, await connect_channel(pg_client, tested=False)
    )

    paused = (await _post(pg_client, live, "pause")).json()
    resumed = (await _post(pg_client, live, "resume")).json()
    gone = (await _post(pg_client, live, "disconnect")).json()

    assert (paused["status"], resumed["status"], gone["status"]) == (
        "paused",
        "live",
        "disconnected",
    )
    assert paused["mapped_pairs"] == 1  # matching is kept while paused
    assert (await pg_client.get(CHANNELS)).json()["usage"]["used"] == 0
    assert [c["status"] for c in (await pg_client.get(CONNECTIONS)).json()] == ["disconnected"]


@pytest.mark.parametrize(
    ("state", "action"),
    [
        ("draft", "pause"),
        ("draft", "resume"),
        ("testing", "pause"),
        ("live", "go-live"),
        ("live", "resume"),
        ("paused", "pause"),
        ("paused", "go-live"),
        ("disconnected", "resume"),
        ("disconnected", "disconnect"),
        ("disconnected", "test"),
    ],
)
async def test_moves_that_make_no_sense_are_refused(pg_client, state, action) -> None:
    ctx = await _property(pg_client)
    connection = await connect_channel(pg_client, tested=state != "draft")
    if state in ("live", "paused", "disconnected"):
        connection = await connect_channel_live(pg_client, ctx, connection)
    if state == "paused":
        await _post(pg_client, connection, "pause")
    if state == "disconnected":
        await _post(pg_client, connection, "disconnect")

    response = await _post(pg_client, connection, action)

    assert response.status_code == 409
    assert state in response.json()["detail"]


async def test_unknown_action_and_unknown_connection(pg_client) -> None:
    await _property(pg_client)
    connection = await connect_channel(pg_client)

    assert (await _post(pg_client, connection, "explode")).status_code == 422
    assert (await pg_client.get(f"{CONNECTIONS}/{MISSING}")).status_code == 404
    assert (await pg_client.post(f"{CONNECTIONS}/{MISSING}/test")).status_code == 404


# ---- settings ---------------------------------------------------------------------------


async def test_settings_have_defaults_and_can_be_changed(pg_client) -> None:
    await _property(pg_client)
    connection = await connect_channel(pg_client)

    changed = await pg_client.patch(
        f"{CONNECTIONS}/{connection['id']}",
        json={
            "commission_percent": 17.5,
            "price_adjustment_percent": -10,
            "payment_collect": "channel",
        },
    )
    partly = await pg_client.patch(
        f"{CONNECTIONS}/{connection['id']}", json={"price_adjustment_percent": 15}
    )

    assert (connection["commission_percent"], connection["price_adjustment_percent"]) == (
        "0.00",
        "0.00",
    )
    assert connection["payment_collect"] == "property"
    assert changed.status_code == 200, changed.text
    body = partly.json()
    assert (body["commission_percent"], body["price_adjustment_percent"]) == ("17.50", "15.00")
    assert body["payment_collect"] == "channel"


@pytest.mark.parametrize(
    "body",
    [
        {"commission_percent": -1},
        {"commission_percent": 50.01},
        {"price_adjustment_percent": -50.5},
        {"price_adjustment_percent": 101},
        {"payment_collect": "guest"},
        {"status": "live"},
    ],
)
async def test_settings_out_of_range_are_refused(pg_client, body) -> None:
    await _property(pg_client)
    connection = await connect_channel(pg_client)

    assert (
        await pg_client.patch(f"{CONNECTIONS}/{connection['id']}", json=body)
    ).status_code == 422


@pytest.mark.parametrize(
    "body",
    [
        {"channel_code": "simulator"},
        {"channel_code": "simulator", "external_property_id": ""},
        {"channel_code": "simulator", "external_property_id": "has space"},
        {"channel_code": "simulator", "external_property_id": "x" * 65},
        {"channel_code": "Simulator!", "external_property_id": "SIM-1"},
        {"channel_code": "simulator", "external_property_id": "SIM-1", "status": "live"},
    ],
)
async def test_create_validation(pg_client, body) -> None:
    await _property(pg_client)

    assert (await pg_client.post(CONNECTIONS, json=body)).status_code == 422


# ---- the plan limit ---------------------------------------------------------------------


async def test_the_free_plan_stops_a_second_connection(pg_client, pg_session) -> None:
    ctx = await _property(pg_client)
    first = await connect_channel(pg_client)
    other_listing = await make_test_listing(pg_client)
    body = {"channel_code": "simulator", "external_property_id": other_listing["hotel_id"]}

    same_channel = await pg_client.post(CONNECTIONS, json=body)
    await _post(pg_client, first, "disconnect")
    await _set_limit(pg_session, ctx["workspace"]["tenant"]["id"], 0)
    not_in_plan = await pg_client.post(CONNECTIONS, json=body)
    await _set_limit(pg_session, ctx["workspace"]["tenant"]["id"], 1)
    after_disconnect = await pg_client.post(CONNECTIONS, json=body)

    assert same_channel.status_code == 409  # one connection per channel
    assert not_in_plan.status_code == 403
    assert not_in_plan.json()["detail"] == "Channel connections are not part of your plan."
    assert after_disconnect.status_code == 201


async def test_the_limit_message_names_the_number(pg_client, pg_session, monkeypatch) -> None:
    ctx = await _property(pg_client)
    await connect_channel(pg_client)
    # a second connectable channel, so the limit (not "already connected") is what refuses
    monkeypatch.setitem(
        channel_provider._PROVIDERS, "agoda", channel_provider._PROVIDERS["simulator"]
    )

    refused = await pg_client.post(
        CONNECTIONS, json={"channel_code": "agoda", "external_property_id": "A-1"}
    )
    await _set_limit(pg_session, ctx["workspace"]["tenant"]["id"], None)
    unlimited = await pg_client.post(
        CONNECTIONS, json={"channel_code": "agoda", "external_property_id": "A-1"}
    )

    assert refused.status_code == 403
    assert "allows 1 connected channel." in refused.json()["detail"]
    assert unlimited.status_code == 201
    usage = (await pg_client.get(CHANNELS)).json()["usage"]
    assert usage == {"used": 2, "limit": None, "limit_reached": False}


async def test_simultaneous_connects_cannot_pass_the_limit(pg_client) -> None:
    await _property(pg_client)
    listings = [await make_test_listing(pg_client) for _ in range(4)]

    responses = await asyncio.gather(
        *(
            pg_client.post(
                CONNECTIONS,
                json={"channel_code": "simulator", "external_property_id": listing["hotel_id"]},
            )
            for listing in listings
        )
    )

    assert sorted(r.status_code for r in responses).count(201) == 1
    assert (await pg_client.get(CHANNELS)).json()["usage"]["used"] == 1


async def test_reconnecting_the_same_listing_continues_its_history(pg_client) -> None:
    ctx = await _property(pg_client)
    listing = await make_test_listing(pg_client)
    body = {"channel_code": "simulator", "external_property_id": listing["hotel_id"]}
    first = (await pg_client.post(CONNECTIONS, json=body)).json()
    await connect_channel_live(pg_client, ctx, first)
    await _post(pg_client, first, "disconnect")

    again = (await pg_client.post(CONNECTIONS, json=body)).json()

    assert again["id"] == first["id"]
    assert (again["status"], again["mapped_pairs"]) == ("draft", 0)  # matched afresh
    events = [entry["event"] for entry in again["history"]]
    assert events[0] == "channel.connection.started"
    assert "channel.connection.disconnected" in events


# ---- history ----------------------------------------------------------------------------


async def test_every_change_is_recorded_with_who_and_when(pg_client, pg_session) -> None:
    ctx = await _property(pg_client)
    live = await connect_channel_live(
        pg_client, ctx, await connect_channel(pg_client, tested=False)
    )
    await pg_client.patch(f"{CONNECTIONS}/{live['id']}", json={"commission_percent": 15})
    await _post(pg_client, live, "pause")

    detail = (await pg_client.get(f"{CONNECTIONS}/{live['id']}")).json()

    events = [entry["event"].removeprefix("channel.connection.") for entry in detail["history"]]
    assert events == [
        "paused",
        "settings_changed",
        "went_live",
        "matching_changed",
        "tested",
        "started",
    ]
    assert all(entry["actor"] and entry["at"] for entry in detail["history"])
    assert detail["history"][1]["details"] == {"commission_percent": "15"}
    chain = (
        await pg_session.execute(
            text(
                "SELECT prev_hash, entry_hash FROM tenantauditentry WHERE tenant_id = :t "
                "ORDER BY occurred_at, id"
            ),
            {"t": ctx["workspace"]["tenant"]["id"]},
        )
    ).all()
    assert chain[0][0] is None
    assert [row[0] for row in chain[1:]] == [row[1] for row in chain[:-1]]  # each links to the last


async def test_a_disconnect_while_the_channel_answers_wins(
    pg_client, pg_session, monkeypatch
) -> None:
    """The locked re-read must see what another transaction committed mid-fetch."""
    from app.channels import provider as channel_provider

    ctx = await _property(pg_client)
    live = await connect_channel_live(
        pg_client, ctx, await connect_channel(pg_client, tested=False)
    )

    real = channel_provider._PROVIDERS["simulator"]

    class DisconnectsMidFetch:
        async def fetch_property(self, call, property_id):
            await pg_session.execute(
                text("UPDATE channelconnection SET status = 'disconnected' WHERE id = :c"),
                {"c": live["id"]},
            )
            await pg_session.commit()
            return await real.fetch_property(call, property_id)

    monkeypatch.setitem(channel_provider._PROVIDERS, "simulator", DisconnectsMidFetch())

    response = await pg_client.post(f"{CONNECTIONS}/{live['id']}/test")

    assert response.status_code == 409
    assert "disconnected" in response.json()["detail"]
    after = (await pg_client.get(f"{CONNECTIONS}/{live['id']}")).json()
    assert after["status"] == "disconnected"  # the test did not bring it back
    assert (await pg_client.get(CHANNELS)).json()["usage"]["used"] == 0


async def test_concurrent_changes_keep_the_history_chain_intact(
    pg_client, pg_session, monkeypatch
) -> None:
    """Two routes recording at once chain one after the other, not side by side."""
    import asyncio

    ctx = await _property(pg_client)
    one = await connect_channel(pg_client)
    await _set_limit(pg_session, ctx["workspace"]["tenant"]["id"], 2)
    # a second connection needs a second channel: register one more behind the simulator
    monkeypatch.setitem(
        channel_provider._PROVIDERS, "agoda", channel_provider._PROVIDERS["simulator"]
    )
    two = (
        await pg_client.post(
            CONNECTIONS, json={"channel_code": "agoda", "external_property_id": "A-1"}
        )
    ).json()
    assert "id" in two, two

    await asyncio.gather(
        pg_client.patch(f"{CONNECTIONS}/{one['id']}", json={"commission_percent": 11}),
        pg_client.post(f"{CONNECTIONS}/{two['id']}/test"),
        pg_client.patch(f"{CONNECTIONS}/{one['id']}", json={"commission_percent": 12}),
    )

    chain = (
        await pg_session.execute(
            text(
                "SELECT prev_hash, entry_hash FROM tenantauditentry WHERE tenant_id = :t "
                "ORDER BY occurred_at, id"
            ),
            {"t": ctx["workspace"]["tenant"]["id"]},
        )
    ).all()
    assert len(chain) >= 4
    assert chain[0][0] is None
    assert [row[0] for row in chain[1:]] == [row[1] for row in chain[:-1]]  # no fork
