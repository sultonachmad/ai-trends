"""Simulated payment gateway — invents QRIS payloads and virtual account numbers.

Nothing here moves money. A "payment" happens when a tester presses the simulate
button on the pay page (POST /api/simulator/payments/{token}/pay), which feeds a
gateway event into the same handler a real gateway webhook will use.
"""

import hashlib

from app.payments.gateway import (
    QRIS,
    VIRTUAL_ACCOUNT,
    ChargeInstructions,
    ChargeRequest,
    GatewayError,
    register_gateway,
)

SIMULATOR_GATEWAY = "simulator"
_BANK_PREFIX = {
    "BCA": "39010",
    "Mandiri": "88908",
    "BNI": "88100",
    "BRI": "26215",
    "Permata": "85160",
}
_VA_LENGTH = 16


def _digits(seed: str, count: int) -> str:
    return str(int(hashlib.sha256(seed.encode()).hexdigest(), 16))[-count:].zfill(count)


class SimulatedGateway:
    async def create_charge(self, request: ChargeRequest) -> ChargeInstructions:
        reference = f"simpay-{hashlib.sha256(request.reference.encode()).hexdigest()[:24]}"
        if request.method == QRIS:
            payload = f"SIMULATED-QRIS.{reference}.{request.currency}{int(request.amount)}"
            return ChargeInstructions(gateway_reference=reference, qris_payload=payload)
        if request.method == VIRTUAL_ACCOUNT and request.bank in _BANK_PREFIX:
            prefix = _BANK_PREFIX[request.bank]
            number = prefix + _digits(request.reference, _VA_LENGTH - len(prefix))
            return ChargeInstructions(
                gateway_reference=reference, va_bank=request.bank, va_number=number
            )
        raise GatewayError(f"unsupported method {request.method!r} / bank {request.bank!r}")


register_gateway(SIMULATOR_GATEWAY, SimulatedGateway())
