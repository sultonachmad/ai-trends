"""Simulated WhatsApp sender — accepts every message and invents a provider id.

Used until a real provider is chosen (PRD: simulated first). Inbound messages are
simulated through POST /api/simulator/whatsapp/inbound (app/routers/simulator.py).
"""

import uuid

from app.messaging.provider import SendResult, register_provider

SIMULATOR_PROVIDER = "simulator"


class SimulatedWhatsAppProvider:
    async def send_text(self, *, sender: str, recipient: str, body: str) -> SendResult:
        return SendResult(accepted=True, provider_message_id=f"sim-{uuid.uuid4().hex}")

    async def send_template(
        self, *, sender: str, recipient: str, template: str, language: str, params: dict[str, str]
    ) -> SendResult:
        return SendResult(accepted=True, provider_message_id=f"sim-{uuid.uuid4().hex}")


register_provider(SIMULATOR_PROVIDER, SimulatedWhatsAppProvider())
