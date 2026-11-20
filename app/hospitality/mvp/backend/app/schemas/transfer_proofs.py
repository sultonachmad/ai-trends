"""Shapes for transfer proofs ("bukti transfer") and the bank account setting."""

import datetime as dt
from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, StringConstraints

from app.schemas.inbox import GuestSummary
from app.tenancy.business_settings import BankAccountNumber, BankText

# One line of plain text: it is shown to the guest and may be sent in a chat message.
Reason = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True, min_length=3, max_length=200, pattern=r"^[^\x00-\x1f\x7f]+$"
    ),
]

ProofState = Literal["awaiting", "awaiting_second", "approved", "rejected"]
ProofFilter = Literal["awaiting", "approved", "rejected"]
PublicProofState = Literal["checking", "rejected"]


class RejectRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: Reason


class DuplicateOf(BaseModel):
    """An earlier proof that used the very same image."""

    id: UUID
    description: str | None
    created_at: dt.datetime


class ProofRead(BaseModel):
    id: UUID
    state: ProofState
    amount: Decimal | None
    description: str | None
    guest: GuestSummary | None
    payment_link_id: UUID | None
    conversation_id: UUID | None
    submitted_by_guest: bool
    uploaded_by_name: str | None
    created_at: dt.datetime
    needs_second_approval: bool
    first_approved_by_name: str | None
    reviewed_by_name: str | None
    reviewed_at: dt.datetime | None
    rejection_reason: str | None
    duplicate_of: DuplicateOf | None
    image_available: bool


class ProofPage(BaseModel):
    items: list[ProofRead]
    next_cursor: str | None


class PublicProof(BaseModel):
    """What the guest may know about the proof they uploaded. No ids."""

    state: PublicProofState
    reason: str | None


class ManualTransfer(BaseModel):
    """Where the guest sends a manual bank transfer."""

    bank_name: str
    account_number: str
    account_holder: str
    max_upload_mb: int


class BankAccountRead(BaseModel):
    bank_name: str | None
    account_number: str | None
    account_holder: str | None
    can_edit: bool


class BankAccountUpdate(BaseModel):
    """All three together, or all three empty to switch manual transfer off."""

    model_config = ConfigDict(extra="forbid")

    bank_name: BankText | None
    account_number: BankAccountNumber | None
    account_holder: BankText | None
