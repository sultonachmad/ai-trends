"""Folio entity — table ``folio``.

Tenant database, H. Folios, postings, invoices, end-of-day.

Guest / master / house / passer-by / AR / deposit folios.

Mirrors .ttest/contexts/schema-tenant.sql; the Alembic migration creates the table.
"""

import datetime as dt
from decimal import Decimal
from typing import Literal
from uuid import UUID

from sqlalchemy import (
    CHAR,
    CheckConstraint,
    ForeignKeyConstraint,
    Index,
    SmallInteger,
    Text,
    UniqueConstraint,
    Uuid,
    text,
)
from sqlmodel import Field, SQLModel

from app.crud.base_model import MIGRATION_ONLY, TenantEntity, utc_datetime_field

FolioKind = Literal[
    "guest",
    "master",
    "house",
    "passer_by",
    "ar",
    "deposit",
]
FolioStatus = Literal[
    "open",
    "settled",
    "closed",
    "transferred",
]


class Folio(TenantEntity, table=True):
    """Guest / master / house / passer-by / AR / deposit folios."""

    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="folio_tenant_id_id_key"),
        ForeignKeyConstraint(
            ["tenant_id", "property_id"],
            ["property.tenant_id", "property.id"],
            name="folio_tenant_id_property_id_fkey",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "reservation_id"],
            ["reservation.tenant_id", "reservation.id"],
            name="folio_tenant_id_reservation_id_fkey",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "reservation_unit_id"],
            ["reservationunit.tenant_id", "reservationunit.id"],
            name="folio_tenant_id_reservation_unit_id_fkey",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "group_block_id"],
            ["groupblock.tenant_id", "groupblock.id"],
            name="folio_tenant_id_group_block_id_fkey",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "guest_id"],
            ["guest.tenant_id", "guest.id"],
            name="folio_tenant_id_guest_id_fkey",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "account_id"],
            ["account.tenant_id", "account.id"],
            name="folio_tenant_id_account_id_fkey",
        ),
        CheckConstraint(
            "kind IN ('guest', 'master', 'house', 'passer_by', 'ar', 'deposit')",
            name="folio_kind_check",
        ),
        CheckConstraint("((window_no >= 1) AND (window_no <= 9))", name="folio_window_no_check"),
        CheckConstraint(
            "status IN ('open', 'settled', 'closed', 'transferred')", name="folio_status_check"
        ),
        CheckConstraint("((kind <> 'ar'::text) OR (account_id IS NOT NULL))", name="folio_check"),
        Index(
            "ix_folio_reservation",
            "tenant_id",
            "reservation_id",
            postgresql_where=text("reservation_id IS NOT NULL"),
        ),
        Index(
            "ix_folio_account_open",
            "tenant_id",
            "account_id",
            postgresql_where=text("(account_id IS NOT NULL) AND (status = 'open'::text)"),
        ),
        MIGRATION_ONLY,
    )

    property_id: UUID = Field(sa_type=Uuid)
    kind: str = Field(sa_type=Text)
    reservation_id: UUID | None = Field(default=None, sa_type=Uuid)
    reservation_unit_id: UUID | None = Field(default=None, sa_type=Uuid)
    group_block_id: UUID | None = Field(default=None, sa_type=Uuid)
    guest_id: UUID | None = Field(default=None, sa_type=Uuid)
    account_id: UUID | None = Field(default=None, sa_type=Uuid)
    window_no: int = Field(
        default=1, sa_type=SmallInteger, sa_column_kwargs={"server_default": text("1")}
    )
    status: str = Field(
        default="open", sa_type=Text, sa_column_kwargs={"server_default": text("'open'::text")}
    )
    currency: str = Field(
        default="IDR", sa_type=CHAR(3), sa_column_kwargs={"server_default": text("'IDR'::bpchar")}
    )
    balance: Decimal = Field(
        default=Decimal("0"),
        max_digits=18,
        decimal_places=2,
        sa_column_kwargs={"server_default": text("0")},
        description="denormalised; truth = sum(foliotransaction)",
    )
    credit_limit: Decimal | None = Field(default=None, max_digits=18, decimal_places=2)
    closed_at: dt.datetime | None = utc_datetime_field(nullable=True)  # type: ignore[assignment]
    version: int = Field(default=1, sa_column_kwargs={"server_default": text("1")})


class FolioCreate(SQLModel):
    """Fields accepted when creating a Folio."""

    property_id: UUID
    kind: FolioKind
    reservation_id: UUID | None = None
    reservation_unit_id: UUID | None = None
    group_block_id: UUID | None = None
    guest_id: UUID | None = None
    account_id: UUID | None = None
    window_no: int = Field(default=1, ge=1, le=9)
    status: FolioStatus = "open"
    currency: str = Field(default="IDR", min_length=3, max_length=3)
    balance: Decimal = Field(default=Decimal("0"), max_digits=18, decimal_places=2)
    credit_limit: Decimal | None = Field(default=None, max_digits=18, decimal_places=2)
    closed_at: dt.datetime | None = None


class FolioUpdate(SQLModel):
    """Fields accepted when patching a Folio (all optional)."""

    property_id: UUID | None = None
    kind: FolioKind | None = None
    reservation_id: UUID | None = None
    reservation_unit_id: UUID | None = None
    group_block_id: UUID | None = None
    guest_id: UUID | None = None
    account_id: UUID | None = None
    window_no: int | None = Field(default=None, ge=1, le=9)
    status: FolioStatus | None = None
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    balance: Decimal | None = Field(default=None, max_digits=18, decimal_places=2)
    credit_limit: Decimal | None = Field(default=None, max_digits=18, decimal_places=2)
    closed_at: dt.datetime | None = None


class FolioRead(SQLModel):
    """Fields returned when reading a Folio."""

    id: UUID
    tenant_id: UUID
    property_id: UUID
    kind: str
    reservation_id: UUID | None
    reservation_unit_id: UUID | None
    group_block_id: UUID | None
    guest_id: UUID | None
    account_id: UUID | None
    window_no: int
    status: str
    currency: str
    balance: Decimal
    credit_limit: Decimal | None
    closed_at: dt.datetime | None
    version: int
    created_at: dt.datetime
    updated_at: dt.datetime
    created_by: str | None
    updated_by: str | None
