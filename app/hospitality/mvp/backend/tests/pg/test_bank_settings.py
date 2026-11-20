"""Bank account details for manual transfer: owner sets them, the pay page shows them."""

import pytest

from tests.pg.conftest import (
    BANK,
    add_staff_member,
    make_link,
    set_bank_account,
    start_workspace,
    token_of,
)

pytestmark = pytest.mark.integration

URL = "/api/settings/bank-account"
EMPTY = {"bank_name": None, "account_number": None, "account_holder": None}


async def test_requires_sign_in(pg_client) -> None:
    assert (await pg_client.get(URL)).status_code == 401
    assert (await pg_client.put(URL, json=BANK)).status_code == 401


async def test_starts_empty_and_owner_can_set_and_clear_it(pg_client) -> None:
    await start_workspace(pg_client)

    assert (await pg_client.get(URL)).json() == {**EMPTY, "can_edit": True}
    saved = await pg_client.put(URL, json={**BANK, "bank_name": "  BCA  "})
    assert saved.status_code == 200
    assert saved.json() == {**BANK, "can_edit": True}
    assert (await pg_client.get(URL)).json() == {**BANK, "can_edit": True}

    cleared = await pg_client.put(URL, json=EMPTY)
    assert cleared.json() == {**EMPTY, "can_edit": True}


@pytest.mark.parametrize(
    "body",
    [
        {**BANK, "account_number": "12-345-678"},
        {**BANK, "account_number": "1234"},
        {**BANK, "account_number": "1" * 31},
        {**BANK, "bank_name": "B"},
        {**BANK, "account_holder": "PT\nVilla"},
        {**BANK, "account_holder": None},
        {"bank_name": "BCA", "account_number": None, "account_holder": None},
        {**BANK, "iban": "x"},
        {"bank_name": "BCA"},
    ],
)
async def test_invalid_details_are_rejected_and_nothing_is_saved(pg_client, body) -> None:
    await start_workspace(pg_client)

    response = await pg_client.put(URL, json=body)

    assert response.status_code == 422, response.text
    assert (await pg_client.get(URL)).json() == {**EMPTY, "can_edit": True}


async def test_only_the_owner_can_change_it(pg_client, other_client, pg_session) -> None:
    workspace = await start_workspace(pg_client)
    await set_bank_account(pg_client)
    await add_staff_member(pg_session, other_client, workspace)

    seen = await other_client.get(URL)
    refused = await other_client.put(URL, json={**BANK, "account_number": "9999999999"})

    assert seen.json() == {**BANK, "can_edit": False}
    assert refused.status_code == 403
    assert "owner" in refused.json()["detail"]
    assert (await pg_client.get(URL)).json()["account_number"] == BANK["account_number"]


async def test_other_settings_survive_a_bank_change(pg_client, pg_session) -> None:
    from sqlalchemy import text

    workspace = await start_workspace(pg_client)
    await pg_session.execute(
        text(
            "UPDATE property SET settings = "
            '\'{"business": {"proof_retention_days": 30}}\' WHERE id = :p'
        ),
        {"p": workspace["property"]["id"]},
    )
    await pg_session.commit()

    await set_bank_account(pg_client)

    settings = (await pg_client.get("/api/workspace")).json()["settings"]
    assert settings["proof_retention_days"] == 30
    assert settings["bank_name"] == "BCA"


async def test_pay_page_offers_manual_transfer_only_when_configured(pg_client, guest) -> None:
    await start_workspace(pg_client)
    token = token_of(await make_link(pg_client))

    before = (await guest.get(f"/api/pay/{token}")).json()
    await set_bank_account(pg_client)
    after = (await guest.get(f"/api/pay/{token}")).json()

    assert before["manual_transfer"] is None
    assert after["manual_transfer"] == {**BANK, "max_upload_mb": 5}
    assert after["proof"] is None


async def test_bank_details_never_cross_tenants(pg_client, other_client) -> None:
    await start_workspace(pg_client)
    await start_workspace(other_client)
    await set_bank_account(pg_client)

    assert (await other_client.get(URL)).json() == {**EMPTY, "can_edit": True}
