"""One property can never see or touch another property's channel connections."""

import importlib.util
from pathlib import Path

import pytest
from sqlalchemy import text

from tests.pg.conftest import (
    connect_channel,
    make_rate_plan,
    make_room_type,
    make_test_listing,
    start_workspace,
)

pytestmark = pytest.mark.integration

CONNECTIONS = "/api/channel-connections"


async def _property(client) -> dict:
    workspace = await start_workspace(client)
    room = await make_room_type(client)
    plan = await make_rate_plan(client, [room])
    connection = await connect_channel(client)
    return {"workspace": workspace, "room": room, "plan": plan, "connection": connection}


async def test_each_property_sees_only_its_own_connections_and_usage(
    pg_client, other_client
) -> None:
    mine = await _property(pg_client)
    await start_workspace(other_client)

    their_list = (await other_client.get(CONNECTIONS)).json()
    their_usage = (await other_client.get("/api/channels")).json()["usage"]
    their_listings = (await other_client.get("/api/simulator/channels/listings")).json()

    assert (their_list, their_listings) == ([], [])
    assert their_usage["used"] == 0
    assert [c["id"] for c in (await pg_client.get(CONNECTIONS)).json()] == [
        mine["connection"]["id"]
    ]


async def test_another_propertys_connection_cannot_be_read_or_changed(
    pg_client, other_client
) -> None:
    theirs = await _property(other_client)
    await start_workspace(pg_client)
    target = f"{CONNECTIONS}/{theirs['connection']['id']}"

    statuses = [
        (await pg_client.get(target)).status_code,
        (await pg_client.patch(target, json={"commission_percent": 1})).status_code,
        (await pg_client.put(f"{target}/mappings", json={"mappings": []})).status_code,
        (await pg_client.get(f"{target}/products")).status_code,
        *[
            (await pg_client.post(f"{target}/{action}")).status_code
            for action in ("test", "go-live", "pause", "resume", "disconnect")
        ],
    ]

    assert statuses == [404] * 9
    after = (await other_client.get(target)).json()
    assert (after["status"], after["commission_percent"]) == ("testing", "0.00")


async def test_another_tenants_listing_id_does_not_connect(pg_client, other_client) -> None:
    await start_workspace(other_client)
    their_listing = await make_test_listing(other_client)
    await start_workspace(pg_client)

    created = (
        await pg_client.post(
            CONNECTIONS,
            json={"channel_code": "simulator", "external_property_id": their_listing["hotel_id"]},
        )
    ).json()
    tested = (await pg_client.post(f"{CONNECTIONS}/{created['id']}/test")).json()

    assert (tested["status"], tested["problem"]) == ("error", "unknown_property")
    assert tested["products"] is None


async def test_matching_cannot_use_another_propertys_rooms_or_plans(
    pg_client, other_client
) -> None:
    mine = await _property(pg_client)
    theirs = await _property(other_client)
    target = f"{CONNECTIONS}/{mine['connection']['id']}/mappings"

    statuses = [
        (
            await pg_client.put(
                target,
                json={
                    "mappings": [
                        {
                            "room_type_id": room,
                            "rate_plan_id": plan,
                            "external_room_id": "R1",
                            "external_rate_id": "P1",
                        }
                    ]
                },
            )
        ).status_code
        for room, plan in (
            (theirs["room"]["id"], mine["plan"]["id"]),
            (mine["room"]["id"], theirs["plan"]["id"]),
            (theirs["room"]["id"], theirs["plan"]["id"]),
        )
    ]

    assert statuses == [422, 422, 422]


async def test_the_listing_table_is_isolated_at_the_database(
    pg_client, other_client, pg_session
) -> None:
    mine = await start_workspace(pg_client)
    await make_test_listing(pg_client)
    theirs = await start_workspace(other_client)

    async def visible_as(tenant_id: str) -> int:
        await pg_session.execute(text("SET LOCAL ROLE app_rw"))
        await pg_session.execute(
            text("SELECT set_config('app.tenant_id', :t, true)"), {"t": tenant_id}
        )
        count = (
            await pg_session.execute(text("SELECT count(*) FROM channelsimulatorlisting"))
        ).scalar_one()
        await pg_session.rollback()
        return int(count)

    assert await visible_as(mine["tenant"]["id"]) == 1
    assert await visible_as(theirs["tenant"]["id"]) == 0


async def test_a_tenant_from_before_the_channel_manager_gets_the_free_limit(
    pg_client, pg_session
) -> None:
    workspace = await start_workspace(pg_client)
    tenant_id = workspace["tenant"]["id"]
    await pg_session.execute(
        text(
            "DELETE FROM tenantentitlement WHERE tenant_id = :t AND module_code = 'channel_manager'"
        ),
        {"t": tenant_id},
    )
    await pg_session.commit()
    before = (await pg_client.get("/api/channels")).json()["usage"]

    await pg_session.execute(text(_migration_0009().BACKFILL_ENTITLEMENTS))
    await pg_session.execute(text(_migration_0009().BACKFILL_ENTITLEMENTS))  # safe to repeat
    await pg_session.commit()

    after = (await pg_client.get("/api/channels")).json()["usage"]
    assert before == {"used": 0, "limit": 0, "limit_reached": True}  # not in the plan
    assert after == {"used": 0, "limit": 1, "limit_reached": False}
    rows = (
        await pg_session.execute(
            text(
                "SELECT count(*) FROM tenantentitlement "
                "WHERE tenant_id = :t AND module_code = 'channel_manager'"
            ),
            {"t": tenant_id},
        )
    ).scalar_one()
    assert rows == 1


def _migration_0009():  # noqa: ANN202
    """The migration module, loaded from its file (the folder is not a package)."""
    path = Path(__file__).parents[2] / "migrations" / "versions" / "0009_channel_connections.py"
    spec = importlib.util.spec_from_file_location("migration_0009", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
