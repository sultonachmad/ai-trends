"""The property's WhatsApp sender account (simulated until a provider is connected)."""

from sqlalchemy.exc import IntegrityError
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.messaging.simulator import SIMULATOR_PROVIDER
from app.models.tenant import MessagingAccount, Property

WHATSAPP = "whatsapp"


def simulated_sender_identity(prop: Property) -> str:
    """Stand-in for the property's WhatsApp number while the provider is simulated."""
    return f"simulator:{prop.id}"


def new_whatsapp_account(prop: Property) -> MessagingAccount:
    return MessagingAccount(
        tenant_id=prop.tenant_id,
        property_id=prop.id,
        channel_kind=WHATSAPP,
        provider=SIMULATOR_PROVIDER,
        sender_identity=simulated_sender_identity(prop),
        status="active",
    )


async def _find_whatsapp_account(session: AsyncSession, prop: Property) -> MessagingAccount | None:
    account = (
        await session.exec(
            select(MessagingAccount)
            .where(
                col(MessagingAccount.tenant_id) == prop.tenant_id,
                col(MessagingAccount.property_id) == prop.id,
                col(MessagingAccount.channel_kind) == WHATSAPP,
            )
            .order_by(col(MessagingAccount.created_at))
            .limit(1)
        )
    ).first()
    return account


async def get_or_create_whatsapp_account(session: AsyncSession, prop: Property) -> MessagingAccount:
    """The property's WhatsApp account; made on first use for older workspaces."""
    account = await _find_whatsapp_account(session, prop)
    if account is not None:
        return account
    try:
        async with session.begin_nested():
            account = new_whatsapp_account(prop)
            session.add(account)
        return account
    except IntegrityError:
        # Another request created it between our look-up and insert.
        existing = await _find_whatsapp_account(session, prop)
        if existing is None:
            raise
        return existing
