"""The team list, changing a staff member's role, and removing them.

Runs on the unscoped session, like `staff_invites`; every query names the tenant.
The owner and the person acting cannot be changed or removed here.
"""

import logging
from uuid import UUID

from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.auth.models import User
from app.models.control_plane import TenantMembership
from app.models.tenant import Property, StaffMember, Task
from app.schemas.staff import MemberRead, TeamRead
from app.services import housekeeping_errors as errors
from app.services import tenant_audit
from app.services.staff_invites import (
    ACTIVE,
    DEPARTMENT,
    ENTITY_STAFF,
    REMOVED,
    _invite_read,
    _open_invites,
)
from app.services.workspace_access import (
    may_grant,
    remove_all_roles,
    set_staff_role,
    staff_roles_of,
)
from app.tenancy.context import TenantContext

log = logging.getLogger(__name__)

UNFINISHED = ("pending", "assigned", "in_progress", "paused", "failed_inspection")


async def read_team(session: AsyncSession, context: TenantContext) -> TeamRead:
    rows = (
        await session.exec(
            select(TenantMembership, StaffMember, User)
            .join(StaffMember, col(StaffMember.id) == col(TenantMembership.staff_member_id))
            .join(User, col(User.id) == col(TenantMembership.user_id))
            .where(
                col(TenantMembership.tenant_id) == context.tenant_id,
                col(StaffMember.tenant_id) == context.tenant_id,
                col(TenantMembership.status) == ACTIVE,
            )
            .order_by(col(TenantMembership.is_tenant_owner).desc(), col(StaffMember.display_name))
        )
    ).all()
    roles = await staff_roles_of(session, [user.id for _, _, user in rows])
    members = [
        MemberRead(
            staff_id=staff.id,
            name=staff.display_name,
            email=user.email,
            role=roles[user.id],
            is_owner=membership.is_tenant_owner,
            is_me=user.id == context.user_id,
            joined_at=membership.joined_at,
        )
        for membership, staff, user in rows
    ]
    invites = [_invite_read(i) for i in await _open_invites(session, context.tenant_id)]
    return TeamRead(members=members, invites=invites)


async def _member(
    session: AsyncSession, context: TenantContext, staff_id: UUID
) -> tuple[TenantMembership, StaffMember]:
    found = (
        await session.exec(
            select(TenantMembership, StaffMember)
            .join(StaffMember, col(StaffMember.id) == col(TenantMembership.staff_member_id))
            .where(
                col(TenantMembership.tenant_id) == context.tenant_id,
                col(StaffMember.tenant_id) == context.tenant_id,
                col(StaffMember.id) == staff_id,
                col(TenantMembership.status) == ACTIVE,
            )
            .with_for_update()
        )
    ).first()
    if found is None:
        raise errors.StaffNotFoundError
    membership, staff = found
    if membership.is_tenant_owner:
        raise errors.CannotChangeOwnerError
    if membership.user_id == context.user_id:
        raise errors.CannotChangeSelfError
    return membership, staff


async def change_role(
    session: AsyncSession, context: TenantContext, prop: Property, staff_id: UUID, role: str
) -> None:
    if not await may_grant(session, context.user_id, context.is_owner, role):
        raise errors.ManagerOnlyError
    membership, staff = await _member(session, context, staff_id)
    await set_staff_role(session, membership.user_id, role)
    staff.department = DEPARTMENT.get(role, "management")
    session.add(staff)
    await tenant_audit.record(
        session,
        context,
        "staff.role_changed",
        property_id=prop.id,
        entity_table=ENTITY_STAFF,
        entity_id=staff.id,
        payload={"role": role},
    )
    await session.commit()


async def remove(
    session: AsyncSession, context: TenantContext, prop: Property, staff_id: UUID
) -> None:
    """They can no longer sign in to this workspace. Their history stays. Commits."""
    membership, staff = await _member(session, context, staff_id)
    membership.status = REMOVED
    staff.status = "left"
    session.add_all([membership, staff])
    await remove_all_roles(session, membership.user_id)
    open_tasks = (
        await session.exec(
            select(Task)
            .where(
                col(Task.tenant_id) == context.tenant_id,
                col(Task.assigned_staff_id) == staff.id,
                col(Task.status).in_(UNFINISHED),
            )
            .with_for_update()
        )
    ).all()
    for task in open_tasks:  # their unfinished rooms go back to everyone
        task.assigned_staff_id = None
        task.status = {"assigned": "pending", "in_progress": "paused"}.get(task.status, task.status)
        session.add(task)
    await tenant_audit.record(
        session,
        context,
        "staff.removed",
        property_id=prop.id,
        entity_table=ENTITY_STAFF,
        entity_id=staff.id,
    )
    await session.commit()
    log.info("Staff removed tenant=%s staff=%s", context.tenant_id, staff.id)
