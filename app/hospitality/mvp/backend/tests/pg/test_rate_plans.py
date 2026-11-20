"""Rate plans: a name, terms, and a base nightly price for each room type they sell."""

import pytest
from sqlalchemy import text

from tests.pg.conftest import (
    make_rate_plan,
    make_room_type,
    set_business_settings,
    start_workspace,
)

pytestmark = pytest.mark.integration

PLANS = "/api/rate-plans"
MISSING = "00000000-0000-0000-0000-000000000000"


async def _two_rooms(client) -> tuple[dict, dict]:
    return (
        await make_room_type(client, name="Deluxe"),
        await make_room_type(client, name="Suite"),
    )


def _prices(plan: dict) -> dict[str, str]:
    return {price["room_type_id"]: price["amount"] for price in plan["prices"]}


async def test_requires_sign_in(pg_client) -> None:
    assert (await pg_client.get(PLANS)).status_code == 401


async def test_create_with_a_price_per_room_type(pg_client) -> None:
    await start_workspace(pg_client)
    deluxe, suite = await _two_rooms(pg_client)

    response = await pg_client.post(
        PLANS,
        json={
            "name": "Harga Normal",
            "meal_plan": "breakfast",
            "prices": [
                {"room_type_id": deluxe["id"], "amount": 750000},
                {"room_type_id": suite["id"], "amount": 1250000},
            ],
        },
    )

    assert response.status_code == 201, response.text
    plan = response.json()
    assert (plan["name"], plan["meal_plan"], plan["is_active"]) == (
        "Harga Normal",
        "breakfast",
        True,
    )
    assert (plan["non_refundable"], plan["free_cancellation_days"]) == (False, 7)
    assert _prices(plan) == {deluxe["id"]: "750000.00", suite["id"]: "1250000.00"}
    assert (await pg_client.get(PLANS)).json() == [plan]


async def test_cancellation_terms(pg_client) -> None:
    await start_workspace(pg_client)
    deluxe, _suite = await _two_rooms(pg_client)

    strict = await make_rate_plan(pg_client, [deluxe], name="Hemat", non_refundable=True)
    loose = await make_rate_plan(pg_client, [deluxe], name="Fleksibel", free_cancellation_days=1)
    changed = (
        await pg_client.patch(f"{PLANS}/{strict['id']}", json={"non_refundable": False})
    ).json()
    longer = (
        await pg_client.patch(f"{PLANS}/{loose['id']}", json={"free_cancellation_days": 14})
    ).json()

    assert (strict["non_refundable"], strict["free_cancellation_days"]) == (True, None)
    assert (loose["non_refundable"], loose["free_cancellation_days"]) == (False, 1)
    assert (changed["non_refundable"], changed["free_cancellation_days"]) == (False, 7)
    assert longer["free_cancellation_days"] == 14


async def test_default_free_cancellation_days_is_a_property_setting(pg_client, pg_session) -> None:
    workspace = await start_workspace(pg_client)
    await set_business_settings(pg_session, workspace["property"]["id"], free_cancellation_days=3)
    deluxe = await make_room_type(pg_client)

    plan = await make_rate_plan(pg_client, [deluxe])

    assert plan["free_cancellation_days"] == 3


async def test_plans_with_the_same_terms_share_the_terms_record(pg_client, pg_session) -> None:
    workspace = await start_workspace(pg_client)
    deluxe = await make_room_type(pg_client)
    await make_rate_plan(pg_client, [deluxe], name="A")
    await make_rate_plan(pg_client, [deluxe], name="B")
    await make_rate_plan(pg_client, [deluxe], name="C", non_refundable=True)

    counts = (
        await pg_session.execute(
            text(
                "SELECT (SELECT count(*) FROM cancellationpolicy WHERE tenant_id = :t), "
                "(SELECT count(*) FROM paymentpolicy WHERE tenant_id = :t)"
            ),
            {"t": workspace["tenant"]["id"]},
        )
    ).one()

    assert tuple(counts) == (2, 1)


async def test_update_prices_replaces_the_set(pg_client, pg_session) -> None:
    workspace = await start_workspace(pg_client)
    deluxe, suite = await _two_rooms(pg_client)
    plan = await make_rate_plan(pg_client, [deluxe, suite], amount=500000)

    response = await pg_client.patch(
        f"{PLANS}/{plan['id']}",
        json={"prices": [{"room_type_id": suite["id"], "amount": 900000}]},
    )

    assert response.status_code == 200, response.text
    assert _prices(response.json()) == {suite["id"]: "900000.00"}
    links = (
        await pg_session.execute(
            text("SELECT count(*) FROM rateplanunittype WHERE tenant_id = :t"),
            {"t": workspace["tenant"]["id"]},
        )
    ).scalar_one()
    assert links == 1


async def test_a_switched_off_room_type_keeps_its_price(pg_client) -> None:
    await start_workspace(pg_client)
    deluxe, suite = await _two_rooms(pg_client)
    plan = await make_rate_plan(pg_client, [deluxe, suite], amount=500000)
    await pg_client.patch(f"/api/room-types/{suite['id']}", json={"is_active": False})

    # the form only lists room types in use, so the saved set leaves the suite out
    await pg_client.patch(
        f"{PLANS}/{plan['id']}",
        json={"prices": [{"room_type_id": deluxe["id"], "amount": 650000}]},
    )
    await pg_client.patch(f"/api/room-types/{suite['id']}", json={"is_active": True})

    [after] = (await pg_client.get(PLANS)).json()
    assert _prices(after) == {deluxe["id"]: "650000.00", suite["id"]: "500000.00"}


async def test_rename_meal_and_switch_off(pg_client) -> None:
    await start_workspace(pg_client)
    deluxe = await make_room_type(pg_client)
    plan = await make_rate_plan(pg_client, [deluxe])

    response = await pg_client.patch(
        f"{PLANS}/{plan['id']}",
        json={"name": "Promo Akhir Pekan", "meal_plan": "breakfast", "is_active": False},
    )

    body = response.json()
    assert (body["name"], body["meal_plan"], body["is_active"]) == (
        "Promo Akhir Pekan",
        "breakfast",
        False,
    )
    assert body["prices"] == plan["prices"]
    assert [p["is_active"] for p in (await pg_client.get(PLANS)).json()] == [False]


async def test_name_must_be_unique_among_active_plans(pg_client) -> None:
    await start_workspace(pg_client)
    deluxe = await make_room_type(pg_client)
    first = await make_rate_plan(pg_client, [deluxe], name="Normal")
    price = [{"room_type_id": deluxe["id"], "amount": 500000}]

    duplicate = await pg_client.post(PLANS, json={"name": "normal", "prices": price})
    await pg_client.patch(f"{PLANS}/{first['id']}", json={"is_active": False})
    after_off = await pg_client.post(PLANS, json={"name": "Normal", "prices": price})
    back_on = await pg_client.patch(f"{PLANS}/{first['id']}", json={"is_active": True})

    assert duplicate.status_code == 409
    assert after_off.status_code == 201
    assert back_on.status_code == 409


async def test_price_must_be_within_the_property_range(pg_client, pg_session) -> None:
    workspace = await start_workspace(pg_client)
    await set_business_settings(
        pg_session,
        workspace["property"]["id"],
        room_rate_min_amount_idr=100000,
        room_rate_max_amount_idr=2000000,
    )
    deluxe = await make_room_type(pg_client)

    statuses = []
    for amount in (99999, 100000, 2000000, 2000001):
        response = await pg_client.post(
            PLANS,
            json={
                "name": f"Harga {amount}",
                "prices": [{"room_type_id": deluxe["id"], "amount": amount}],
            },
        )
        statuses.append(response.status_code)

    assert statuses == [422, 201, 201, 422]
    assert "Rp 100.000" in response.json()["detail"]


async def test_room_type_must_be_ours_and_in_use(pg_client, other_client) -> None:
    await start_workspace(pg_client)
    await start_workspace(other_client)
    mine = await make_room_type(pg_client)
    theirs = await make_room_type(other_client)
    off = await make_room_type(pg_client, name="Lama")
    await pg_client.patch(f"/api/room-types/{off['id']}", json={"is_active": False})

    statuses = []
    for room_type_id in (theirs["id"], off["id"], MISSING):
        response = await pg_client.post(
            PLANS,
            json={"name": "X", "prices": [{"room_type_id": room_type_id, "amount": 500000}]},
        )
        statuses.append(response.status_code)
    ok = await make_rate_plan(pg_client, [mine])

    assert statuses == [422, 422, 422]
    assert ok["is_active"] is True


@pytest.mark.parametrize(
    "change",
    [
        {"name": ""},
        {"name": "a\tb"},
        {"meal_plan": "all_you_can_eat"},
        {"prices": []},
        {"prices": "DUPLICATE"},
        {"prices": "DECIMAL"},
        {"free_cancellation_days": -1},
        {"free_cancellation_days": 366},
        {"non_refundable": True, "free_cancellation_days": 3},
        {"code": "x"},
    ],
)
async def test_validation(pg_client, change) -> None:
    await start_workspace(pg_client)
    deluxe = await make_room_type(pg_client)
    price = {"room_type_id": deluxe["id"], "amount": 500000}
    if change.get("prices") == "DUPLICATE":
        change = {"prices": [price, price]}
    elif change.get("prices") == "DECIMAL":
        change = {"prices": [{**price, "amount": "500000.50"}]}

    response = await pg_client.post(PLANS, json={"name": "Normal", "prices": [price], **change})

    assert response.status_code == 422


async def test_limit_is_a_property_setting(pg_client, pg_session) -> None:
    workspace = await start_workspace(pg_client)
    await set_business_settings(pg_session, workspace["property"]["id"], max_rate_plans=1)
    deluxe = await make_room_type(pg_client)
    await make_rate_plan(pg_client, [deluxe], name="A")

    second = await pg_client.post(
        PLANS, json={"name": "B", "prices": [{"room_type_id": deluxe["id"], "amount": 500000}]}
    )

    assert second.status_code == 409
    assert "at most 1 rate plan" in second.json()["detail"]


async def test_another_property_cannot_see_or_change_them(pg_client, other_client) -> None:
    await start_workspace(pg_client)
    await start_workspace(other_client)
    deluxe = await make_room_type(pg_client)
    plan = await make_rate_plan(pg_client, [deluxe])

    listed = (await other_client.get(PLANS)).json()
    patch = await other_client.patch(f"{PLANS}/{plan['id']}", json={"name": "Dicuri"})

    assert listed == []
    assert patch.status_code == 404
    assert (await pg_client.get(PLANS)).json()[0]["name"] == "Harga Normal"


async def test_unknown_plan_is_404(pg_client) -> None:
    await start_workspace(pg_client)

    assert (await pg_client.patch(f"{PLANS}/{MISSING}", json={"name": "X"})).status_code == 404


async def test_switched_off_plans_cannot_pile_up_without_end(pg_client, pg_session) -> None:
    workspace = await start_workspace(pg_client)
    await set_business_settings(
        pg_session, workspace["property"]["id"], max_rate_plans=1, switched_off_allowance=2
    )
    deluxe = await make_room_type(pg_client)
    for name in ("A", "B"):
        plan = await make_rate_plan(pg_client, [deluxe], name=name)
        await pg_client.patch(f"{PLANS}/{plan['id']}", json={"is_active": False})

    third = await pg_client.post(
        PLANS, json={"name": "C", "prices": [{"room_type_id": deluxe["id"], "amount": 500000}]}
    )

    assert third.status_code == 409
    assert "Switch one back on" in third.json()["detail"]
