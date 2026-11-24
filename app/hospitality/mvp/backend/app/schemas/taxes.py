"""Tax settings of a property: region, rates and price mode."""

import datetime as dt
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.bills import ChargeCategory
from app.services.tax_regions import PBJT_MAX, REGION_CODES, SERVICE_MAX

PriceMode = Literal["nett", "plus_plus"]
Percent = Decimal


class TaxRegionRead(BaseModel):
    code: str
    name: str
    province: str
    suggested_pbjt_pct: Decimal
    verified: bool = False  # nobody has checked this against official sources yet


class UpcomingRates(BaseModel):
    effective_from: dt.date
    pbjt_pct: Decimal
    service_pct: Decimal


class TaxSettingsRead(BaseModel):
    confirmed: bool  # the owner checked the rates; until then nothing is taxed
    can_edit: bool  # only the owner changes taxes
    region_code: str | None
    pbjt_pct: Decimal
    service_pct: Decimal
    pbjt_on_service: bool
    price_mode: PriceMode
    untaxed_categories: list[str]
    effective_from: dt.date | None
    upcoming: UpcomingRates | None
    regions: list[TaxRegionRead]


class TaxSettingsUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    region_code: str
    pbjt_pct: Percent = Field(ge=0, le=PBJT_MAX, decimal_places=2)
    service_pct: Percent = Field(ge=0, le=SERVICE_MAX, decimal_places=2)
    pbjt_on_service: bool = True
    price_mode: PriceMode
    untaxed_categories: list[ChargeCategory] = Field(default_factory=list, max_length=7)
    effective_from: dt.date
    confirmed: Literal[True]  # "I have checked these rates with my Bapenda"

    @field_validator("region_code")
    @classmethod
    def _known_region(cls, value: str) -> str:
        if value not in REGION_CODES:
            raise ValueError("choose a region from the list")
        return value
