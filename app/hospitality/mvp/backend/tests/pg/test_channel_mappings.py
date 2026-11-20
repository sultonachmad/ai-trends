"""Matching our rooms and rate plans to a channel's rooms and rates."""

import pytest
from sqlalchemy import text

from tests.pg.conftest import (
    connect_channel,
    make_rate_plan,
    make_room_type,
    start_workspace,
)

pytestmark = pytest.mark.integration

CONNECTIONS = "/api/channel-connections"
MISSING = "00000000-0000-0000-0000-000000000000"


async def _property(client) -> dict:
    """Deluxe (2 guests) and Suite (4) on "Normal"; Deluxe also on "Hemat"."""
    workspace = await start_workspace(client)
    deluxe = await make_room_type(client, name="Deluxe", max_guests=2)
    suite = await make_room_type(client, name="Suite", max_guests=4)
    normal = await make_rate_plan(client, [deluxe, suite], name="Normal")
    hemat = await make_rate_plan(client, [deluxe], name="Hemat")
    return {
        "workspace": workspace,
        "deluxe": deluxe,
        "suite": suite,
        "normal": normal,
        "hemat": hemat,
    }


def _pair(ctx: dict, room: str, plan: str, external_room: str, external_rate: str) -> dict:
    return {
        "room_type_id": ctx[room]["id"],
        "rate_plan_id": ctx[plan]["id"],
        "external_room_id": external_room,
        "external_rate_id": external_rate,
    }


async def _save(client, connection: dict, pairs: list[dict]):
    return await client.put(f"{CONNECTIONS}/{connection['id']}/mappings", json={"mappings": pairs})


async def test_the_channel_lists_its_own_rooms_and_rates(pg_client) -> None:
    await _property(pg_client)
    connection = await connect_channel(pg_client)

    products = (await pg_client.get(f"{CONNECTIONS}/{connection['id']}/products")).json()

    assert [(room["id"], room["name"], room["max_guests"]) for room in products["rooms"]] == [
        ("R1", "Deluxe — Double or Twin", 2),
        ("R2", "Suite — Double or Twin", 3),
        ("R3", "Family Room with Balcony", 4),
    ]
    assert [rate["id"] for rate in products["rooms"][0]["rates"]] == ["P1", "P2"]
    assert products["rooms"][0]["rates"][1]["name"] == "Hemat — Agency Rate"


async def test_save_replace_and_clear(pg_client) -> None:
    ctx = await _property(pg_client)
    connection = await connect_channel(pg_client)
    first = [_pair(ctx, "deluxe", "normal", "R1", "P1"), _pair(ctx, "suite", "normal", "R2", "P3")]

    saved = (await _save(pg_client, connection, first)).json()
    replaced = (
        await _save(pg_client, connection, [_pair(ctx, "deluxe", "hemat", "R1", "P2")])
    ).json()
    cleared = (await _save(pg_client, connection, [])).json()

    assert saved["mappings"] == first
    assert (saved["mapped_pairs"], replaced["mapped_pairs"], cleared["mapped_pairs"]) == (2, 1, 0)
    assert replaced["mappings"] == [_pair(ctx, "deluxe", "hemat", "R1", "P2")]
    assert cleared["mappings"] == []


async def test_health_counts_what_is_left_over(pg_client) -> None:
    ctx = await _property(pg_client)
    connection = await connect_channel(pg_client)

    nothing = connection["health"]
    one = (await _save(pg_client, connection, [_pair(ctx, "deluxe", "normal", "R1", "P1")])).json()
    with_suite = (
        await _save(
            pg_client,
            connection,
            [_pair(ctx, "deluxe", "normal", "R1", "P1"), _pair(ctx, "suite", "normal", "R2", "P3")],
        )
    ).json()

    assert (nothing["unmatched_pairs"], nothing["unmatched_channel_rates"]) == (3, 4)
    assert (one["health"]["unmatched_pairs"], one["health"]["unmatched_channel_rates"]) == (2, 3)
    assert one["health"]["smaller_capacity"] == []
    # the agency's suite fits 3, ours fits 4: a warning, not a refusal
    assert with_suite["health"]["smaller_capacity"] == [_pair(ctx, "suite", "normal", "R2", "P3")]


@pytest.mark.parametrize(
    "broken",
    [
        "our_pair_twice",
        "their_pair_twice",
        "unknown_room",
        "unknown_plan",
        "plan_does_not_sell_room",
        "unknown_channel_room",
        "rate_of_another_channel_room",
        "extra_field",
    ],
)
async def test_a_matching_that_does_not_add_up_is_refused_whole(pg_client, broken) -> None:
    ctx = await _property(pg_client)
    connection = await connect_channel(pg_client)
    good = _pair(ctx, "deluxe", "normal", "R1", "P1")
    pairs = {
        "our_pair_twice": [good, {**good, "external_rate_id": "P2"}],
        "their_pair_twice": [good, {**_pair(ctx, "suite", "normal", "R1", "P1")}],
        "unknown_room": [good, {**good, "room_type_id": MISSING, "external_rate_id": "P2"}],
        "unknown_plan": [good, {**good, "rate_plan_id": MISSING, "external_rate_id": "P2"}],
        "plan_does_not_sell_room": [good, _pair(ctx, "suite", "hemat", "R2", "P3")],
        "unknown_channel_room": [good, _pair(ctx, "suite", "normal", "R9", "P3")],
        "rate_of_another_channel_room": [good, _pair(ctx, "suite", "normal", "R2", "P1")],
        "extra_field": [{**good, "markup": 5}],
    }[broken]

    response = await _save(pg_client, connection, pairs)

    assert response.status_code == 422
    detail = (await pg_client.get(f"{CONNECTIONS}/{connection['id']}")).json()
    assert detail["mappings"] == []  # the good pair was not saved either


async def test_matching_needs_a_tested_connection(pg_client) -> None:
    ctx = await _property(pg_client)
    draft = await connect_channel(pg_client, tested=False)

    save = await _save(pg_client, draft, [_pair(ctx, "deluxe", "normal", "R1", "P1")])
    products = await pg_client.get(f"{CONNECTIONS}/{draft['id']}/products")

    assert (save.status_code, products.status_code) == (409, 409)


async def test_matching_can_change_while_live_and_paused(pg_client) -> None:
    ctx = await _property(pg_client)
    connection = await connect_channel(pg_client)
    await _save(pg_client, connection, [_pair(ctx, "deluxe", "normal", "R1", "P1")])
    await pg_client.post(f"{CONNECTIONS}/{connection['id']}/go-live")

    live = await _save(pg_client, connection, [_pair(ctx, "deluxe", "hemat", "R1", "P2")])
    await pg_client.post(f"{CONNECTIONS}/{connection['id']}/pause")
    paused = await _save(pg_client, connection, [])

    assert (live.status_code, paused.status_code) == (200, 200)
    assert paused.json()["status"] == "paused"


async def test_a_room_switched_off_later_is_a_warning_not_an_error(pg_client) -> None:
    ctx = await _property(pg_client)
    connection = await connect_channel(pg_client)
    pair = _pair(ctx, "suite", "normal", "R2", "P3")
    await _save(pg_client, connection, [pair])

    await pg_client.patch(f"/api/room-types/{ctx['suite']['id']}", json={"is_active": False})
    detail = await pg_client.get(f"{CONNECTIONS}/{connection['id']}")

    assert detail.status_code == 200
    assert detail.json()["health"]["switched_off"] == [pair]
    assert detail.json()["mappings"] == [pair]


async def test_a_room_the_channel_dropped_shows_as_missing_after_a_refresh(
    pg_client, pg_session
) -> None:
    ctx = await _property(pg_client)
    connection = await connect_channel(pg_client)
    pair = _pair(ctx, "suite", "normal", "R2", "P3")
    await _save(pg_client, connection, [pair])
    await pg_session.execute(
        text(
            "UPDATE channelsimulatorlisting SET rooms = jsonb_path_query_array(rooms, "
            "'$[*] ? (@.id != \"R2\")') WHERE hotel_id = :h"
        ),
        {"h": connection["external_property_id"]},
    )
    await pg_session.commit()

    await pg_client.get(f"{CONNECTIONS}/{connection['id']}/products")
    detail = (await pg_client.get(f"{CONNECTIONS}/{connection['id']}")).json()

    assert detail["health"]["missing_on_channel"] == [pair]
    assert [room["id"] for room in detail["products"]["rooms"]] == ["R1", "R3"]


async def test_too_many_pairs_are_refused(pg_client) -> None:
    ctx = await _property(pg_client)
    connection = await connect_channel(pg_client)
    pairs = [{**_pair(ctx, "deluxe", "normal", f"R{n}", "P1")} for n in range(501)]

    assert (await _save(pg_client, connection, pairs)).status_code == 422
