"""Shapes for payment links: staff side and the public pay page."""

import datetime as dt
from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.schemas.inbox import GuestSummary

MAX_EXPIRY_HOURS = 24 * 90
# One line of plain text: it is written into the chat message next to the pay address,
# so line breaks and control characters (which could fake extra lines) are refused.
Description = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True, min_length=1, max_length=200, pattern=r"^[^\x00-\x1f\x7f]+$"
    ),
]
# Whole rupiah. The allowed range is a property setting, checked in the service.
Rupiah = Annotated[Decimal, Field(gt=0, max_digits=16, decimal_places=0)]

LinkState = Literal["pending", "paid", "expired", "cancelled"]
LinkFilter = Literal["all", "pending", "paid", "expired", "cancelled"]
NotSentReason = Literal["resolved", "window_closed", "send_failed"]
PaymentMethod = Literal["qris", "virtual_account"]
VaBank = Literal["BCA", "Mandiri", "BNI", "BRI", "Permata"]


class PaymentLinkCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    amount: Rupiah
    description: Description
    total_amount: Rupiah | None = Field(
        default=None, description="Set for a down payment (DP): the full amount it is part of."
    )
    expires_in_hours: int | None = Field(default=None, ge=1, le=MAX_EXPIRY_HOURS)
    conversation_id: UUID | None = None


class PaymentLinkRead(BaseModel):
    id: UUID
    state: LinkState
    amount: Decimal
    total_amount: Decimal | None
    currency: str
    description: str | None
    expires_at: dt.datetime
    paid_at: dt.datetime | None
    paid_via: str | None  # e.g. "QRIS", "Virtual account BCA"
    created_at: dt.datetime
    guest: GuestSummary | None
    conversation_id: UUID | None
    sent_to_chat: bool
    needs_refund_review: bool = Field(
        default=False,
        description="Money arrived for this link after it was paid, expired or cancelled.",
    )


class PaymentLinkCreated(BaseModel):
    """Answer to creating a link. `url` holds the secret token and is shown only here."""

    link: PaymentLinkRead
    url: str
    sent_to_chat: bool
    not_sent_reason: NotSentReason | None


class PaymentLinkPage(BaseModel):
    items: list[PaymentLinkRead]
    next_cursor: str | None


class StartPaymentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    method: PaymentMethod
    bank: VaBank | None = None


class SimulatePaymentRequest(BaseModel):
    """Which open attempt the simulated payment is for (development only)."""

    model_config = ConfigDict(extra="forbid")

    reference: Annotated[str, StringConstraints(min_length=1, max_length=100)] | None = None


class PaymentInstructions(BaseModel):
    """What the guest needs in order to pay with the chosen method."""

    reference: str
    method: str
    qris_payload: str | None
    va_bank: str | None
    va_number: str | None


class PublicPaymentLink(BaseModel):
    """Everything the pay page may show. Deliberately no ids and no guest details."""

    property_name: str
    description: str | None
    amount: Decimal
    total_amount: Decimal | None
    currency: str
    expires_at: dt.datetime
    state: LinkState
    paid_at: dt.datetime | None
    methods: list[str]
    banks: list[str]
    instructions: PaymentInstructions | None
    simulator_enabled: bool
