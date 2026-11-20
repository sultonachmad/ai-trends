"""Configurable business values (PRD scope item 7).

The numbers here are *defaults*. The effective value is read at request time from
data, so the product owner can change it without a code change:

* plan level     → ``tenantentitlement.limits`` (copied from ``planmodule.limits``)
* property level → ``property.settings["business"]``

Only keys declared below are accepted; anything else is rejected, so a typo in a
stored override fails loudly instead of being ignored.
"""

import datetime as dt
from dataclasses import dataclass
from decimal import Decimal
from typing import Annotated, Any, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    ValidationError,
    model_validator,
)

BUSINESS_KEY = "business"


# One line of plain text, shown to guests on the pay page.
BankText = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True, min_length=2, max_length=80, pattern=r"^[^\x00-\x1f\x7f]+$"
    ),
]
BankAccountNumber = Annotated[
    str, StringConstraints(strip_whitespace=True, pattern=r"^[0-9]{5,30}$")
]


class BusinessSettingsError(ValueError):
    """A stored or submitted business value is unknown or out of range."""


# Ceiling of `proof_max_upload_mb`; the upload routes refuse larger bodies outright.
MAX_PROOF_UPLOAD_MB = 20


class PropertySettings(BaseModel):
    """Per-property business values."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    second_approver_threshold_idr: Decimal = Field(
        default=Decimal("5000000"),
        ge=0,
        max_digits=18,
        decimal_places=2,
        description="Transfer proofs above this amount need a second approver.",
    )
    proof_retention_days: int = Field(
        default=90, gt=0, le=3650, description="Days a screenshot is kept after the decision."
    )
    payment_link_expiry_hours: int = Field(
        default=24, gt=0, le=24 * 90, description="Default lifetime of a new payment link."
    )
    payment_link_min_amount_idr: int = Field(
        default=10_000, ge=1, description="Smallest amount a payment link may ask for."
    )
    payment_link_max_amount_idr: int = Field(
        default=500_000_000, ge=1, description="Largest amount a payment link may ask for."
    )
    first_reply_target_minutes: int = Field(
        default=15, gt=0, le=24 * 60, description="Target for the first reply to a new chat."
    )
    reply_hours_start: dt.time = Field(
        default=dt.time(8, 0), description="Start of the hours the reply target counts."
    )
    reply_hours_end: dt.time = Field(
        default=dt.time(21, 0), description="End of the hours the reply target counts."
    )
    proof_max_upload_mb: int = Field(
        default=5,
        ge=1,
        le=MAX_PROOF_UPLOAD_MB,
        description="Largest transfer-proof image accepted, in MB.",
    )
    proof_max_awaiting_per_link: int = Field(
        default=3, ge=1, le=10, description="Proofs one link may have waiting for review."
    )
    bank_name: BankText | None = Field(
        default=None, description="Bank guests transfer to (manual transfer)."
    )
    bank_account_number: BankAccountNumber | None = Field(
        default=None, description="Account number guests transfer to."
    )
    bank_account_holder: BankText | None = Field(default=None, description="Name on that account.")
    inbox_poll_seconds: int = Field(
        default=5, ge=2, le=120, description="How often the inbox list checks for new messages."
    )
    thread_poll_seconds: int = Field(
        default=3, ge=2, le=120, description="How often an open conversation checks for messages."
    )
    calendar_horizon_days: int = Field(
        default=365, ge=30, le=730, description="Days ahead (counting today) the calendar is open."
    )
    calendar_max_change_days: int = Field(
        default=365, ge=1, le=730, description="Most days one calendar change may cover."
    )
    room_rate_min_amount_idr: int = Field(
        default=10_000, ge=1, description="Lowest nightly price a room may be given."
    )
    room_rate_max_amount_idr: int = Field(
        default=500_000_000, ge=1, description="Highest nightly price a room may be given."
    )
    max_room_types: int = Field(
        default=30, ge=1, le=200, description="Active room types a property may have."
    )
    max_units_per_room_type: int = Field(
        default=100, ge=1, le=1000, description="Units one room type may have."
    )
    max_rate_plans: int = Field(
        default=10, ge=1, le=50, description="Active rate plans a property may have."
    )
    booking_backdate_days: int = Field(
        default=30, ge=0, le=365, description="How far back a booking's arrival may be entered."
    )
    booking_max_nights: int = Field(
        default=365, ge=1, le=365, description="Longest stay one booking may cover."
    )
    booking_max_units: int = Field(
        default=20, ge=1, le=100, description="Most units of a room type in one booking."
    )
    switched_off_allowance: int = Field(
        default=3,
        ge=1,
        le=20,
        description="Room types / rate plans kept in total, as a multiple of the active limit.",
    )
    free_cancellation_days: int = Field(
        default=7, ge=0, le=365, description="Default days before arrival for free cancellation."
    )
    direct_deposit_percent: int = Field(
        default=50, ge=10, le=100, description="Share of a direct booking paid when booking."
    )

    @model_validator(mode="after")
    def _hours_in_order(self) -> Self:
        if self.reply_hours_end <= self.reply_hours_start:
            raise ValueError("reply_hours_end must be after reply_hours_start")
        if self.payment_link_max_amount_idr < self.payment_link_min_amount_idr:
            raise ValueError("payment_link_max_amount_idr must not be below the minimum")
        if self.room_rate_max_amount_idr < self.room_rate_min_amount_idr:
            raise ValueError("room_rate_max_amount_idr must not be below the minimum")
        bank = (self.bank_name, self.bank_account_number, self.bank_account_holder)
        if any(bank) and not all(bank):
            raise ValueError("bank name, account number and account holder go together")
        return self


class PlanLimits(BaseModel):
    """Per-plan limits. ``None`` means unlimited."""

    model_config = ConfigDict(frozen=True, extra="ignore")

    payment_links_per_month: int | None = Field(default=30, ge=0)
    connected_channels: int | None = Field(
        default=1, ge=0, description="Channel connections a property may have at once."
    )
    usage_warning_percent: int = Field(
        default=80, ge=1, le=100, description="Share of a limit used before staff are warned."
    )


@dataclass(frozen=True)
class BankAccount:
    """Where guests send a manual transfer."""

    bank_name: str
    account_number: str
    account_holder: str


def bank_account(settings: PropertySettings) -> BankAccount | None:
    """The property's bank details, or None until all three are filled in."""
    if not (settings.bank_name and settings.bank_account_number and settings.bank_account_holder):
        return None
    return BankAccount(
        bank_name=settings.bank_name,
        account_number=settings.bank_account_number,
        account_holder=settings.bank_account_holder,
    )


def resolve_property_settings(raw_settings: dict[str, Any] | None) -> PropertySettings:
    """Effective property values: stored overrides on top of the defaults."""
    overrides = (raw_settings or {}).get(BUSINESS_KEY, {})
    try:
        return PropertySettings.model_validate(overrides)
    except ValidationError as exc:
        raise BusinessSettingsError(f"invalid property business settings: {exc}") from exc


def with_property_overrides(
    raw_settings: dict[str, Any] | None, changes: dict[str, Any]
) -> dict[str, Any]:
    """Return a new ``property.settings`` dict with `changes` merged in (validated)."""
    current = raw_settings or {}
    merged = {**current.get(BUSINESS_KEY, {}), **changes}
    updated = {**current, BUSINESS_KEY: merged}
    resolve_property_settings(updated)
    return updated


def resolve_plan_limits(raw_limits: dict[str, Any] | None) -> PlanLimits:
    """Effective plan limits from an entitlement's (or plan module's) ``limits``."""
    try:
        return PlanLimits.model_validate(raw_limits or {})
    except ValidationError as exc:
        raise BusinessSettingsError(f"invalid plan limits: {exc}") from exc
