"""Shapes for onboarding and the workspace summary."""

from datetime import date, datetime
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, StringConstraints

from app.models.tenant.organisation.property import PropertyType
from app.tenancy.business_settings import PropertySettings

PropertyName = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=2, max_length=120)
]
CityName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)]


class OnboardingRequest(BaseModel):
    """What an operator fills in to create their workspace."""

    model_config = ConfigDict(extra="forbid")

    property_name: PropertyName
    property_type: PropertyType
    city: CityName


class OnboardingStatus(BaseModel):
    has_workspace: bool


class TenantSummary(BaseModel):
    id: UUID
    code: str
    name: str


class PropertySummary(BaseModel):
    id: UUID
    code: str
    name: str
    property_type: str
    city: str | None
    timezone: str
    currency: str


class PlanSummary(BaseModel):
    code: str
    name: str


class UsageSummary(BaseModel):
    payment_links_used: int
    payment_links_limit: int | None  # None = unlimited
    payment_links_resets_at: datetime  # start of next month, property time
    payment_links_resets_on: date  # that moment as the property's local calendar date
    payment_links_warning: bool  # close to the limit
    payment_links_limit_reached: bool


class StaffSummary(BaseModel):
    display_name: str
    email: str | None


class WorkspaceRead(BaseModel):
    """Everything the workspace home needs, in one response."""

    tenant: TenantSummary
    property: PropertySummary
    plan: PlanSummary
    usage: UsageSummary
    is_owner: bool
    staff: StaffSummary
    settings: PropertySettings
    unread_conversations: int = 0
    proofs_awaiting_review: int = 0
    simulator_enabled: bool = False
