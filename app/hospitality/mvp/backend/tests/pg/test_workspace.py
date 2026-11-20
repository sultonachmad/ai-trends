"""Workspace summary: own property, Free plan, usage — and nothing from other tenants."""

import datetime as dt
import uuid
from decimal import Decimal

import pytest
from sqlalchemy import text
from sqlmodel import select

from app.models.tenant import PaymentLink, Property
from tests.pg.conftest import onboarding_payload, sign_up_and_in

pytestmark = pytest.mark.integration


async def test_workspace_requires_sign_in(pg_client) -> None:
    assert (await pg_client.get("/api/workspace")).status_code == 401


async def test_workspace_without_onboarding_is_forbidden(pg_client) -> None:
    await sign_up_and_in(pg_client)

    response = await pg_client.get("/api/workspace")

    assert response.status_code == 403
    assert response.json()["detail"] == "This account has no workspace yet"


async def test_workspace_returns_own_property_and_plan(pg_client) -> None:
    email = await sign_up_and_in(pg_client)
    await pg_client.post("/api/onboarding", json=onboarding_payload(property_name="Rumah Bambu"))

    response = await pg_client.get("/api/workspace")

    assert response.status_code == 200
    body = response.json()
    assert body["property"]["name"] == "Rumah Bambu"
    assert body["plan"] == {"code": "free", "name": "Free"}
    usage = body["usage"]
    assert (usage["payment_links_used"], usage["payment_links_limit"]) == (0, 30)
    assert body["is_owner"] is True
    assert body["staff"]["email"] == email
    assert body["settings"]["proof_retention_days"] == 90
    assert body["settings"]["second_approver_threshold_idr"] == "5000000"


async def test_each_user_only_gets_their_own_workspace(pg_client, other_client) -> None:
    await sign_up_and_in(pg_client)
    await sign_up_and_in(other_client)
    await pg_client.post("/api/onboarding", json=onboarding_payload(property_name="Villa A"))
    await other_client.post("/api/onboarding", json=onboarding_payload(property_name="Villa B"))

    first = (await pg_client.get("/api/workspace")).json()
    second = (await other_client.get("/api/workspace")).json()

    assert first["property"]["name"] == "Villa A"
    assert second["property"]["name"] == "Villa B"
    assert first["tenant"]["id"] != second["tenant"]["id"]


async def test_usage_counts_this_months_links_for_this_tenant_only(
    pg_client, other_client, pg_session
) -> None:
    await sign_up_and_in(pg_client)
    await sign_up_and_in(other_client)
    mine = (await pg_client.post("/api/onboarding", json=onboarding_payload())).json()
    theirs = (await other_client.post("/api/onboarding", json=onboarding_payload())).json()
    now = dt.datetime.now(dt.UTC)

    def link(workspace: dict, created_at: dt.datetime) -> PaymentLink:
        return PaymentLink(
            tenant_id=workspace["tenant"]["id"],
            property_id=workspace["property"]["id"],
            amount=Decimal("150000.00"),
            expires_at=now + dt.timedelta(days=1),
            token_hash=f"hash-{uuid.uuid4().hex}",
            created_at=created_at,
        )

    pg_session.add_all(
        [
            link(mine, now),
            link(mine, now),
            link(mine, now - dt.timedelta(days=40)),  # an earlier month: not counted
            link(theirs, now),
        ]
    )
    await pg_session.commit()

    usage = (await pg_client.get("/api/workspace")).json()["usage"]

    assert (usage["payment_links_used"], usage["payment_links_limit"]) == (2, 30)


async def test_property_setting_and_plan_limit_changes_show_without_code_change(
    pg_client, pg_session
) -> None:
    await sign_up_and_in(pg_client)
    workspace = (await pg_client.post("/api/onboarding", json=onboarding_payload())).json()
    prop = (
        await pg_session.exec(select(Property).where(Property.id == workspace["property"]["id"]))
    ).one()
    prop.settings = {"business": {"proof_retention_days": 45}}
    pg_session.add(prop)
    await pg_session.execute(
        text(
            "UPDATE tenantentitlement SET limits = '{\"payment_links_per_month\": 100}' "
            "WHERE tenant_id = :t AND module_code = 'payments'"
        ),
        {"t": workspace["tenant"]["id"]},
    )
    await pg_session.commit()

    body = (await pg_client.get("/api/workspace")).json()

    assert body["settings"]["proof_retention_days"] == 45
    assert body["usage"]["payment_links_limit"] == 100


async def test_workspace_route_runs_inside_the_tenant_scope(pg_client, monkeypatch) -> None:
    """Fails if the route stops binding the restricted role / tenant to its session."""
    from app.routers import workspace as workspace_router_module

    await sign_up_and_in(pg_client)
    created = (await pg_client.post("/api/onboarding", json=onboarding_payload())).json()
    seen: dict[str, str] = {}
    real_get_workspace = workspace_router_module.get_workspace

    async def probing_get_workspace(session, context):
        row = (
            await session.execute(
                text("SELECT current_user, current_setting('app.tenant_id', true)")
            )
        ).one()
        seen["role"], seen["tenant"] = row[0], row[1]
        return await real_get_workspace(session, context)

    monkeypatch.setattr(workspace_router_module, "get_workspace", probing_get_workspace)

    response = await pg_client.get("/api/workspace")

    assert response.status_code == 200
    assert seen == {"role": "app_rw", "tenant": created["tenant"]["id"]}


async def test_invalid_stored_setting_gives_a_clear_error(pg_client, pg_session) -> None:
    await sign_up_and_in(pg_client)
    workspace = (await pg_client.post("/api/onboarding", json=onboarding_payload())).json()
    await pg_session.execute(
        text(
            'UPDATE property SET settings = \'{"business": {"no_such_setting": 1}}\' WHERE id = :p'
        ),
        {"p": workspace["property"]["id"]},
    )
    await pg_session.commit()

    response = await pg_client.get("/api/workspace")

    assert response.status_code == 500
    assert (
        response.json()["detail"]
        == "This workspace has an invalid setting. Please contact support."
    )


async def test_no_payments_module_means_no_payment_links(pg_client, pg_session) -> None:
    await sign_up_and_in(pg_client)
    workspace = (await pg_client.post("/api/onboarding", json=onboarding_payload())).json()
    await pg_session.execute(
        text(
            "UPDATE tenantentitlement SET enabled = false "
            "WHERE tenant_id = :t AND module_code = 'payments'"
        ),
        {"t": workspace["tenant"]["id"]},
    )
    await pg_session.commit()

    usage = (await pg_client.get("/api/workspace")).json()["usage"]

    assert usage["payment_links_limit"] == 0
