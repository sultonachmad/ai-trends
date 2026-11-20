"""Configurable business values (PRD scope item 7).

The numbers here are *defaults*. The effective value is read at request time from
data, so the product owner can change it without a code change:

* plan level     → ``tenantentitlement.limits`` (copied from ``planmodule.limits``)
* property level → ``property.settings["business"]``

Only keys declared below are accepted; anything else is rejected, so a typo in a
stored override fails loudly instead of being ignored.
"""

import datetime as dt
from decimal import Decimal
from typing import Any, Self

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

BUSINESS_KEY = "business"


class BusinessSettingsError(ValueError):
    """A stored or submitted business value is unknown or out of range."""


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
    first_reply_target_minutes: int = Field(
        default=15, gt=0, le=24 * 60, description="Target for the first reply to a new chat."
    )
    reply_hours_start: dt.time = Field(
        default=dt.time(8, 0), description="Start of the hours the reply target counts."
    )
    reply_hours_end: dt.time = Field(
        default=dt.time(21, 0), description="End of the hours the reply target counts."
    )

    @model_validator(mode="after")
    def _hours_in_order(self) -> Self:
        if self.reply_hours_end <= self.reply_hours_start:
            raise ValueError("reply_hours_end must be after reply_hours_start")
        return self


class PlanLimits(BaseModel):
    """Per-plan limits. ``None`` means unlimited."""

    model_config = ConfigDict(frozen=True, extra="ignore")

    payment_links_per_month: int | None = Field(default=30, ge=0)


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
