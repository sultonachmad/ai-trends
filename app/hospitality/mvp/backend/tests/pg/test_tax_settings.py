"""Tax settings: nothing is taxed until confirmed; rates apply from a date."""

import datetime as dt

import pytest
from sqlalchemy import text

from app.services.calendar_dates import property_today
from tests.pg.conftest import add_staff_member, start_workspace

pytestmark = pytest.mark.integration

URL = "/api/settings/taxes"


def _body(today: dt.date, **over) -> dict:
    return {
        "region_code": "51.03",
        "pbjt_pct": "10",
        "service_pct": "10",
        "pbjt_on_service": True,
        "price_mode": "plus_plus",
        "untaxed_categories": ["transport"],
        "effective_from": today.isoformat(),
        "confirmed": True,
        **over,
    }


async def _workspace(client) -> tuple[dict, dt.date]:
    workspace = await start_workspace(client)
    return workspace, property_today(workspace["property"]["timezone"])


async def test_nothing_is_set_at_first_and_regions_are_offered(pg_client) -> None:
    await _workspace(pg_client)

    read = (await pg_client.get(URL)).json()

    assert read["confirmed"] is False
    codes = {region["code"] for region in read["regions"]}
    assert {"51.03", "51.71", "31.71", "34.71", "32.73", "35.78", "other"} <= codes
    assert all(region["verified"] is False for region in read["regions"])


async def test_saving_needs_confirmation_and_sane_rates(pg_client) -> None:
    _, today = await _workspace(pg_client)

    for bad in (
        {"confirmed": False},
        {"pbjt_pct": "10.5"},
        {"service_pct": "16"},
        {"region_code": "99.99"},
        {"effective_from": (today - dt.timedelta(days=1)).isoformat()},
        {"untaxed_categories": ["room"]},
    ):
        response = await pg_client.put(URL, json=_body(today, **bad))
        assert response.status_code == 422, (bad, response.text)


async def test_saved_rates_read_back_and_are_in_the_history(pg_client, pg_session) -> None:
    workspace, today = await _workspace(pg_client)

    saved = await pg_client.put(URL, json=_body(today))

    assert saved.status_code == 200, saved.text
    body = saved.json()
    assert (body["confirmed"], body["pbjt_pct"], body["service_pct"], body["price_mode"]) == (
        True,
        "10.00",
        "10.00",
        "plus_plus",
    )
    logged = await pg_session.execute(
        text(
            "SELECT count(*) FROM tenantauditentry "
            "WHERE event_id = 'taxes.updated' AND tenant_id = :t"
        ),
        {"t": workspace["tenant"]["id"]},
    )
    assert logged.scalar_one() == 1


async def test_a_later_change_waits_for_its_date(pg_client) -> None:
    _, today = await _workspace(pg_client)
    await pg_client.put(URL, json=_body(today))
    later = (today + dt.timedelta(days=30)).isoformat()

    changed = await pg_client.put(URL, json=_body(today, pbjt_pct="5", effective_from=later))

    body = changed.json()
    assert body["pbjt_pct"] == "10.00"
    assert (body["upcoming"]["effective_from"], body["upcoming"]["pbjt_pct"]) == (later, "5.00")


async def test_saving_twice_on_one_day_replaces_the_rates(pg_client) -> None:
    _, today = await _workspace(pg_client)
    await pg_client.put(URL, json=_body(today))

    again = await pg_client.put(URL, json=_body(today, pbjt_pct="8"))

    assert again.status_code == 200, again.text
    assert again.json()["pbjt_pct"] == "8.00"


async def test_tax_settings_need_permission(pg_client, other_client, pg_session) -> None:
    workspace, today = await _workspace(pg_client)
    await add_staff_member(pg_session, other_client, workspace, role=None)

    assert (await other_client.get(URL)).status_code == 403
    assert (await other_client.put(URL, json=_body(today))).status_code == 403


async def test_only_the_owner_changes_taxes(pg_client, other_client, pg_session) -> None:
    workspace, today = await _workspace(pg_client)
    await add_staff_member(pg_session, other_client, workspace)  # a manager

    read = await other_client.get(URL)
    changed = await other_client.put(URL, json=_body(today))

    assert (read.status_code, read.json()["can_edit"]) == (200, False)
    assert changed.status_code == 403


async def test_saving_today_keeps_a_scheduled_change(pg_client) -> None:
    _, today = await _workspace(pg_client)
    later = (today + dt.timedelta(days=30)).isoformat()
    await pg_client.put(URL, json=_body(today))
    await pg_client.put(URL, json=_body(today, pbjt_pct="5", effective_from=later))

    again = await pg_client.put(URL, json=_body(today, service_pct="5"))

    body = again.json()
    assert (body["service_pct"], body["upcoming"]["effective_from"]) == ("5.00", later)
    assert body["upcoming"]["pbjt_pct"] == "5.00"


async def test_the_history_shows_before_and_after(pg_client, pg_session) -> None:
    workspace, today = await _workspace(pg_client)
    await pg_client.put(URL, json=_body(today))
    await pg_client.put(URL, json=_body(today, pbjt_pct="8", untaxed_categories=[]))

    rows = await pg_session.execute(
        text(
            "SELECT payload FROM tenantauditentry WHERE event_id = 'taxes.updated' "
            "AND tenant_id = :t ORDER BY occurred_at DESC LIMIT 1"
        ),
        {"t": workspace["tenant"]["id"]},
    )
    payload = rows.scalar_one()
    assert (payload["before"]["pbjt_pct"], payload["pbjt_pct"]) == ("10.00", "8")
    assert payload["untaxed_categories"] == []
