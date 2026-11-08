"""PosOrder entity — table ``posorder``.

Tenant database, Q. Ancillary / POS lite.

POS Lite, services, gift vouchers.

Mirrors .ttest/contexts/schema-tenant.sql; the Alembic migration creates the table.
"""

import datetime as dt
from decimal import Decimal
from typing import Literal
from uuid import UUID

from sqlalchemy import CheckConstraint, ForeignKeyConstraint, Text, UniqueConstraint, Uuid, text
from sqlmodel import Field, SQLModel

from app.crud.base_model import MIGRATION_ONLY, TenantEntity, utc_datetime_field

PosOrderStatus = Literal[
    "open",
    "settled",
    "voided",
]
PosOrderSettlementKind = Literal[
    "room_charge",
    "payment",
    "complimentary",
    "package_entitlement",
]


class PosOrder(TenantEntity, table=True):
    """POS Lite, services, gift vouchers."""

    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="posorder_tenant_id_id_key"),
        ForeignKeyConstraint(
            ["tenant_id", "outlet_id"],
            ["outlet.tenant_id", "outlet.id"],
            name="posorder_tenant_id_outlet_id_fkey",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "folio_id"],
            ["folio.tenant_id", "folio.id"],
            name="posorder_tenant_id_folio_id_fkey",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "reservation_unit_id"],
            ["reservationunit.tenant_id", "reservationunit.id"],
            name="posorder_tenant_id_reservation_unit_id_fkey",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "payment_id"],
            ["payment.tenant_id", "payment.id"],
            name="posorder_tenant_id_payment_id_fkey",
        ),
        CheckConstraint("status IN ('open', 'settled', 'voided')", name="posorder_status_check"),
        CheckConstraint(
            (
                "settlement_kind IN ('room_charge', 'payment', 'complimentary', "
                "'package_entitlement')"
            ),
            name="posorder_settlement_kind_check",
        ),
        MIGRATION_ONLY,
    )

    outlet_id: UUID = Field(sa_type=Uuid)
    business_date: dt.date = Field()
    status: str = Field(
        default="open", sa_type=Text, sa_column_kwargs={"server_default": text("'open'::text")}
    )
    settlement_kind: str | None = Field(default=None, sa_type=Text)
    folio_id: UUID | None = Field(default=None, sa_type=Uuid)
    reservation_unit_id: UUID | None = Field(default=None, sa_type=Uuid)
    payment_id: UUID | None = Field(default=None, sa_type=Uuid)
    total_amount: Decimal = Field(
        default=Decimal("0"),
        max_digits=18,
        decimal_places=2,
        sa_column_kwargs={"server_default": text("0")},
    )
    opened_by: str | None = Field(default=None, sa_type=Text)
    closed_at: dt.datetime | None = utc_datetime_field(nullable=True)  # type: ignore[assignment]


class PosOrderCreate(SQLModel):
    """Fields accepted when creating a PosOrder."""

    outlet_id: UUID
    business_date: dt.date
    status: PosOrderStatus = "open"
    settlement_kind: PosOrderSettlementKind | None = None
    folio_id: UUID | None = None
    reservation_unit_id: UUID | None = None
    payment_id: UUID | None = None
    total_amount: Decimal = Field(default=Decimal("0"), max_digits=18, decimal_places=2)
    opened_by: str | None = None
    closed_at: dt.datetime | None = None


class PosOrderUpdate(SQLModel):
    """Fields accepted when patching a PosOrder (all optional)."""

    outlet_id: UUID | None = None
    business_date: dt.date | None = None
    status: PosOrderStatus | None = None
    settlement_kind: PosOrderSettlementKind | None = None
    folio_id: UUID | None = None
    reservation_unit_id: UUID | None = None
    payment_id: UUID | None = None
    total_amount: Decimal | None = Field(default=None, max_digits=18, decimal_places=2)
    opened_by: str | None = None
    closed_at: dt.datetime | None = None


class PosOrderRead(SQLModel):
    """Fields returned when reading a PosOrder."""

    id: UUID
    tenant_id: UUID
    outlet_id: UUID
    business_date: dt.date
    status: str
    settlement_kind: str | None
    folio_id: UUID | None
    reservation_unit_id: UUID | None
    payment_id: UUID | None
    total_amount: Decimal
    opened_by: str | None
    closed_at: dt.datetime | None
    created_at: dt.datetime
    updated_at: dt.datetime
    created_by: str | None
    updated_by: str | None
