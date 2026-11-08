"""AiSuggestion entity — table ``aisuggestion``.

Tenant database, S. AI assistant layer.

Every AI output shown to a human or acted on.

Mirrors .ttest/contexts/schema-tenant.sql; the Alembic migration creates the table.
"""

import datetime as dt
from decimal import Decimal
from typing import Any, Literal
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    ForeignKeyConstraint,
    Index,
    Text,
    UniqueConstraint,
    Uuid,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel

from app.crud.base_model import MIGRATION_ONLY, TenantRecord, utc_datetime_field

AiSuggestionStatus = Literal[
    "proposed",
    "accepted",
    "edited",
    "rejected",
    "auto_applied",
    "expired",
]


class AiSuggestion(TenantRecord, table=True):
    """Every AI output shown to a human or acted on."""

    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="aisuggestion_tenant_id_id_key"),
        ForeignKeyConstraint(
            ["tenant_id", "property_id"],
            ["property.tenant_id", "property.id"],
            name="aisuggestion_tenant_id_property_id_fkey",
            ondelete="CASCADE",
        ),
        CheckConstraint(
            ("status IN ('proposed', 'accepted', 'edited', 'rejected', 'auto_applied', 'expired')"),
            name="aisuggestion_status_check",
        ),
        Index("ix_aisuggestion_subject", "tenant_id", "subject_table", "subject_id"),
        MIGRATION_ONLY,
    )

    property_id: UUID | None = Field(default=None, sa_type=Uuid)
    feature: str = Field(sa_type=Text)
    subject_table: str = Field(
        sa_type=Text, description="'message','review','transferproof','guestdocument',…"
    )
    subject_id: UUID = Field(sa_type=Uuid)
    input_ref: dict[str, Any] = Field(
        default_factory=dict,
        sa_type=JSONB,
        sa_column_kwargs={"server_default": text("'{}'::jsonb")},
        description="ids of grounding data, not raw PII",
    )
    output: Any = Field(sa_type=JSONB, nullable=False)
    confidence: Decimal | None = Field(default=None, max_digits=4, decimal_places=3)
    status: str = Field(
        default="proposed",
        sa_type=Text,
        sa_column_kwargs={"server_default": text("'proposed'::text")},
    )
    decided_by: str | None = Field(default=None, sa_type=Text)
    decided_at: dt.datetime | None = utc_datetime_field(nullable=True)  # type: ignore[assignment]
    edit_distance: int | None = Field(default=None)
    feedback: str | None = Field(default=None, sa_type=Text)
    created_at: dt.datetime = utc_datetime_field(
        nullable=False, default_now=True, server_default_now=True
    )  # type: ignore[assignment]


class AiSuggestionCreate(SQLModel):
    """Fields accepted when creating a AiSuggestion."""

    property_id: UUID | None = None
    feature: str
    subject_table: str
    subject_id: UUID
    input_ref: dict[str, Any] = Field(default_factory=dict)
    output: Any
    confidence: Decimal | None = Field(default=None, max_digits=4, decimal_places=3)
    status: AiSuggestionStatus = "proposed"
    decided_by: str | None = None
    decided_at: dt.datetime | None = None
    edit_distance: int | None = None
    feedback: str | None = None


class AiSuggestionUpdate(SQLModel):
    """Fields accepted when patching a AiSuggestion (all optional)."""

    property_id: UUID | None = None
    feature: str | None = None
    subject_table: str | None = None
    subject_id: UUID | None = None
    input_ref: dict[str, Any] | None = None
    output: Any = None
    confidence: Decimal | None = Field(default=None, max_digits=4, decimal_places=3)
    status: AiSuggestionStatus | None = None
    decided_by: str | None = None
    decided_at: dt.datetime | None = None
    edit_distance: int | None = None
    feedback: str | None = None


class AiSuggestionRead(SQLModel):
    """Fields returned when reading a AiSuggestion."""

    id: UUID
    tenant_id: UUID
    property_id: UUID | None
    feature: str
    subject_table: str
    subject_id: UUID
    input_ref: dict[str, Any]
    output: Any
    confidence: Decimal | None
    status: str
    decided_by: str | None
    decided_at: dt.datetime | None
    edit_distance: int | None
    feedback: str | None
    created_at: dt.datetime
