"""Onboarding: sign up -> create a property workspace on the Free plan (PRD milestone 1)."""

import pytest
from sqlmodel import select

from app.auth.models import User
from app.models.control_plane import (
    Tenant,
    TenantDatabase,
    TenantEntitlement,
    TenantMembership,
    TenantSubscription,
)
from app.models.tenant import (
    LegalEntity,
    Property,
    StaffMember,
    StaffRole,
    StaffRoleAssignment,
    TenantProfile,
)
from app.services import onboarding as onboarding_service
from tests.pg.conftest import onboarding_payload, sign_up_and_in

pytestmark = pytest.mark.integration


async def _tenant_of(pg_session, email: str) -> Tenant:
    user = (await pg_session.exec(select(User).where(User.email == email))).one()
    membership = (
        await pg_session.exec(select(TenantMembership).where(TenantMembership.user_id == user.id))
    ).one()
    return (await pg_session.exec(select(Tenant).where(Tenant.id == membership.tenant_id))).one()


async def test_status_is_false_before_onboarding(pg_client) -> None:
    await sign_up_and_in(pg_client)

    response = await pg_client.get("/api/onboarding/status")

    assert response.status_code == 200
    assert response.json() == {"has_workspace": False}


async def test_onboarding_creates_the_workspace(pg_client, pg_session) -> None:
    email = await sign_up_and_in(pg_client)

    response = await pg_client.post("/api/onboarding", json=onboarding_payload())

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["property"]["name"] == "Villa Senja Ubud"
    assert body["property"]["property_type"] == "villa_portfolio"
    assert body["property"]["city"] == "Ubud"
    assert body["plan"] == {"code": "free", "name": "Free"}
    assert body["usage"] == {"payment_links_used": 0, "payment_links_limit": 30}
    assert body["is_owner"] is True

    tenant = await _tenant_of(pg_session, email)
    assert tenant.status == "active"
    assert tenant.code.startswith("villa-senja-ubud")

    async def count(model, column) -> int:
        return len((await pg_session.exec(select(model).where(column == tenant.id))).all())

    assert await count(TenantDatabase, TenantDatabase.tenant_id) == 1
    assert await count(TenantSubscription, TenantSubscription.tenant_id) == 1
    assert await count(TenantEntitlement, TenantEntitlement.tenant_id) == 3
    assert await count(TenantProfile, TenantProfile.tenant_id) == 1
    assert await count(LegalEntity, LegalEntity.tenant_id) == 1
    assert await count(Property, Property.tenant_id) == 1
    assert await count(StaffMember, StaffMember.tenant_id) == 1
    assert await count(StaffRole, StaffRole.tenant_id) == 1
    assert await count(StaffRoleAssignment, StaffRoleAssignment.tenant_id) == 1

    membership = (
        await pg_session.exec(
            select(TenantMembership).where(TenantMembership.tenant_id == tenant.id)
        )
    ).one()
    assert membership.is_tenant_owner is True
    assert membership.staff_member_id is not None
    assert membership.last_property_id is not None


async def test_status_is_true_after_onboarding(pg_client) -> None:
    await sign_up_and_in(pg_client)
    await pg_client.post("/api/onboarding", json=onboarding_payload())

    response = await pg_client.get("/api/onboarding/status")

    assert response.json() == {"has_workspace": True}


async def test_second_onboarding_is_rejected(pg_client) -> None:
    await sign_up_and_in(pg_client)
    await pg_client.post("/api/onboarding", json=onboarding_payload())

    response = await pg_client.post("/api/onboarding", json=onboarding_payload())

    assert response.status_code == 409
    assert response.json()["detail"] == "This account already has a workspace"


@pytest.mark.parametrize(
    "overrides",
    [
        {"property_name": "   "},
        {"property_name": "x"},
        {"property_name": "n" * 121},
        {"property_type": "castle"},
        {"city": ""},
        {"city": "c" * 81},
    ],
)
async def test_invalid_input_is_rejected(pg_client, overrides) -> None:
    await sign_up_and_in(pg_client)

    response = await pg_client.post("/api/onboarding", json=onboarding_payload(**overrides))

    assert response.status_code == 422


async def test_unknown_fields_are_rejected(pg_client) -> None:
    await sign_up_and_in(pg_client)

    response = await pg_client.post(
        "/api/onboarding", json=onboarding_payload(tenant_id="00000000-0000-0000-0000-000000000001")
    )

    assert response.status_code == 422


async def test_requires_sign_in(pg_client) -> None:
    assert (await pg_client.get("/api/onboarding/status")).status_code == 401
    assert (await pg_client.post("/api/onboarding", json=onboarding_payload())).status_code == 401


async def test_same_property_name_gets_distinct_tenant_codes(
    pg_client, other_client, pg_session
) -> None:
    email_a = await sign_up_and_in(pg_client)
    email_b = await sign_up_and_in(other_client)
    payload = onboarding_payload(property_name="Guesthouse Melati")

    first = await pg_client.post("/api/onboarding", json=payload)
    second = await other_client.post("/api/onboarding", json=payload)

    assert first.status_code == 201
    assert second.status_code == 201
    code_a = (await _tenant_of(pg_session, email_a)).code
    code_b = (await _tenant_of(pg_session, email_b)).code
    assert code_a != code_b


async def test_name_without_latin_letters_still_gets_a_valid_code(pg_client, pg_session) -> None:
    email = await sign_up_and_in(pg_client)

    response = await pg_client.post(
        "/api/onboarding", json=onboarding_payload(property_name="民宿 ★")
    )

    assert response.status_code == 201
    assert (await _tenant_of(pg_session, email)).code.startswith("property")


async def test_failure_midway_leaves_nothing_behind(pg_client, pg_session, monkeypatch) -> None:
    email = await sign_up_and_in(pg_client)

    async def boom(*args, **kwargs):
        raise RuntimeError("simulated failure after control-plane rows")

    monkeypatch.setattr(onboarding_service, "_create_tenant_data", boom)

    with pytest.raises(RuntimeError):
        await pg_client.post("/api/onboarding", json=onboarding_payload())

    user = (await pg_session.exec(select(User).where(User.email == email))).one()
    memberships = (
        await pg_session.exec(select(TenantMembership).where(TenantMembership.user_id == user.id))
    ).all()
    assert memberships == []
    status = await pg_client.get("/api/onboarding/status")
    assert status.json() == {"has_workspace": False}


async def test_owner_of_a_suspended_tenant_cannot_start_a_fresh_workspace(
    pg_client, pg_session
) -> None:
    email = await sign_up_and_in(pg_client)
    await pg_client.post("/api/onboarding", json=onboarding_payload())
    tenant = await _tenant_of(pg_session, email)
    tenant.status = "suspended"
    pg_session.add(tenant)
    await pg_session.commit()

    assert (await pg_client.get("/api/workspace")).status_code == 403
    again = await pg_client.post("/api/onboarding", json=onboarding_payload())

    assert again.status_code == 409


async def test_missing_free_plan_is_reported_as_unavailable(pg_client, monkeypatch) -> None:
    await sign_up_and_in(pg_client)
    monkeypatch.setattr(onboarding_service, "FREE_PLAN_CODE", "no-such-plan")

    response = await pg_client.post("/api/onboarding", json=onboarding_payload())

    assert response.status_code == 503
    assert "temporarily unavailable" in response.json()["detail"]
    assert (await pg_client.get("/api/onboarding/status")).json() == {"has_workspace": False}
