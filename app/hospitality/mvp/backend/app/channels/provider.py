"""What every sales channel must be able to do, and how one is picked.

`channelcatalog.code` names the channel. Today only the simulated agency exists; a
certified connection (through a connectivity partner or direct) registers here later.

The interface follows the usual shape of an agency connection: the property has an ID
on the channel, the channel lists that property's rooms and rates by its own IDs, and
our rooms and rates are matched to those. Sending availability and prices, and
receiving bookings, are added to this interface in the next milestones.
"""

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from sqlmodel.ext.asyncio.session import AsyncSession


@dataclass(frozen=True)
class ChannelRate:
    id: str
    name: str


@dataclass(frozen=True)
class ChannelRoom:
    """A room as the channel lists it."""

    id: str
    name: str
    max_guests: int
    rates: tuple[ChannelRate, ...]


@dataclass(frozen=True)
class ChannelProperty:
    """The property as the channel knows it."""

    property_id: str
    name: str
    rooms: tuple[ChannelRoom, ...]


class ChannelError(Exception):
    """A channel could not do what was asked."""


class ChannelUnavailableError(ChannelError):
    """The channel did not answer, or answered with a fault. Worth trying again."""


class UnknownChannelPropertyError(ChannelError):
    """The channel has no property with that ID (or will not show it to us)."""


class UnknownChannelError(LookupError):
    """No channel is registered under that code."""


@dataclass(frozen=True)
class ChannelCall:
    """Who is calling. A real channel uses `tenant_id` to pick credentials.

    `session` is there for the simulated agency only, whose "extranet" lives in our own
    database; a real channel never touches it. It is handed over with no transaction
    open and no lock held.
    """

    tenant_id: UUID
    session: AsyncSession


@dataclass(frozen=True)
class AriDay:
    """One day of one room as it is sold on a channel: the unit of every push.

    `prices` maps the channel's own rate ids to the whole-rupiah price a guest pays
    there (our price with the connection's adjustment applied). Availability is what
    the channel may sell: our units left, minus any units held back for direct sale,
    never below zero — and zero on a date closed for sale.
    """

    date: str  # ISO date
    available: int
    closed: bool
    min_stay: int | None
    prices: dict[str, int]


class ChannelProvider(Protocol):
    async def fetch_property(self, call: ChannelCall, property_id: str) -> ChannelProperty:
        """The property and its rooms and rates on the channel.

        Raises `UnknownChannelPropertyError` or `ChannelUnavailableError`.
        """
        ...

    async def push_ari(
        self, call: ChannelCall, property_id: str, days: dict[str, list[AriDay]]
    ) -> None:
        """Send availability, prices and restrictions for the given rooms.

        `days` maps the channel's room id to the days that changed. The channel
        acknowledges by not raising; `ChannelUnavailableError` means: try again later.
        """
        ...

    async def fetch_current_ari(
        self, call: ChannelCall, property_id: str, room_ids: list[str], dates: list[str]
    ) -> dict[str, list[AriDay]]:
        """What the channel currently holds for those rooms and dates (drift check).

        Rooms or dates the channel has never been told about come back with an empty
        day list or are absent — that is itself drift.
        """
        ...


_PROVIDERS: dict[str, ChannelProvider] = {}


def register_channel(code: str, provider: ChannelProvider) -> None:
    _PROVIDERS[code] = provider


def get_channel(code: str) -> ChannelProvider:
    try:
        return _PROVIDERS[code]
    except KeyError:
        raise UnknownChannelError(f"No channel named {code!r} can be connected") from None


def is_connectable(code: str) -> bool:
    return code in _PROVIDERS
