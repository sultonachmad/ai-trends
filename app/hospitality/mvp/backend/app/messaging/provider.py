"""What every messaging provider must do, and how one is picked.

`messagingaccount.provider` names the provider. Today only the simulator exists;
a real WhatsApp Cloud API client registers here later without touching the inbox.
"""

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class SendResult:
    """Outcome of handing one message to a provider."""

    accepted: bool
    provider_message_id: str | None = None
    error: str | None = None


class MessagingProvider(Protocol):
    async def send_text(self, *, sender: str, recipient: str, body: str) -> SendResult:
        """Send a plain-text message from `sender` to `recipient`."""
        ...

    async def send_template(
        self, *, sender: str, recipient: str, template: str, language: str, params: dict[str, str]
    ) -> SendResult:
        """Send an approved template: the only way to message a guest outside the
        24-hour service window, such as the first confirmation of a direct booking."""
        ...


class UnknownProviderError(LookupError):
    """No provider is registered under that name."""


_PROVIDERS: dict[str, MessagingProvider] = {}


def register_provider(name: str, provider: MessagingProvider) -> None:
    _PROVIDERS[name] = provider


def get_provider(name: str) -> MessagingProvider:
    try:
        return _PROVIDERS[name]
    except KeyError:
        raise UnknownProviderError(f"No messaging provider named {name!r} is configured") from None
