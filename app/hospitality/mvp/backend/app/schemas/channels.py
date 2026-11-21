"""Shapes for sales channels: the catalogue, a connection, its matching and history."""

import datetime as dt
from decimal import Decimal
from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

# The property's ID on the channel: what an agency prints in its extranet.
ChannelPropertyId = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True, min_length=1, max_length=64, pattern=r"^[A-Za-z0-9._-]+$"
    ),
]
ChannelCode = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=40, pattern=r"^[a-z_]+$")
]
ExternalId = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True, min_length=1, max_length=64, pattern=r"^[A-Za-z0-9._:-]+$"
    ),
]
Percent = Annotated[Decimal, Field(max_digits=5, decimal_places=2)]
MAX_SYNC_DAYS = 366  # one selling window is the most anyone can ask for at once

CatalogState = Literal["connectable", "coming_soon"]
ConnectionStatus = Literal["draft", "testing", "live", "paused", "error", "disconnected"]
CollectModel = Literal["property", "channel"]
MAX_MAPPINGS = 500
MIN_PRICE_ADJUSTMENT = Decimal("-50")
MAX_PRICE_ADJUSTMENT = Decimal("100")
MAX_COMMISSION = Decimal("50")


class ChannelUsage(BaseModel):
    used: int
    limit: int | None  # None = unlimited
    limit_reached: bool


class CatalogChannel(BaseModel):
    code: str
    name: str
    kind: str
    features: list[str]
    state: CatalogState
    connected: bool  # this property already has a connection to it


class ChannelsOverview(BaseModel):
    usage: ChannelUsage
    channels: list[CatalogChannel]


class ConnectionCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    channel_code: ChannelCode
    external_property_id: ChannelPropertyId


class ConnectionSettingsRequest(BaseModel):
    """Only the fields sent are changed."""

    model_config = ConfigDict(extra="forbid")

    commission_percent: Percent | None = Field(default=None, ge=0, le=MAX_COMMISSION)
    price_adjustment_percent: Percent | None = Field(
        default=None, ge=MIN_PRICE_ADJUSTMENT, le=MAX_PRICE_ADJUSTMENT
    )
    payment_collect: CollectModel | None = None


class MappingPair(BaseModel):
    """One of our room type + rate plan pairs, matched to a channel room + rate."""

    model_config = ConfigDict(extra="forbid")

    room_type_id: UUID
    rate_plan_id: UUID
    external_room_id: ExternalId
    external_rate_id: ExternalId


class MappingsRequest(BaseModel):
    """The whole matching of a connection; what is not listed is not sold there."""

    model_config = ConfigDict(extra="forbid")

    mappings: list[MappingPair] = Field(max_length=MAX_MAPPINGS)

    @model_validator(mode="after")
    def _each_side_once(self) -> Self:
        ours = [(m.room_type_id, m.rate_plan_id) for m in self.mappings]
        theirs = [(m.external_room_id, m.external_rate_id) for m in self.mappings]
        if len(set(ours)) != len(ours):
            raise ValueError("a room type and rate plan may be matched only once")
        if len(set(theirs)) != len(theirs):
            raise ValueError("a channel room and rate may be matched only once")
        return self


class ChannelRateRead(BaseModel):
    id: str
    name: str


class ChannelRoomRead(BaseModel):
    id: str
    name: str
    max_guests: int
    rates: list[ChannelRateRead]


class ChannelProductsRead(BaseModel):
    property_name: str
    rooms: list[ChannelRoomRead]


class MappingHealth(BaseModel):
    """What is left over or does not fit. Warnings, never blockers."""

    unmatched_pairs: int  # ours, sold but not on this channel
    unmatched_channel_rates: int  # theirs, with nothing of ours behind them
    smaller_capacity: list[MappingPair]  # the channel room fits fewer guests than ours
    switched_off: list[MappingPair]  # our room type or rate plan is no longer in use
    missing_on_channel: list[MappingPair]  # the channel no longer lists that room or rate


class SyncRequest(BaseModel):
    """Re-send a date range now; omitted = the next 60 days."""

    model_config = ConfigDict(extra="forbid")

    date_from: dt.date | None = None
    date_to: dt.date | None = None

    @model_validator(mode="after")
    def _ordered(self) -> Self:
        if self.date_from and self.date_to and self.date_to < self.date_from:
            raise ValueError("date_to must not be before date_from")
        if self.date_from and self.date_to:
            if (self.date_to - self.date_from).days + 1 > MAX_SYNC_DAYS:
                raise ValueError(f"a sync range can cover at most {MAX_SYNC_DAYS} days")
        return self


class ConnectionHealth(BaseModel):
    pending_updates: int
    oldest_pending_at: dt.datetime | None
    failing_since: dt.datetime | None
    next_push_at: dt.datetime | None
    at_risk: bool
    last_success_at: dt.datetime | None


class MessageLogEntry(BaseModel):
    message_type: str
    status: str
    attempts: int
    date_from: dt.date | None
    date_to: dt.date | None
    error: str | None
    next_attempt_at: dt.datetime | None
    sent_at: dt.datetime | None
    created_at: dt.datetime


class DriftEntry(BaseModel):
    room: str
    date: str
    kind: str  # missing_on_channel | differs
    channel: dict[str, object] | None = None
    ours: dict[str, object] | None = None


class HistoryEntry(BaseModel):
    event: str
    actor: str | None
    at: dt.datetime
    details: dict[str, object]


class ConnectionRead(BaseModel):
    id: UUID
    channel_code: str
    channel_name: str
    external_property_id: str
    channel_property_name: str | None
    status: ConnectionStatus
    problem: str | None  # why the last test failed, as a short code
    commission_percent: Decimal
    price_adjustment_percent: Decimal
    payment_collect: str
    mapped_pairs: int
    last_tested_at: dt.datetime | None
    created_at: dt.datetime


class ConnectionDetail(ConnectionRead):
    mappings: list[MappingPair]
    products: ChannelProductsRead | None  # as last fetched from the channel
    health: MappingHealth
    push_health: ConnectionHealth
    messages: list[MessageLogEntry]  # newest first, latest 30
    history: list[HistoryEntry]


class ConnectionDrift(BaseModel):
    differences: list[DriftEntry]
