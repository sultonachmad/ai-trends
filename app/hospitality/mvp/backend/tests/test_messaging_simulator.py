"""Provider interface and the simulated WhatsApp sender."""

import pytest

from app.messaging.provider import SendResult, UnknownProviderError, get_provider
from app.messaging.simulator import SIMULATOR_PROVIDER, SimulatedWhatsAppProvider


async def test_simulator_accepts_a_message_and_returns_a_provider_id() -> None:
    provider = SimulatedWhatsAppProvider()

    first = await provider.send_text(sender="sim", recipient="+6281234567890", body="Halo")
    second = await provider.send_text(sender="sim", recipient="+6281234567890", body="Halo")

    assert isinstance(first, SendResult)
    assert first.accepted is True
    assert first.error is None
    assert first.provider_message_id.startswith("sim-")
    assert first.provider_message_id != second.provider_message_id


def test_provider_lookup() -> None:
    assert isinstance(get_provider(SIMULATOR_PROVIDER), SimulatedWhatsAppProvider)


def test_unknown_provider_is_a_clear_error() -> None:
    with pytest.raises(UnknownProviderError) as error:
        get_provider("carrier-pigeon")

    assert "carrier-pigeon" in str(error.value)
