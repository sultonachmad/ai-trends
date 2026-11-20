"""Tenant-scoped session: row-level security must actually apply (PRD scope item 6)."""

import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlmodel import select

from app.models.tenant import LegalEntity, TenantProfile
from app.tenancy.session import bind_tenant

pytestmark = pytest.mark.integration


async def _make_tenant(session, name: str) -> uuid.UUID:
    tenant_id = uuid.uuid4()
    session.add(
        TenantProfile(id=tenant_id, tenant_id=tenant_id, code=f"t-{tenant_id.hex[:8]}", name=name)
    )
    await session.flush()
    session.add(LegalEntity(tenant_id=tenant_id, name=f"{name} entity"))
    await session.commit()
    return tenant_id


async def test_scoped_session_sees_only_its_own_tenant(pg_session, pg_session_factory) -> None:
    tenant_a = await _make_tenant(pg_session, "A")
    tenant_b = await _make_tenant(pg_session, "B")

    async with pg_session_factory() as scoped:
        await bind_tenant(scoped, tenant_a)
        names = (await scoped.exec(select(LegalEntity.name))).all()
        other = (
            await scoped.exec(select(LegalEntity).where(LegalEntity.tenant_id == tenant_b))
        ).all()

    assert names == ["A entity"]
    assert other == []


async def test_scoped_session_cannot_update_another_tenant(pg_session, pg_session_factory) -> None:
    tenant_a = await _make_tenant(pg_session, "A")
    tenant_b = await _make_tenant(pg_session, "B")

    async with pg_session_factory() as scoped:
        await bind_tenant(scoped, tenant_a)
        result = await scoped.execute(
            text("UPDATE legalentity SET name = 'hacked' WHERE tenant_id = :t"), {"t": tenant_b}
        )
        await scoped.commit()

    assert result.rowcount == 0
    untouched = (
        await pg_session.exec(select(LegalEntity.name).where(LegalEntity.tenant_id == tenant_b))
    ).one()
    assert untouched == "B entity"


async def test_scoped_session_cannot_insert_for_another_tenant(
    pg_session, pg_session_factory
) -> None:
    tenant_a = await _make_tenant(pg_session, "A")
    tenant_b = await _make_tenant(pg_session, "B")

    async with pg_session_factory() as scoped:
        await bind_tenant(scoped, tenant_a)
        scoped.add(LegalEntity(tenant_id=tenant_b, name="smuggled"))
        with pytest.raises(DBAPIError):
            await scoped.commit()


async def test_isolation_survives_a_commit(pg_session, pg_session_factory) -> None:
    tenant_a = await _make_tenant(pg_session, "A")
    await _make_tenant(pg_session, "B")

    async with pg_session_factory() as scoped:
        await bind_tenant(scoped, tenant_a)
        scoped.add(LegalEntity(tenant_id=tenant_a, name="A second"))
        await scoped.commit()  # ends the transaction; SET LOCAL values are gone
        names = sorted((await scoped.exec(select(LegalEntity.name))).all())

    assert names == ["A entity", "A second"]


async def test_bind_applies_to_a_transaction_already_in_progress(
    pg_session, pg_session_factory
) -> None:
    tenant_a = await _make_tenant(pg_session, "A")
    await _make_tenant(pg_session, "B")

    async with pg_session_factory() as scoped:
        await scoped.execute(text("SELECT 1"))  # transaction begins unscoped
        await bind_tenant(scoped, tenant_a)
        names = (await scoped.exec(select(LegalEntity.name))).all()

    assert names == ["A entity"]


async def test_role_without_tenant_sees_nothing(pg_session, pg_session_factory) -> None:
    await _make_tenant(pg_session, "A")

    async with pg_session_factory() as session:
        await session.execute(text("SET LOCAL ROLE app_rw"))
        count = (await session.execute(text("SELECT count(*) FROM legalentity"))).scalar_one()

    assert count == 0


async def test_scoped_role_cannot_write_control_plane(pg_session, pg_session_factory) -> None:
    tenant_a = await _make_tenant(pg_session, "A")

    async with pg_session_factory() as scoped:
        await bind_tenant(scoped, tenant_a)
        with pytest.raises(DBAPIError):
            await scoped.execute(text("UPDATE plan SET name = 'x'"))


async def test_scoped_role_reads_only_its_own_control_plane_rows(
    pg_client, other_client, pg_session_factory
) -> None:
    from tests.pg.conftest import onboarding_payload, sign_up_and_in

    await sign_up_and_in(pg_client)
    await sign_up_and_in(other_client)
    mine = (await pg_client.post("/api/onboarding", json=onboarding_payload())).json()
    await other_client.post("/api/onboarding", json=onboarding_payload())

    async with pg_session_factory() as scoped:
        await bind_tenant(scoped, uuid.UUID(mine["tenant"]["id"]))
        tenants = (await scoped.execute(text("SELECT id FROM tenant"))).scalars().all()
        subs = (await scoped.execute(text("SELECT tenant_id FROM tenantsubscription"))).scalars()
        ents = (await scoped.execute(text("SELECT tenant_id FROM tenantentitlement"))).scalars()

        assert [str(t) for t in tenants] == [mine["tenant"]["id"]]
        assert {str(t) for t in subs.all()} == {mine["tenant"]["id"]}
        assert {str(t) for t in ents.all()} == {mine["tenant"]["id"]}


@pytest.mark.parametrize("table", ['"user"', "tenantmembership", "tenantinvitation", "dbcluster"])
async def test_scoped_role_cannot_read_accounts_or_other_platform_tables(
    pg_session, pg_session_factory, table
) -> None:
    tenant_a = await _make_tenant(pg_session, "A")

    async with pg_session_factory() as scoped:
        await bind_tenant(scoped, tenant_a)
        with pytest.raises(DBAPIError):
            await scoped.execute(text(f"SELECT 1 FROM {table} LIMIT 1"))  # noqa: S608
