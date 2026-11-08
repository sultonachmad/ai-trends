"""SurveyResponse entity — table ``surveyresponse``.

Tenant database, L. CRM, messaging & reputation.

Reputation, surveys, complaints.

Mirrors .ttest/contexts/schema-tenant.sql; the Alembic migration creates the table.
"""

import datetime as dt
from typing import Any, Literal
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    ForeignKeyConstraint,
    SmallInteger,
    Text,
    UniqueConstraint,
    Uuid,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel

from app.crud.base_model import MIGRATION_ONLY, TenantRecord, utc_datetime_field

SurveyResponseStage = Literal[
    "in_stay",
    "post_stay",
]


class SurveyResponse(TenantRecord, table=True):
    """Reputation, surveys, complaints."""

    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="surveyresponse_tenant_id_id_key"),
        ForeignKeyConstraint(
            ["tenant_id", "property_id"],
            ["property.tenant_id", "property.id"],
            name="surveyresponse_tenant_id_property_id_fkey",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "reservation_id"],
            ["reservation.tenant_id", "reservation.id"],
            name="surveyresponse_tenant_id_reservation_id_fkey",
            ondelete="SET NULL (reservation_id)",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "guest_id"],
            ["guest.tenant_id", "guest.id"],
            name="surveyresponse_tenant_id_guest_id_fkey",
            ondelete="SET NULL (guest_id)",
        ),
        CheckConstraint("stage IN ('in_stay', 'post_stay')", name="surveyresponse_stage_check"),
        CheckConstraint("((nps >= 0) AND (nps <= 10))", name="surveyresponse_nps_check"),
        CheckConstraint("((csat >= 1) AND (csat <= 5))", name="surveyresponse_csat_check"),
        MIGRATION_ONLY,
    )

    property_id: UUID = Field(sa_type=Uuid)
    reservation_id: UUID | None = Field(default=None, sa_type=Uuid)
    guest_id: UUID | None = Field(default=None, sa_type=Uuid)
    survey_code: str = Field(sa_type=Text)
    stage: str = Field(
        default="post_stay",
        sa_type=Text,
        sa_column_kwargs={"server_default": text("'post_stay'::text")},
    )
    nps: int | None = Field(default=None, sa_type=SmallInteger)
    csat: int | None = Field(default=None, sa_type=SmallInteger)
    answers: dict[str, Any] = Field(
        default_factory=dict,
        sa_type=JSONB,
        sa_column_kwargs={"server_default": text("'{}'::jsonb")},
    )
    submitted_at: dt.datetime = utc_datetime_field(
        nullable=False, default_now=True, server_default_now=True
    )  # type: ignore[assignment]


class SurveyResponseCreate(SQLModel):
    """Fields accepted when creating a SurveyResponse."""

    property_id: UUID
    reservation_id: UUID | None = None
    guest_id: UUID | None = None
    survey_code: str
    stage: SurveyResponseStage = "post_stay"
    nps: int | None = Field(default=None, ge=0, le=10)
    csat: int | None = Field(default=None, ge=1, le=5)
    answers: dict[str, Any] = Field(default_factory=dict)
    submitted_at: dt.datetime = Field(default_factory=lambda: dt.datetime.now(dt.UTC))


class SurveyResponseUpdate(SQLModel):
    """Fields accepted when patching a SurveyResponse (all optional)."""

    property_id: UUID | None = None
    reservation_id: UUID | None = None
    guest_id: UUID | None = None
    survey_code: str | None = None
    stage: SurveyResponseStage | None = None
    nps: int | None = Field(default=None, ge=0, le=10)
    csat: int | None = Field(default=None, ge=1, le=5)
    answers: dict[str, Any] | None = None
    submitted_at: dt.datetime | None = None


class SurveyResponseRead(SQLModel):
    """Fields returned when reading a SurveyResponse."""

    id: UUID
    tenant_id: UUID
    property_id: UUID
    reservation_id: UUID | None
    guest_id: UUID | None
    survey_code: str
    stage: str
    nps: int | None
    csat: int | None
    answers: dict[str, Any]
    submitted_at: dt.datetime
