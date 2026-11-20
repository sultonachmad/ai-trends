"""Shapes for property settings that staff edit."""

from pydantic import BaseModel, ConfigDict, Field

# The allowed range is declared once, on `PropertySettings.direct_deposit_percent`.
MIN_DEPOSIT_PERCENT = 10
MAX_DEPOSIT_PERCENT = 100


class BookingTermsRead(BaseModel):
    deposit_percent: int
    can_edit: bool


class BookingTermsUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    deposit_percent: int = Field(ge=MIN_DEPOSIT_PERCENT, le=MAX_DEPOSIT_PERCENT)
