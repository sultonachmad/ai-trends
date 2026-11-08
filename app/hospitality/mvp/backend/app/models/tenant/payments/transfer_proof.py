"""TransferProof entity — table ``transferproof``.

Tenant database, I. Payments.

Guest-submitted "bukti transfer" screenshot, AI-extracted and matched.

Mirrors .ttest/contexts/schema-tenant.sql; the Alembic migration creates the table.
"""

import datetime as dt
from decimal import Decimal
from typing import Any, Literal
from uuid import UUID

from sqlalchemy import CheckConstraint, ForeignKeyConstraint, Text, UniqueConstraint, Uuid, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel

from app.crud.base_model import MIGRATION_ONLY, TenantEntity, utc_datetime_field

TransferProofSubmittedVia = Literal[
    "whatsapp",
    "portal",
    "email",
    "staff_upload",
]
TransferProofMatchStatus = Literal[
    "pending",
    "matched",
    "amount_mismatch",
    "not_found",
    "suspected_tampered",
    "manually_confirmed",
    "rejected",
]


class TransferProof(TenantEntity, table=True):
    """Guest-submitted "bukti transfer" screenshot, AI-extracted and matched."""

    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="transferproof_tenant_id_id_key"),
        ForeignKeyConstraint(
            ["tenant_id", "property_id"],
            ["property.tenant_id", "property.id"],
            name="transferproof_tenant_id_property_id_fkey",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "reservation_id"],
            ["reservation.tenant_id", "reservation.id"],
            name="transferproof_tenant_id_reservation_id_fkey",
            ondelete="SET NULL (reservation_id)",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "payment_id"],
            ["payment.tenant_id", "payment.id"],
            name="transferproof_tenant_id_payment_id_fkey",
            ondelete="SET NULL (payment_id)",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "document_id"],
            ["document.tenant_id", "document.id"],
            name="transferproof_tenant_id_document_id_fkey",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "bank_statement_line_id"],
            ["bankstatementline.tenant_id", "bankstatementline.id"],
            name="transferproof_tenant_id_bank_statement_line_id_fkey",
            ondelete="SET NULL (bank_statement_line_id)",
        ),
        CheckConstraint(
            "submitted_via IN ('whatsapp', 'portal', 'email', 'staff_upload')",
            name="transferproof_submitted_via_check",
        ),
        CheckConstraint(
            (
                "match_status IN ('pending', 'matched', 'amount_mismatch', 'not_found', "
                "'suspected_tampered', 'manually_confirmed', 'rejected')"
            ),
            name="transferproof_match_status_check",
        ),
        MIGRATION_ONLY,
    )

    property_id: UUID = Field(sa_type=Uuid)
    reservation_id: UUID | None = Field(default=None, sa_type=Uuid)
    payment_id: UUID | None = Field(default=None, sa_type=Uuid)
    document_id: UUID = Field(sa_type=Uuid)
    submitted_via: str = Field(sa_type=Text)
    extracted: dict[str, Any] = Field(
        default_factory=dict,
        sa_type=JSONB,
        sa_column_kwargs={"server_default": text("'{}'::jsonb")},
        description='{"bank":"BCA","amount":1500000,"date":"…","ref":"…","sender":"…"}',
    )
    extraction_confidence: Decimal | None = Field(default=None, max_digits=4, decimal_places=3)
    match_status: str = Field(
        default="pending",
        sa_type=Text,
        sa_column_kwargs={"server_default": text("'pending'::text")},
    )
    bank_statement_line_id: UUID | None = Field(default=None, sa_type=Uuid)
    reviewed_by: str | None = Field(default=None, sa_type=Text)
    reviewed_at: dt.datetime | None = utc_datetime_field(nullable=True)  # type: ignore[assignment]


class TransferProofCreate(SQLModel):
    """Fields accepted when creating a TransferProof."""

    property_id: UUID
    reservation_id: UUID | None = None
    payment_id: UUID | None = None
    document_id: UUID
    submitted_via: TransferProofSubmittedVia
    extracted: dict[str, Any] = Field(default_factory=dict)
    extraction_confidence: Decimal | None = Field(default=None, max_digits=4, decimal_places=3)
    match_status: TransferProofMatchStatus = "pending"
    bank_statement_line_id: UUID | None = None
    reviewed_by: str | None = None
    reviewed_at: dt.datetime | None = None


class TransferProofUpdate(SQLModel):
    """Fields accepted when patching a TransferProof (all optional)."""

    property_id: UUID | None = None
    reservation_id: UUID | None = None
    payment_id: UUID | None = None
    document_id: UUID | None = None
    submitted_via: TransferProofSubmittedVia | None = None
    extracted: dict[str, Any] | None = None
    extraction_confidence: Decimal | None = Field(default=None, max_digits=4, decimal_places=3)
    match_status: TransferProofMatchStatus | None = None
    bank_statement_line_id: UUID | None = None
    reviewed_by: str | None = None
    reviewed_at: dt.datetime | None = None


class TransferProofRead(SQLModel):
    """Fields returned when reading a TransferProof."""

    id: UUID
    tenant_id: UUID
    property_id: UUID
    reservation_id: UUID | None
    payment_id: UUID | None
    document_id: UUID
    submitted_via: str
    extracted: dict[str, Any]
    extraction_confidence: Decimal | None
    match_status: str
    bank_statement_line_id: UUID | None
    reviewed_by: str | None
    reviewed_at: dt.datetime | None
    created_at: dt.datetime
    updated_at: dt.datetime
    created_by: str | None
    updated_by: str | None
