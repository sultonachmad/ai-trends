"""MeterReading entity — table ``meterreading``.

Tenant database, O. Long stay, kos & leases.

Electricity / PLN token / water.

Mirrors .ttest/contexts/schema-tenant.sql; the Alembic migration creates the table.
"""

import datetime as dt
from decimal import Decimal
from uuid import UUID

from sqlalchemy import ForeignKeyConstraint, Text, UniqueConstraint, Uuid
from sqlmodel import Field, SQLModel

from app.crud.base_model import MIGRATION_ONLY, TenantRecord, utc_datetime_field


class MeterReading(TenantRecord, table=True):
    """Electricity / PLN token / water."""

    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="meterreading_tenant_id_id_key"),
        ForeignKeyConstraint(
            ["tenant_id", "meter_id"],
            ["meter.tenant_id", "meter.id"],
            name="meterreading_tenant_id_meter_id_fkey",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "photo_document_id"],
            ["document.tenant_id", "document.id"],
            name="meterreading_tenant_id_photo_document_id_fkey",
            ondelete="SET NULL (photo_document_id)",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "folio_transaction_id"],
            ["foliotransaction.tenant_id", "foliotransaction.id"],
            name="meterreading_tenant_id_folio_transaction_id_fkey",
        ),
        MIGRATION_ONLY,
    )

    meter_id: UUID = Field(sa_type=Uuid)
    read_at: dt.datetime = utc_datetime_field(nullable=False)  # type: ignore[assignment]
    reading_value: Decimal = Field(max_digits=14, decimal_places=3)
    consumption: Decimal | None = Field(default=None, max_digits=14, decimal_places=3)
    token_purchase_amount: Decimal | None = Field(
        default=None, max_digits=18, decimal_places=2, description="prepaid token top-ups"
    )
    photo_document_id: UUID | None = Field(default=None, sa_type=Uuid)
    read_by: str | None = Field(default=None, sa_type=Text)
    folio_transaction_id: UUID | None = Field(
        default=None, sa_type=Uuid, description="set when billed"
    )
    created_at: dt.datetime = utc_datetime_field(
        nullable=False, default_now=True, server_default_now=True
    )  # type: ignore[assignment]


class MeterReadingCreate(SQLModel):
    """Fields accepted when creating a MeterReading."""

    meter_id: UUID
    read_at: dt.datetime
    reading_value: Decimal = Field(max_digits=14, decimal_places=3)
    consumption: Decimal | None = Field(default=None, max_digits=14, decimal_places=3)
    token_purchase_amount: Decimal | None = Field(default=None, max_digits=18, decimal_places=2)
    photo_document_id: UUID | None = None
    read_by: str | None = None
    folio_transaction_id: UUID | None = None


class MeterReadingUpdate(SQLModel):
    """Fields accepted when patching a MeterReading (all optional)."""

    meter_id: UUID | None = None
    read_at: dt.datetime | None = None
    reading_value: Decimal | None = Field(default=None, max_digits=14, decimal_places=3)
    consumption: Decimal | None = Field(default=None, max_digits=14, decimal_places=3)
    token_purchase_amount: Decimal | None = Field(default=None, max_digits=18, decimal_places=2)
    photo_document_id: UUID | None = None
    read_by: str | None = None
    folio_transaction_id: UUID | None = None


class MeterReadingRead(SQLModel):
    """Fields returned when reading a MeterReading."""

    id: UUID
    tenant_id: UUID
    meter_id: UUID
    read_at: dt.datetime
    reading_value: Decimal
    consumption: Decimal | None
    token_purchase_amount: Decimal | None
    photo_document_id: UUID | None
    read_by: str | None
    folio_transaction_id: UUID | None
    created_at: dt.datetime
