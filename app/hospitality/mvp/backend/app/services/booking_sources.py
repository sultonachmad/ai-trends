"""Where a booking came from: the property's source ("channel") rows.

Staff pick one of a fixed set when entering a booking by hand. Each is a row in
`channel`, found or created on first use, so reports can later group direct bookings
and channel bookings the same way.
"""

from dataclasses import dataclass
from typing import Literal

from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.tenant import Channel
from app.tenancy.context import TenantContext

StaffSource = Literal["whatsapp", "walk_in", "phone", "instagram", "other"]


@dataclass(frozen=True)
class _Source:
    name: str
    kind: str


_STAFF_SOURCES: dict[str, _Source] = {
    "whatsapp": _Source("WhatsApp", "messaging"),
    "walk_in": _Source("Walk-in", "walk_in"),
    "phone": _Source("Phone", "direct_phone"),
    "instagram": _Source("Instagram", "messaging"),
    "other": _Source("Other", "other"),
}


async def direct_web_source(session: AsyncSession, context: TenantContext) -> Channel:
    """The tenant's "Booking page" source, created on first use (flushed, not committed)."""
    existing = (
        await session.exec(
            select(Channel).where(
                col(Channel.tenant_id) == context.tenant_id, col(Channel.code) == "direct_web"
            )
        )
    ).first()
    if existing is not None:
        return existing
    channel = Channel(
        tenant_id=context.tenant_id,
        code="direct_web",
        name="Booking page",
        kind="direct_web",
        is_direct=True,
    )
    session.add(channel)
    await session.flush()
    return channel


async def staff_source(session: AsyncSession, context: TenantContext, code: StaffSource) -> Channel:
    """The tenant's row for a direct source, created on first use (flushed, not committed).

    The caller holds the property's row lock, so two bookings cannot create it twice.
    """
    existing = (
        await session.exec(
            select(Channel).where(
                col(Channel.tenant_id) == context.tenant_id, col(Channel.code) == code
            )
        )
    ).first()
    if existing is not None:
        return existing
    source = _STAFF_SOURCES[code]
    channel = Channel(
        tenant_id=context.tenant_id, code=code, name=source.name, kind=source.kind, is_direct=True
    )
    session.add(channel)
    await session.flush()
    return channel
