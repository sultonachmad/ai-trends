"""RoutingInstruction entity — table ``routinginstruction``.

Tenant database, H. Folios, postings, invoices, end-of-day.

Charge routing (e.g. accommodation -> company folio, extras -> guest folio).

Mirrors .ttest/contexts/schema-tenant.sql; the Alembic migration creates the table.
"""

import datetime as dt
from uuid import UUID

from sqlalchemy import CheckConstraint, ForeignKeyConstraint, Text, UniqueConstraint, Uuid
from sqlmodel import Field, SQLModel

from app.crud.base_model import MIGRATION_ONLY, TenantEntity


class RoutingInstruction(TenantEntity, table=True):
    """Charge routing (e.g. accommodation -> company folio, extras -> guest folio)."""

    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="routinginstruction_tenant_id_id_key"),
        ForeignKeyConstraint(
            ["tenant_id", "reservation_id"],
            ["reservation.tenant_id", "reservation.id"],
            name="routinginstruction_tenant_id_reservation_id_fkey",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "target_folio_id"],
            ["folio.tenant_id", "folio.id"],
            name="routinginstruction_tenant_id_target_folio_id_fkey",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "transaction_code_id"],
            ["transactioncode.tenant_id", "transactioncode.id"],
            name="routinginstruction_tenant_id_transaction_code_id_fkey",
            ondelete="CASCADE",
        ),
        CheckConstraint(
            "((transaction_code_id IS NOT NULL) OR (department IS NOT NULL))",
            name="routinginstruction_check",
        ),
        MIGRATION_ONLY,
    )

    reservation_id: UUID = Field(sa_type=Uuid)
    target_folio_id: UUID = Field(sa_type=Uuid)
    transaction_code_id: UUID | None = Field(
        default=None, sa_type=Uuid, description="one of code / department must be set"
    )
    department: str | None = Field(default=None, sa_type=Text)
    valid_from: dt.date | None = Field(default=None)
    valid_to: dt.date | None = Field(default=None)


class RoutingInstructionCreate(SQLModel):
    """Fields accepted when creating a RoutingInstruction."""

    reservation_id: UUID
    target_folio_id: UUID
    transaction_code_id: UUID | None = None
    department: str | None = None
    valid_from: dt.date | None = None
    valid_to: dt.date | None = None


class RoutingInstructionUpdate(SQLModel):
    """Fields accepted when patching a RoutingInstruction (all optional)."""

    reservation_id: UUID | None = None
    target_folio_id: UUID | None = None
    transaction_code_id: UUID | None = None
    department: str | None = None
    valid_from: dt.date | None = None
    valid_to: dt.date | None = None


class RoutingInstructionRead(SQLModel):
    """Fields returned when reading a RoutingInstruction."""

    id: UUID
    tenant_id: UUID
    reservation_id: UUID
    target_folio_id: UUID
    transaction_code_id: UUID | None
    department: str | None
    valid_from: dt.date | None
    valid_to: dt.date | None
    created_at: dt.datetime
    updated_at: dt.datetime
    created_by: str | None
    updated_by: str | None
