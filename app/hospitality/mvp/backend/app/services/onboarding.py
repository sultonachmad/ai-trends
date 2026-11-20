"""Workspace provisioning: one sign-up becomes one tenant with one property.

This is platform work (database-design.md §1.5): it writes control-plane rows and
the first tenant rows before any tenant scope exists, so it runs on the plain,
elevated session — never on a tenant-scoped one. Everything happens in a single
transaction: the caller gets a complete workspace or nothing.
"""

import datetime as dt
import logging
import re
import secrets
import unicodedata

from sqlalchemy import text
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.auth.models import User
from app.models.control_plane import (
    DbCluster,
    Plan,
    PlanModule,
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
from app.schemas.workspace import OnboardingRequest
from app.services.gateway_accounts import new_gateway_account
from app.services.messaging_accounts import new_whatsapp_account
from app.tenancy.context import TenantContext

log = logging.getLogger(__name__)

FREE_PLAN_CODE = "free"  # seeded by migration 0004
LOCAL_CLUSTER_CODE = "local-pooled-01"  # seeded by migration 0004
OWNER_ROLE_CODE = "owner"
FIRST_PROPERTY_CODE = "MAIN"
_FALLBACK_SLUG = "property"
_MAX_SLUG_LENGTH = 48  # leaves room for a "-xxxxxx" suffix inside tenant.code's 63 chars
_CODE_ATTEMPTS = 5


class WorkspaceExistsError(Exception):
    """The account already has a workspace."""


class AccountNotFoundError(Exception):
    """The signed-in account no longer exists."""


class ProvisioningError(RuntimeError):
    """Required seed data is missing or a unique tenant code could not be found."""


def slugify(name: str) -> str:
    """URL-safe tenant code base: lowercase ASCII letters, digits and single dashes."""
    ascii_name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_name.lower()).strip("-")[:_MAX_SLUG_LENGTH].strip("-")
    return slug if len(slug) >= 2 else _FALLBACK_SLUG


async def _unique_tenant_code(session: AsyncSession, name: str) -> str:
    base = slugify(name)
    candidate = base
    for _ in range(_CODE_ATTEMPTS):
        taken = (await session.exec(select(Tenant.id).where(col(Tenant.code) == candidate))).first()
        if taken is None:
            return candidate
        candidate = f"{base}-{secrets.token_hex(3)}"
    raise ProvisioningError(f"could not find a free tenant code for {base!r}")


async def _create_control_plane(
    session: AsyncSession, user: User, request: OnboardingRequest
) -> Tenant:
    plan = (await session.exec(select(Plan).where(col(Plan.code) == FREE_PLAN_CODE))).first()
    cluster = (
        await session.exec(select(DbCluster).where(col(DbCluster.code) == LOCAL_CLUSTER_CODE))
    ).first()
    if plan is None or cluster is None:
        raise ProvisioningError("Free plan or local cluster missing — run `alembic upgrade head`")

    tenant = Tenant(
        code=await _unique_tenant_code(session, request.property_name),
        name=request.property_name,
        status="active",
    )
    session.add(tenant)
    await session.flush()

    database_name = (await session.execute(text("SELECT current_database()"))).scalar_one()
    schema_version = (
        await session.execute(text("SELECT version_num FROM alembic_version LIMIT 1"))
    ).scalar_one_or_none()
    session.add(
        TenantDatabase(
            tenant_id=tenant.id,
            cluster_id=cluster.id,
            isolation_mode="pooled_rls",
            database_name=database_name,
            schema_version=schema_version,
            status="ready",
        )
    )
    session.add(
        TenantSubscription(
            tenant_id=tenant.id, plan_id=plan.id, status="active", started_on=dt.date.today()
        )
    )
    plan_modules = (
        await session.exec(select(PlanModule).where(col(PlanModule.plan_id) == plan.id))
    ).all()
    session.add_all(
        TenantEntitlement(
            tenant_id=tenant.id,
            module_code=module.module_code,
            source="plan",
            limits=dict(module.limits),
        )
        for module in plan_modules
    )
    await session.flush()
    return tenant


async def _create_tenant_data(
    session: AsyncSession, tenant: Tenant, user: User, request: OnboardingRequest
) -> tuple[Property, StaffMember]:
    enabled = (
        await session.exec(
            select(TenantEntitlement.module_code).where(
                col(TenantEntitlement.tenant_id) == tenant.id
            )
        )
    ).all()
    session.add(
        TenantProfile(
            id=tenant.id,
            tenant_id=tenant.id,
            code=tenant.code,
            name=tenant.name,
            enabled_modules=sorted(enabled),
        )
    )
    await session.flush()

    legal_entity = LegalEntity(tenant_id=tenant.id, name=request.property_name)
    owner_role = StaffRole(tenant_id=tenant.id, code=OWNER_ROLE_CODE, name="Owner", is_system=True)
    staff = StaffMember(
        tenant_id=tenant.id,
        user_id=user.id,
        display_name=user.email.split("@", 1)[0],
        email=user.email,
        department="management",
    )
    session.add_all([legal_entity, owner_role, staff])
    await session.flush()

    prop = Property(
        tenant_id=tenant.id,
        legal_entity_id=legal_entity.id,
        code=FIRST_PROPERTY_CODE,
        name=request.property_name,
        property_type=request.property_type,
        status="live",
        address={"city": request.city},
    )
    session.add(prop)
    session.add(
        StaffRoleAssignment(tenant_id=tenant.id, staff_member_id=staff.id, role_id=owner_role.id)
    )
    await session.flush()
    session.add(new_whatsapp_account(prop))
    session.add(new_gateway_account(prop))
    await session.flush()
    return prop, staff


async def create_workspace(
    session: AsyncSession, user_id: int, request: OnboardingRequest
) -> TenantContext:
    """Provision the caller's workspace. Commits on success; raises without side effects."""
    # Lock the account row so two simultaneous submissions cannot both pass the check.
    user = (
        await session.exec(select(User).where(col(User.id) == user_id).with_for_update())
    ).first()
    if user is None:
        raise AccountNotFoundError
    # Any membership counts — including one in a suspended or cancelled tenant, so a
    # closed workspace cannot be side-stepped by provisioning a fresh free one.
    existing = (
        await session.exec(
            select(TenantMembership.id).where(col(TenantMembership.user_id) == user_id).limit(1)
        )
    ).first()
    if existing is not None:
        raise WorkspaceExistsError

    tenant = await _create_control_plane(session, user, request)
    prop, staff = await _create_tenant_data(session, tenant, user, request)
    membership = TenantMembership(
        tenant_id=tenant.id,
        user_id=user_id,
        status="active",
        is_tenant_owner=True,
        staff_member_id=staff.id,
        last_property_id=prop.id,
        joined_at=dt.datetime.now(dt.UTC),
    )
    session.add(membership)
    # The owner who creates the workspace gets full feature access (RBAC manager).
    from app.services.workspace_access import grant_manager

    await grant_manager(session, user_id)
    await session.commit()
    log.info("Provisioned workspace tenant=%s for user_id=%s", tenant.code, user_id)
    return TenantContext(
        tenant_id=tenant.id,
        user_id=user_id,
        email=user.email,
        is_owner=True,
        staff_member_id=staff.id,
        last_property_id=prop.id,
    )
