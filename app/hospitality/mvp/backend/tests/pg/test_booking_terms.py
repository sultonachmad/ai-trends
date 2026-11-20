"""Booking terms: the share of a direct booking paid when booking (the deposit, "DP")."""

import pytest

from tests.pg.conftest import add_staff_member, set_bank_account, start_workspace

pytestmark = pytest.mark.integration

URL = "/api/settings/booking-terms"


async def test_requires_sign_in(pg_client) -> None:
    assert (await pg_client.get(URL)).status_code == 401


async def test_default_is_half(pg_client) -> None:
    await start_workspace(pg_client)

    assert (await pg_client.get(URL)).json() == {"deposit_percent": 50, "can_edit": True}


async def test_owner_changes_it_and_other_settings_survive(pg_client) -> None:
    await start_workspace(pg_client)
    await set_bank_account(pg_client)

    saved = await pg_client.put(URL, json={"deposit_percent": 30})

    assert saved.status_code == 200, saved.text
    assert saved.json() == {"deposit_percent": 30, "can_edit": True}
    assert (await pg_client.get(URL)).json()["deposit_percent"] == 30
    assert (await pg_client.get("/api/settings/bank-account")).json()["bank_name"] == "BCA"
    settings = (await pg_client.get("/api/workspace")).json()["settings"]
    assert settings["direct_deposit_percent"] == 30


@pytest.mark.parametrize("body", [{"deposit_percent": 9}, {"deposit_percent": 101}, {}, {"x": 1}])
async def test_out_of_range_or_malformed_is_refused(pg_client, body) -> None:
    await start_workspace(pg_client)

    assert (await pg_client.put(URL, json=body)).status_code == 422
    assert (await pg_client.get(URL)).json()["deposit_percent"] == 50


@pytest.mark.parametrize("percent", [10, 100])
async def test_the_ends_of_the_range_are_allowed(pg_client, percent) -> None:
    await start_workspace(pg_client)

    assert (await pg_client.put(URL, json={"deposit_percent": percent})).status_code == 200


async def test_only_the_owner_can_change_it(pg_client, other_client, pg_session) -> None:
    workspace = await start_workspace(pg_client)
    await add_staff_member(pg_session, other_client, workspace)

    seen = await other_client.get(URL)
    refused = await other_client.put(URL, json={"deposit_percent": 100})

    assert seen.json() == {"deposit_percent": 50, "can_edit": False}
    assert refused.status_code == 403
    assert (await pg_client.get(URL)).json()["deposit_percent"] == 50
