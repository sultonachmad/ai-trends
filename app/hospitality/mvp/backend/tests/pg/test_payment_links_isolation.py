"""Payment links never cross tenants, on the staff routes or through the public page."""

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from app.payments.tokens import fingerprint
from app.services import checkout, payment_links
from app.tenancy.session import bind_tenant
from tests.pg.conftest import guest_says, make_link, start_workspace, token_of

pytestmark = pytest.mark.integration


async def test_other_tenant_cannot_reach_a_link_by_id(pg_client, other_client) -> None:
    await start_workspace(pg_client)
    await start_workspace(other_client)
    created = await make_link(pg_client)
    base = f"/api/payment-links/{created['link']['id']}"

    responses = [await other_client.get(base), await other_client.post(f"{base}/cancel")]

    assert [r.status_code for r in responses] == [404, 404]
    assert (await pg_client.get(base)).json()["state"] == "pending"


async def test_lists_and_usage_never_mix_tenants(pg_client, other_client) -> None:
    await start_workspace(pg_client)
    await start_workspace(other_client)
    await make_link(pg_client, description="milik A")
    await make_link(other_client, description="milik B")
    await make_link(other_client, description="milik B juga")

    mine = (await pg_client.get("/api/payment-links")).json()["items"]
    theirs = (await other_client.get("/api/payment-links")).json()["items"]

    assert [i["description"] for i in mine] == ["milik A"]
    assert sorted(i["description"] for i in theirs) == ["milik B", "milik B juga"]
    assert (await pg_client.get("/api/workspace")).json()["usage"]["payment_links_used"] == 1
    assert (await other_client.get("/api/workspace")).json()["usage"]["payment_links_used"] == 2


async def test_cannot_send_a_link_into_another_tenants_conversation(
    pg_client, other_client
) -> None:
    await start_workspace(pg_client)
    await start_workspace(other_client)
    conversation_id = (await guest_says(pg_client, "rahasia A"))["conversation_id"]

    response = await other_client.post(
        "/api/payment-links",
        json={"amount": 850000, "description": "x", "conversation_id": conversation_id},
    )

    assert response.status_code == 404
    assert (await other_client.get("/api/payment-links")).json()["items"] == []
    thread = (await pg_client.get(f"/api/conversations/{conversation_id}/messages")).json()
    assert [m["body"] for m in thread] == ["rahasia A"]


async def test_a_token_only_reveals_its_own_link(pg_client, other_client) -> None:
    await start_workspace(pg_client, property_name="Properti A")
    await start_workspace(other_client, property_name="Properti B")
    token_a = token_of(await make_link(pg_client, description="untuk A"))
    token_b = token_of(await make_link(other_client, description="untuk B"))

    page_a = (await other_client.get(f"/api/pay/{token_a}")).json()  # B's staff opening A's link
    page_b = (await pg_client.get(f"/api/pay/{token_b}")).json()

    assert (page_a["property_name"], page_a["description"]) == ("Properti A", "untuk A")
    assert (page_b["property_name"], page_b["description"]) == ("Properti B", "untuk B")


async def test_staff_routes_run_inside_the_tenant_scope(pg_client, monkeypatch) -> None:
    workspace = await start_workspace(pg_client)
    seen: dict[str, str] = {}
    real = payment_links.list_links

    async def probing(session, context, *args, **kwargs):
        row = (
            await session.execute(
                text("SELECT current_user, current_setting('app.tenant_id', true)")
            )
        ).one()
        seen["role"], seen["tenant"] = row[0], row[1]
        return await real(session, context, *args, **kwargs)

    monkeypatch.setattr(payment_links, "list_links", probing)

    assert (await pg_client.get("/api/payment-links")).status_code == 200
    assert seen == {"role": "app_rw", "tenant": workspace["tenant"]["id"]}


async def test_public_page_runs_as_the_restricted_role_in_the_links_tenant(
    pg_client, monkeypatch
) -> None:
    workspace = await start_workspace(pg_client)
    token = token_of(await make_link(pg_client))
    seen: dict[str, str] = {}
    real = checkout.public_view

    async def probing(scope):
        row = (
            await scope.session.execute(
                text("SELECT current_user, current_setting('app.tenant_id', true)")
            )
        ).one()
        seen["role"], seen["tenant"] = row[0], row[1]
        return await real(scope)

    monkeypatch.setattr(checkout, "public_view", probing)

    assert (await pg_client.get(f"/api/pay/{token}")).status_code == 200
    assert seen == {"role": "app_rw", "tenant": workspace["tenant"]["id"]}


async def test_lookup_function_is_all_an_unscoped_session_can_learn(
    pg_client, pg_session_factory
) -> None:
    workspace = await start_workspace(pg_client)
    token = token_of(await make_link(pg_client))

    async with pg_session_factory() as session:
        await session.execute(text("SET LOCAL ROLE app_rw"))
        found = (
            await session.execute(
                text("SELECT resolve_payment_link(:h)"), {"h": fingerprint(token)}
            )
        ).scalar_one()
        missing = (
            await session.execute(text("SELECT resolve_payment_link(:h)"), {"h": "0" * 64})
        ).scalar_one()
        visible_rows = (
            await session.execute(text("SELECT count(*) FROM paymentlink"))
        ).scalar_one()

    assert str(found) == workspace["tenant"]["id"]
    assert missing is None
    assert visible_rows == 0


async def test_only_the_app_role_may_call_the_lookup_function(pg_session_factory) -> None:
    async with pg_session_factory() as session:
        await session.execute(text("DROP ROLE IF EXISTS hosp_nobody"))
        await session.execute(text("CREATE ROLE hosp_nobody NOLOGIN"))
        await session.commit()
        try:
            await session.execute(text("SET LOCAL ROLE hosp_nobody"))
            with pytest.raises(DBAPIError):
                await session.execute(text("SELECT resolve_payment_link('x')"))
        finally:
            await session.rollback()
            await session.execute(text("DROP ROLE hosp_nobody"))
            await session.commit()


async def test_scoped_public_session_cannot_see_another_tenants_links(
    pg_client, other_client, pg_session_factory
) -> None:
    workspace_a = await start_workspace(pg_client)
    await start_workspace(other_client)
    await make_link(pg_client)
    await make_link(other_client)

    async with pg_session_factory() as session:
        await bind_tenant(session, workspace_a["tenant"]["id"])
        tenants = (
            (await session.execute(text("SELECT DISTINCT tenant_id FROM paymentlink")))
            .scalars()
            .all()
        )

    assert [str(t) for t in tenants] == [workspace_a["tenant"]["id"]]
