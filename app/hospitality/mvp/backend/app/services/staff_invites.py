"""The team: join links, joining, roles and removal.

Memberships and invitations are control-plane rows the tenant role (`app_rw`) cannot
touch, so, like onboarding, this module runs on the unscoped session. Every query
therefore names the tenant itself; tests check that one workspace never sees another's.

A join link is a random token shown once to the owner; only its SHA-256 is stored. It
works once, for `INVITE_DAYS`, and only for the invited email.
"""

import datetime as dt
import hashlib
import logging
import secrets
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlmodel import col, func, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.auth.models import User
from app.models.control_plane import Tenant, TenantInvitation, TenantMembership
from app.models.tenant import Property, StaffMember
from app.schemas.staff import (
    InviteCreated,
    InviteRead,
    InviteRequest,
    JoinPreview,
    JoinResult,
)
from app.services import housekeeping_errors as errors
from app.services import tenant_audit
from app.services.workspace_access import (
    FRONT_DESK_ROLE,
    HOUSEKEEPER_ROLE,
    may_grant,
    set_staff_role,
)
from app.tenancy.context import TenantContext

log = logging.getLogger(__name__)

INVITE_DAYS = 7
TOKEN_BYTES = 32
ACTIVE, REMOVED = "active", "removed"
DEPARTMENT = {HOUSEKEEPER_ROLE: "housekeeping", FRONT_DESK_ROLE: "front_office"}
ENTITY_INVITE, ENTITY_STAFF = "tenantinvitation", "staffmember"


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def email_hint(email: str) -> str:
    """`w***@example.com`: enough to recognise, not enough to collect."""
    local, _, domain = email.partition("@")
    return f"{local[:1]}***@{domain}"


def _now() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


def _invite_read(invite: TenantInvitation) -> InviteRead:
    return InviteRead(
        id=invite.id,
        name=invite.display_name,
        email=invite.email,
        role=invite.role_codes[0] if invite.role_codes else HOUSEKEEPER_ROLE,
        created_at=invite.created_at,
        expires_at=invite.expires_at,
    )


def _is_open(invite: TenantInvitation, now: dt.datetime) -> bool:
    return invite.accepted_at is None and invite.revoked_at is None and invite.expires_at > now


async def _open_invites(session: AsyncSession, tenant_id: UUID) -> list[TenantInvitation]:
    rows = await session.exec(
        select(TenantInvitation)
        .where(
            col(TenantInvitation.tenant_id) == tenant_id,
            col(TenantInvitation.accepted_at).is_(None),
            col(TenantInvitation.revoked_at).is_(None),
            col(TenantInvitation.expires_at) > _now(),
        )
        .order_by(col(TenantInvitation.created_at).desc())
    )
    return list(rows.all())


async def _member_emails(session: AsyncSession, tenant_id: UUID) -> set[str]:
    rows = await session.exec(
        select(User.email)
        .join(TenantMembership, col(TenantMembership.user_id) == col(User.id))
        .where(col(TenantMembership.tenant_id) == tenant_id, col(TenantMembership.status) == ACTIVE)
    )
    return {email.lower() for email in rows.all()}


async def _retire_expired(session: AsyncSession, tenant_id: UUID, email: str) -> None:
    """An expired, unused link no longer blocks a new one for the same email."""
    rows = await session.exec(
        select(TenantInvitation)
        .where(
            col(TenantInvitation.tenant_id) == tenant_id,
            func.lower(col(TenantInvitation.email)) == email.lower(),
            col(TenantInvitation.accepted_at).is_(None),
            col(TenantInvitation.revoked_at).is_(None),
            col(TenantInvitation.expires_at) <= _now(),
        )
        .with_for_update()
    )
    for expired in rows.all():
        expired.revoked_at = _now()
        session.add(expired)
    await session.flush()


async def invite(
    session: AsyncSession, context: TenantContext, prop: Property, request: InviteRequest
) -> InviteCreated:
    """A join link for `request.email`. Commits."""
    if not await may_grant(session, context.user_id, context.is_owner, request.role):
        raise errors.ManagerOnlyError
    taken = {i.email.lower() for i in await _open_invites(session, context.tenant_id)}
    if request.email in taken | await _member_emails(session, context.tenant_id):
        raise errors.AlreadyInvitedError
    await _retire_expired(session, context.tenant_id, request.email)
    token = secrets.token_urlsafe(TOKEN_BYTES)
    created = TenantInvitation(
        tenant_id=context.tenant_id,
        email=request.email,
        display_name=request.name,
        token_hash=token_hash(token),
        role_codes=[request.role],
        property_ids=[prop.id],
        invited_by_user_id=context.user_id,
        expires_at=_now() + dt.timedelta(days=INVITE_DAYS),
    )
    session.add(created)
    try:
        await session.flush()
    except IntegrityError:  # the database's own guard: one open link per email
        await session.rollback()
        raise errors.AlreadyInvitedError from None
    await tenant_audit.record(
        session,
        context,
        "staff.invited",
        property_id=prop.id,
        entity_table=ENTITY_INVITE,
        entity_id=created.id,
        payload={"name": request.name, "role": request.role},
    )
    await session.commit()
    await session.refresh(created)
    log.info(
        "Staff invited tenant=%s invite=%s role=%s", context.tenant_id, created.id, request.role
    )
    return InviteCreated(invite=_invite_read(created), token=token)


async def revoke(
    session: AsyncSession, context: TenantContext, prop: Property, invite_id: UUID
) -> None:
    found = (
        await session.exec(
            select(TenantInvitation)
            .where(
                col(TenantInvitation.tenant_id) == context.tenant_id,
                col(TenantInvitation.id) == invite_id,
            )
            .with_for_update()
        )
    ).first()
    if found is None:
        raise errors.InviteNotFoundError
    if found.accepted_at is not None:
        raise errors.InviteUsedError
    if found.revoked_at is None:
        found.revoked_at = _now()
        session.add(found)
        await tenant_audit.record(
            session,
            context,
            "staff.invite_revoked",
            property_id=prop.id,
            entity_table=ENTITY_INVITE,
            entity_id=found.id,
        )
    await session.commit()


def _state(invite: TenantInvitation, now: dt.datetime) -> str:
    """Used, cancelled before it ran out, expired, or open."""
    if invite.accepted_at is not None:
        return "used"
    if invite.revoked_at is not None and invite.revoked_at < invite.expires_at:
        return "revoked"
    return "expired" if invite.expires_at <= now else "open"


async def _by_token(session: AsyncSession, token: str, *, lock: bool) -> TenantInvitation:
    statement = select(TenantInvitation).where(
        col(TenantInvitation.token_hash) == token_hash(token)
    )
    found = (await session.exec(statement.with_for_update() if lock else statement)).first()
    if found is None:
        raise errors.InviteNotFoundError
    return found


async def preview(session: AsyncSession, token: str) -> JoinPreview:
    """What the join page shows before signing in. Reveals nothing without the token."""
    found = await _by_token(session, token, lock=False)
    tenant = (await session.exec(select(Tenant).where(col(Tenant.id) == found.tenant_id))).one()
    return JoinPreview(
        workspace=tenant.name,
        name=found.display_name,
        email_hint=email_hint(found.email),
        role=_invite_read(found).role,
        state=_state(found, _now()),
    )


_REFUSED_STATE = {
    "expired": errors.InviteExpiredError,
    "used": errors.InviteUsedError,
    "revoked": errors.InviteRevokedError,
}


async def _staff_profile(
    session: AsyncSession, found: TenantInvitation, user: User, role: str
) -> StaffMember:
    """The staff member for this user: the one from an earlier stay on the team, or new."""
    staff = (
        await session.exec(
            select(StaffMember)
            .where(
                col(StaffMember.tenant_id) == found.tenant_id,
                col(StaffMember.user_id) == user.id,
            )
            .with_for_update()
        )
    ).first()
    staff = staff or StaffMember(tenant_id=found.tenant_id, user_id=user.id, display_name="")
    staff.display_name = found.display_name or user.email.split("@", 1)[0]
    staff.email = user.email
    staff.department = DEPARTMENT.get(role, "management")
    staff.status = ACTIVE
    session.add(staff)
    await session.flush()
    return staff


async def _place(
    session: AsyncSession, found: TenantInvitation, user: User, staff: StaffMember
) -> TenantMembership:
    memberships = (
        await session.exec(
            select(TenantMembership)
            .where(col(TenantMembership.user_id) == user.id)
            .with_for_update()
        )
    ).all()
    same = next((m for m in memberships if m.tenant_id == found.tenant_id), None)
    if any(m.tenant_id != found.tenant_id for m in memberships) or (
        same is not None and same.status != REMOVED
    ):
        raise errors.AlreadyMemberError
    membership = same or TenantMembership(tenant_id=found.tenant_id, user_id=user.id)
    membership.status, membership.is_tenant_owner = ACTIVE, False
    membership.staff_member_id = staff.id
    membership.last_property_id = found.property_ids[0] if found.property_ids else None
    membership.joined_at = _now()
    session.add(membership)
    return membership


async def join(session: AsyncSession, user_id: int, token: str) -> JoinResult:
    """The signed-in user joins the team the link is for. Commits."""
    found = await _by_token(session, token, lock=True)
    refused = _REFUSED_STATE.get(_state(found, _now()))
    if refused is not None:
        raise refused
    user = (
        await session.exec(select(User).where(col(User.id) == user_id).with_for_update())
    ).first()
    if user is None or user.email.lower() != found.email.lower():
        raise errors.WrongEmailError
    role = _invite_read(found).role
    staff = await _staff_profile(session, found, user, role)
    membership = await _place(session, found, user, staff)
    found.accepted_at = _now()
    session.add(found)
    await set_staff_role(session, user.id, role)
    context = TenantContext(
        tenant_id=found.tenant_id,
        user_id=user.id,
        email=user.email,
        is_owner=False,
        staff_member_id=staff.id,
        last_property_id=membership.last_property_id,
    )
    await tenant_audit.record(
        session,
        context,
        "staff.joined",
        property_id=membership.last_property_id,
        entity_table=ENTITY_STAFF,
        entity_id=staff.id,
        payload={"invite": str(found.id), "role": role},
    )
    await session.commit()
    log.info("Staff joined tenant=%s staff=%s role=%s", found.tenant_id, staff.id, role)
    return JoinResult(role=role)
