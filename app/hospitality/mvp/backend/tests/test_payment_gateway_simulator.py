"""Gateway interface and the simulated gateway."""

import datetime as dt
from decimal import Decimal

import pytest

from app.payments.gateway import (
    VA_BANKS,
    ChargeRequest,
    GatewayError,
    UnknownGatewayError,
    get_gateway,
)
from app.payments.simulator import SIMULATOR_GATEWAY, SimulatedGateway


def _request(method: str, bank: str | None = None, reference: str = "pay-1") -> ChargeRequest:
    return ChargeRequest(
        reference=reference,
        amount=Decimal("850000"),
        currency="IDR",
        method=method,
        bank=bank,
        description="DP Villa",
        expires_at=dt.datetime(2026, 11, 21, tzinfo=dt.UTC),
    )


async def test_qris_charge_has_a_payload_and_no_account_number() -> None:
    result = await SimulatedGateway().create_charge(_request("qris"))

    assert result.gateway_reference.startswith("simpay-")
    assert result.qris_payload is not None and "SIMULATED" in result.qris_payload
    assert "IDR850000" in result.qris_payload
    assert (result.va_bank, result.va_number) == (None, None)


@pytest.mark.parametrize("bank", VA_BANKS)
async def test_virtual_account_number_is_16_digits_for_every_bank(bank: str) -> None:
    result = await SimulatedGateway().create_charge(_request("virtual_account", bank))

    assert result.va_bank == bank
    assert result.va_number is not None
    assert len(result.va_number) == 16 and result.va_number.isdigit()
    assert result.qris_payload is None


async def test_same_payment_gets_the_same_instructions_and_others_differ() -> None:
    gateway = SimulatedGateway()

    first = await gateway.create_charge(_request("virtual_account", "BCA", "pay-1"))
    again = await gateway.create_charge(_request("virtual_account", "BCA", "pay-1"))
    other = await gateway.create_charge(_request("virtual_account", "BCA", "pay-2"))

    assert first == again
    assert first.va_number != other.va_number
    assert first.gateway_reference != other.gateway_reference


@pytest.mark.parametrize(
    ("method", "bank"),
    [("card", None), ("virtual_account", "Bank Fiktif"), ("virtual_account", None)],
)
async def test_unsupported_method_or_bank_is_refused(method: str, bank: str | None) -> None:
    with pytest.raises(GatewayError):
        await SimulatedGateway().create_charge(_request(method, bank))


def test_gateway_lookup() -> None:
    assert isinstance(get_gateway(SIMULATOR_GATEWAY), SimulatedGateway)
    with pytest.raises(UnknownGatewayError):
        get_gateway("barter")
