"""Shapes for rate plans: terms and a base nightly price per room type."""

from decimal import Decimal
from typing import Literal, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.payment_links import Rupiah
from app.schemas.rooms import RoomName

MealPlan = Literal["room_only", "breakfast"]
MAX_FREE_CANCELLATION_DAYS = 365
MAX_PRICES = 200


class RoomPrice(BaseModel):
    """The normal nightly price of one room type on a rate plan (whole rupiah, all-in)."""

    model_config = ConfigDict(extra="forbid")

    room_type_id: UUID
    amount: Rupiah


def _no_room_twice(prices: list[RoomPrice] | None) -> None:
    if prices is not None and len({price.room_type_id for price in prices}) != len(prices):
        raise ValueError("a room type may be priced only once")


def _terms_agree(non_refundable: bool | None, free_cancellation_days: int | None) -> None:
    if non_refundable and free_cancellation_days is not None:
        raise ValueError("a non-refundable plan has no free cancellation days")


class RatePlanCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: RoomName
    meal_plan: MealPlan = "room_only"
    non_refundable: bool = False
    free_cancellation_days: int | None = Field(
        default=None,
        ge=0,
        le=MAX_FREE_CANCELLATION_DAYS,
        description="Free cancellation until this many days before arrival; "
        "omitted = the property's default.",
    )
    prices: list[RoomPrice] = Field(min_length=1, max_length=MAX_PRICES)

    @model_validator(mode="after")
    def _consistent(self) -> Self:
        _terms_agree(self.non_refundable, self.free_cancellation_days)
        _no_room_twice(self.prices)
        return self


class RatePlanUpdateRequest(BaseModel):
    """Only the fields sent are changed; `prices`, when sent, replaces the whole set."""

    model_config = ConfigDict(extra="forbid")

    name: RoomName | None = None
    meal_plan: MealPlan | None = None
    non_refundable: bool | None = None
    free_cancellation_days: int | None = Field(default=None, ge=0, le=MAX_FREE_CANCELLATION_DAYS)
    prices: list[RoomPrice] | None = Field(default=None, min_length=1, max_length=MAX_PRICES)
    is_active: bool | None = None

    @model_validator(mode="after")
    def _consistent(self) -> Self:
        _terms_agree(self.non_refundable, self.free_cancellation_days)
        _no_room_twice(self.prices)
        return self


class RoomPriceRead(BaseModel):
    room_type_id: UUID
    amount: Decimal


class RatePlanRead(BaseModel):
    id: UUID
    name: str
    meal_plan: str
    non_refundable: bool
    free_cancellation_days: int | None  # None when non-refundable
    is_active: bool
    prices: list[RoomPriceRead]
