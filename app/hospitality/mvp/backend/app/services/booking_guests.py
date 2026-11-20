"""Finding or creating the guest record for a chat or a booking.

A guest is recognised by their WhatsApp number. A booking entered without a number
gets a guest record of its own.
"""

from uuid import UUID

from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.tenant import Guest


async def find_guest_by_phone(session: AsyncSession, tenant_id: UUID, phone: str) -> Guest | None:
    """The earliest guest record with this WhatsApp number that has not been merged away."""
    return (
        await session.exec(
            select(Guest)
            .where(
                col(Guest.tenant_id) == tenant_id,
                col(Guest.whatsapp_phone) == phone,
                col(Guest.merged_into_guest_id).is_(None),
            )
            .order_by(col(Guest.created_at))
            .limit(1)
        )
    ).first()


async def find_or_create_guest(
    session: AsyncSession, tenant_id: UUID, name: str | None, phone: str | None
) -> Guest:
    """The guest with this number, or a new one. Flushed, not committed.

    An existing guest keeps the name already on record: a booking typed by staff must
    not rename the person the inbox knows.
    """
    if phone is not None:
        guest = await find_guest_by_phone(session, tenant_id, phone)
        if guest is not None:
            return guest
    guest = Guest(
        tenant_id=tenant_id,
        full_name=name or phone or "",
        phone=phone,
        whatsapp_phone=phone,
    )
    session.add(guest)
    await session.flush()
    return guest
