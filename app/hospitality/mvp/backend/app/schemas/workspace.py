"""Shapes for onboarding and the workspace summary."""

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
