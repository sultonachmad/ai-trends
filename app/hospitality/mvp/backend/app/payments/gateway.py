"""What every payment gateway must do, and how one is picked.

`paymentgatewayaccount.provider` names the gateway. Today only the simulator exists;
a real gateway (Xendit first, per the PRD) registers here later.
"""

import datetime as dt
from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol

QRIS = "qris"
VIRTUAL_ACCOUNT = "virtual_account"
SUPPORTED_METHODS: tuple[str, ...] = (QRIS, VIRTUAL_ACCOUNT)
VA_BANKS: tuple[str, ...] = ("BCA", "Mandiri", "BNI", "BRI", "Permata")


@dataclass(frozen=True)
class ChargeRequest:
    reference: str  # our payment id; the gateway echoes it back
    amount: Decimal
    currency: str
    method: str
    bank: str | None
    description: str
    expires_at: dt.datetime


@dataclass(frozen=True)
class ChargeInstructions:
    """What the guest needs in order to pay."""

    gateway_reference: str
    qris_payload: str | None = None
    va_bank: str | None = None
    va_number: str | None = None


class GatewayError(Exception):
    """The gateway could not create the charge."""


class UnknownGatewayError(LookupError):
    """No gateway is registered under that name."""


class PaymentGateway(Protocol):
    async def create_charge(self, request: ChargeRequest) -> ChargeInstructions:
        """Ask the gateway for payment instructions. Raises `GatewayError` on refusal."""
        ...


_GATEWAYS: dict[str, PaymentGateway] = {}


def register_gateway(name: str, gateway: PaymentGateway) -> None:
    _GATEWAYS[name] = gateway


def get_gateway(name: str) -> PaymentGateway:
    try:
        return _GATEWAYS[name]
    except KeyError:
        raise UnknownGatewayError(f"No payment gateway named {name!r} is configured") from None
