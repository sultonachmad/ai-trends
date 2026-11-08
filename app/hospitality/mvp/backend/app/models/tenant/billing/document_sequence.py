"""DocumentSequence entity — table ``documentsequence``.

Tenant database, H. Folios, postings, invoices, end-of-day.

Gapless numbering per legal entity + series (lock row FOR UPDATE when issuing).

Mirrors .ttest/contexts/schema-tenant.sql; the Alembic migration creates the table.
"""

import datetime as dt
from typing import Literal
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    ForeignKeyConstraint,
    SmallInteger,
    Text,
    UniqueConstraint,
    Uuid,
    text,
)
from sqlmodel import Field, SQLModel

from app.crud.base_model import MIGRATION_ONLY, TenantRecord, utc_datetime_field

DocumentSequenceSeries = Literal[
    "invoice",
    "credit_note",
    "receipt",
    "deposit_invoice",
    "owner_statement",
    "work_order",
    "quote",
]


class DocumentSequence(TenantRecord, table=True):
    """Gapless numbering per legal entity + series (lock row FOR UPDATE when issuing)."""

    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="documentsequence_tenant_id_id_key"),
        UniqueConstraint(
            "tenant_id",
            "legal_entity_id",
            "series",
            "period_key",
            name="documentsequence_tenant_id_legal_entity_id_series_period_ke_key",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "legal_entity_id"],
            ["legalentity.tenant_id", "legalentity.id"],
            name="documentsequence_tenant_id_legal_entity_id_fkey",
        ),
        CheckConstraint(
            (
                "series IN ('invoice', 'credit_note', 'receipt', 'deposit_invoice', "
                "'owner_statement', 'work_order', 'quote')"
            ),
            name="documentsequence_series_check",
        ),
        CheckConstraint("(next_number > 0)", name="documentsequence_next_number_check"),
        MIGRATION_ONLY,
    )

    legal_entity_id: UUID = Field(sa_type=Uuid)
    series: str = Field(sa_type=Text)
    period_key: str = Field(
        default="",
        sa_type=Text,
        sa_column_kwargs={"server_default": text("''::text")},
        description="'' (never reset) or '2026' / '2026-11'",
    )
    prefix: str = Field(
        default="", sa_type=Text, sa_column_kwargs={"server_default": text("''::text")}
    )
    next_number: int = Field(
        default=1, sa_type=BigInteger, sa_column_kwargs={"server_default": text("1")}
    )
    padding: int = Field(
        default=6, sa_type=SmallInteger, sa_column_kwargs={"server_default": text("6")}
    )
    updated_at: dt.datetime = utc_datetime_field(
        nullable=False, default_now=True, onupdate_now=True, server_default_now=True
    )  # type: ignore[assignment]


class DocumentSequenceCreate(SQLModel):
    """Fields accepted when creating a DocumentSequence."""

    legal_entity_id: UUID
    series: DocumentSequenceSeries
    period_key: str = ""
    prefix: str = ""
    next_number: int = Field(default=1, gt=0)
    padding: int = 6


class DocumentSequenceUpdate(SQLModel):
    """Fields accepted when patching a DocumentSequence (all optional)."""

    legal_entity_id: UUID | None = None
    series: DocumentSequenceSeries | None = None
    period_key: str | None = None
    prefix: str | None = None
    next_number: int | None = Field(default=None, gt=0)
    padding: int | None = None


class DocumentSequenceRead(SQLModel):
    """Fields returned when reading a DocumentSequence."""

    id: UUID
    tenant_id: UUID
    legal_entity_id: UUID
    series: str
    period_key: str
    prefix: str
    next_number: int
    padding: int
    updated_at: dt.datetime
