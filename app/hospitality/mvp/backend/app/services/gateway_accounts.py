"""The property's payment gateway account (simulated until a gateway is connected)."""

from sqlalchemy.exc import IntegrityError
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.tenant import PaymentGatewayAccount, Property
from app.payments.gateway import SUPPORTED_METHODS
from app.payments.simulator import SIMULATOR_GATEWAY


def new_gateway_account(prop: Property) -> PaymentGatewayAccount:
    return PaymentGatewayAccount(
        tenant_id=prop.tenant_id,
        property_id=prop.id,
        provider=SIMULATOR_GATEWAY,
        display_name="Simulated gateway",
        supported_methods=list(SUPPORTED_METHODS),
        settlement_currency=prop.currency,
        is_default=True,
        status="active",
    )


async def _find_gateway_account(
    session: AsyncSession, prop: Property
) -> PaymentGatewayAccount | None:
    return (
        await session.exec(
            select(PaymentGatewayAccount)
            .where(
                col(PaymentGatewayAccount.tenant_id) == prop.tenant_id,
                col(PaymentGatewayAccount.property_id) == prop.id,
                col(PaymentGatewayAccount.status) == "active",
            )
            .order_by(
                col(PaymentGatewayAccount.is_default).desc(),
                col(PaymentGatewayAccount.created_at),
            )
            .limit(1)
        )
    ).first()


async def get_or_create_gateway_account(
    session: AsyncSession, prop: Property
) -> PaymentGatewayAccount:
    """The property's active gateway account; made on first use for older workspaces.

    There is no unique rule to lean on here, so first use is serialised on the
    property row.
    """
    account = await _find_gateway_account(session, prop)
    if account is not None:
        return account
    await session.exec(
        select(Property.id)
        .where(col(Property.tenant_id) == prop.tenant_id, col(Property.id) == prop.id)
        .with_for_update()
    )
    account = await _find_gateway_account(session, prop)
    if account is not None:
        return account
    try:
        async with session.begin_nested():
            account = new_gateway_account(prop)
            session.add(account)
        return account
    except IntegrityError:  # pragma: no cover — defensive; the row lock prevents this
        existing = await _find_gateway_account(session, prop)
        if existing is None:
            raise
        return existing
