"""Room types: what the property sells, and how many units of each."""

import pytest

from tests.pg.conftest import make_room_type, set_business_settings, start_workspace

pytestmark = pytest.mark.integration

ROOMS = "/api/room-types"


async def test_requires_sign_in(pg_client) -> None:
    assert (await pg_client.get(ROOMS)).status_code == 401


async def test_create_makes_the_units(pg_client) -> None:
    await start_workspace(pg_client)

    room = await make_room_type(pg_client, name="Deluxe Garden", kind="villa", units=3)

    assert room["name"] == "Deluxe Garden"
    assert (room["kind"], room["max_guests"], room["is_active"]) == ("villa", 2, True)
    assert [unit["name"] for unit in room["units"]] == [
        "Deluxe Garden 1",
        "Deluxe Garden 2",
        "Deluxe Garden 3",
    ]
    assert (await pg_client.get(ROOMS)).json() == [room]


async def test_list_is_in_creation_order_and_keeps_switched_off_ones(pg_client) -> None:
    await start_workspace(pg_client)
    first = await make_room_type(pg_client, name="Standar")
    await make_room_type(pg_client, name="Suite")
    await pg_client.patch(f"{ROOMS}/{first['id']}", json={"is_active": False})

    listed = (await pg_client.get(ROOMS)).json()

    assert [(room["name"], room["is_active"]) for room in listed] == [
        ("Standar", False),
        ("Suite", True),
    ]


async def test_rename_carries_the_untouched_unit_names(pg_client) -> None:
    await start_workspace(pg_client)
    room = await make_room_type(pg_client, name="Deluxe", units=2)
    unit = room["units"][0]
    renamed_unit = await pg_client.patch(
        f"{ROOMS}/{room['id']}/units/{unit['id']}", json={"name": "Kamar Melati"}
    )

    response = await pg_client.patch(f"{ROOMS}/{room['id']}", json={"name": "Superior"})

    assert renamed_unit.status_code == 200
    assert response.status_code == 200
    assert [u["name"] for u in response.json()["units"]] == ["Kamar Melati", "Superior 2"]


async def test_raising_the_count_adds_units(pg_client) -> None:
    await start_workspace(pg_client)
    room = await make_room_type(pg_client, units=2)

    response = await pg_client.patch(f"{ROOMS}/{room['id']}", json={"units": 4})

    assert [u["name"] for u in response.json()["units"]] == [
        "Deluxe 1",
        "Deluxe 2",
        "Deluxe 3",
        "Deluxe 4",
    ]


async def test_lowering_the_count_retires_the_last_units_and_raising_brings_them_back(
    pg_client,
) -> None:
    await start_workspace(pg_client)
    room = await make_room_type(pg_client, units=3)
    last = room["units"][2]
    await pg_client.patch(f"{ROOMS}/{room['id']}/units/{last['id']}", json={"name": "Pojok"})

    lowered = (await pg_client.patch(f"{ROOMS}/{room['id']}", json={"units": 1})).json()
    raised = (await pg_client.patch(f"{ROOMS}/{room['id']}", json={"units": 3})).json()

    assert [u["name"] for u in lowered["units"]] == ["Deluxe 1"]
    assert [u["name"] for u in raised["units"]] == ["Deluxe 1", "Deluxe 2", "Pojok"]
    assert [u["id"] for u in raised["units"]] == [u["id"] for u in room["units"]]


async def test_guest_capacity_can_change(pg_client) -> None:
    await start_workspace(pg_client)
    room = await make_room_type(pg_client, max_guests=2)

    response = await pg_client.patch(f"{ROOMS}/{room['id']}", json={"max_guests": 6})

    assert response.json()["max_guests"] == 6


async def test_name_must_be_unique_among_active_room_types(pg_client) -> None:
    await start_workspace(pg_client)
    first = await make_room_type(pg_client, name="Deluxe")
    second = await make_room_type(pg_client, name="Suite")

    duplicate = await pg_client.post(
        ROOMS, json={"name": " deluxe ", "kind": "room", "units": 1, "max_guests": 2}
    )
    rename = await pg_client.patch(f"{ROOMS}/{second['id']}", json={"name": "DELUXE"})
    await pg_client.patch(f"{ROOMS}/{first['id']}", json={"is_active": False})
    after_off = await pg_client.post(
        ROOMS, json={"name": "Deluxe", "kind": "room", "units": 1, "max_guests": 2}
    )
    back_on = await pg_client.patch(f"{ROOMS}/{first['id']}", json={"is_active": True})

    assert (duplicate.status_code, rename.status_code) == (409, 409)
    assert "already" in duplicate.json()["detail"]
    assert after_off.status_code == 201
    assert back_on.status_code == 409


@pytest.mark.parametrize(
    "payload",
    [
        {"name": "", "kind": "room", "units": 1, "max_guests": 2},
        {"name": "x" * 81, "kind": "room", "units": 1, "max_guests": 2},
        {"name": "Baris\nBaru", "kind": "room", "units": 1, "max_guests": 2},
        {"name": "A", "kind": "castle", "units": 1, "max_guests": 2},
        {"name": "A", "kind": "room", "units": 0, "max_guests": 2},
        {"name": "A", "kind": "room", "units": 1, "max_guests": 0},
        {"name": "A", "kind": "room", "units": 1, "max_guests": 2, "code": "x"},
        {"name": "A", "kind": "room", "units": 1},
    ],
)
async def test_validation(pg_client, payload) -> None:
    await start_workspace(pg_client)

    assert (await pg_client.post(ROOMS, json=payload)).status_code == 422


async def test_limits_are_property_settings(pg_client, pg_session) -> None:
    workspace = await start_workspace(pg_client)
    property_id = workspace["property"]["id"]
    await set_business_settings(
        pg_session, property_id, max_room_types=1, max_units_per_room_type=2
    )

    too_many_units = await pg_client.post(
        ROOMS, json={"name": "A", "kind": "room", "units": 3, "max_guests": 2}
    )
    room = await make_room_type(pg_client, name="A", units=2)
    raise_units = await pg_client.patch(f"{ROOMS}/{room['id']}", json={"units": 3})
    second = await pg_client.post(
        ROOMS, json={"name": "B", "kind": "room", "units": 1, "max_guests": 2}
    )

    assert too_many_units.status_code == 422
    assert "at most 2 units" in too_many_units.json()["detail"]
    assert raise_units.status_code == 422
    assert second.status_code == 409
    assert "at most 1 room type" in second.json()["detail"]


async def test_a_switched_off_room_type_does_not_count_toward_the_limit(
    pg_client, pg_session
) -> None:
    workspace = await start_workspace(pg_client)
    property_id = workspace["property"]["id"]
    await set_business_settings(pg_session, property_id, max_room_types=1)
    room = await make_room_type(pg_client, name="A")
    await pg_client.patch(f"{ROOMS}/{room['id']}", json={"is_active": False})

    second = await make_room_type(pg_client, name="B")
    back_on = await pg_client.patch(f"{ROOMS}/{room['id']}", json={"is_active": True})

    assert second["is_active"] is True
    assert back_on.status_code == 409


async def test_unknown_ids_are_404(pg_client) -> None:
    await start_workspace(pg_client)
    room = await make_room_type(pg_client)
    missing = "00000000-0000-0000-0000-000000000000"

    assert (await pg_client.patch(f"{ROOMS}/{missing}", json={"name": "X"})).status_code == 404
    assert (
        await pg_client.patch(f"{ROOMS}/{room['id']}/units/{missing}", json={"name": "X"})
    ).status_code == 404


async def test_another_property_cannot_see_or_change_them(pg_client, other_client) -> None:
    await start_workspace(pg_client)
    await start_workspace(other_client)
    room = await make_room_type(pg_client, name="Milik Saya")
    unit = room["units"][0]

    listed = (await other_client.get(ROOMS)).json()
    patch = await other_client.patch(f"{ROOMS}/{room['id']}", json={"name": "Dicuri"})
    unit_patch = await other_client.patch(
        f"{ROOMS}/{room['id']}/units/{unit['id']}", json={"name": "Dicuri"}
    )
    same_name = await other_client.post(
        ROOMS, json={"name": "Milik Saya", "kind": "room", "units": 1, "max_guests": 2}
    )

    assert listed == []
    assert (patch.status_code, unit_patch.status_code) == (404, 404)
    assert same_name.status_code == 201
    assert (await pg_client.get(ROOMS)).json()[0]["name"] == "Milik Saya"


async def test_empty_patch_changes_nothing(pg_client) -> None:
    await start_workspace(pg_client)
    room = await make_room_type(pg_client)

    response = await pg_client.patch(f"{ROOMS}/{room['id']}", json={})

    assert response.status_code == 200
    assert response.json() == room


@pytest.mark.parametrize("name", ["Suite\u202eetiuS", "Zero\u200bWidth", "C1\u0085Control"])
async def test_names_cannot_hide_characters(pg_client, name) -> None:
    await start_workspace(pg_client)

    response = await pg_client.post(
        ROOMS, json={"name": name, "kind": "room", "units": 1, "max_guests": 2}
    )

    assert response.status_code == 422


async def test_names_in_other_scripts_are_fine(pg_client) -> None:
    await start_workspace(pg_client)

    room = await make_room_type(pg_client, name="Vila Bambu – ꦗꦮ 竹")

    assert room["name"] == "Vila Bambu – ꦗꦮ 竹"


async def test_switched_off_room_types_cannot_pile_up_without_end(pg_client, pg_session) -> None:
    workspace = await start_workspace(pg_client)
    await set_business_settings(
        pg_session, workspace["property"]["id"], max_room_types=1, switched_off_allowance=2
    )
    for name in ("A", "B"):
        room = await make_room_type(pg_client, name=name)
        await pg_client.patch(f"{ROOMS}/{room['id']}", json={"is_active": False})

    third = await pg_client.post(
        ROOMS, json={"name": "C", "kind": "room", "units": 1, "max_guests": 2}
    )
    reuse = await pg_client.patch(f"{ROOMS}/{room['id']}", json={"is_active": True, "name": "C"})

    assert third.status_code == 409
    assert "Switch one back on" in third.json()["detail"]
    assert reuse.status_code == 200


async def test_unit_names_stay_unique_over_several_raise_and_lower_cycles(pg_client) -> None:
    await start_workspace(pg_client)
    room = await make_room_type(pg_client, units=2)
    names = []
    for units in (4, 1, 3, 5, 2, 6):
        response = await pg_client.patch(f"{ROOMS}/{room['id']}", json={"units": units})
        assert response.status_code == 200, response.text
        names = [unit["name"] for unit in response.json()["units"]]
        assert len(names) == units

    assert names == [f"Deluxe {n}" for n in range(1, 7)]
