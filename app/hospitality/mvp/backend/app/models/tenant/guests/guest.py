"""Guest entity — table ``guest``.

Tenant database, F. Accounts & guests.

Guest profile (single-name friendly), stats, merge, anonymisation.

Mirrors .ttest/contexts/schema-tenant.sql; the Alembic migration creates the table.
"""

import datetime as dt
from decimal import Decimal
from typing import Any, Literal
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
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlmodel import Field, SQLModel

from app.crud.base_model import MIGRATION_ONLY, TenantEntity, utc_datetime_field

GuestGender = Literal[
    "male",
    "female",
    "other",
    "undisclosed",
]


class Guest(TenantEntity, table=True):
    """Guest profile (single-name friendly), stats, merge, anonymisation."""

    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="guest_tenant_id_id_key"),
        ForeignKeyConstraint(
            ["tenant_id", "employer_account_id"],
            ["account.tenant_id", "account.id"],
            name="guest_tenant_id_employer_account_id_fkey",
            ondelete="SET NULL (employer_account_id)",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "merged_into_guest_id"],
            ["guest.tenant_id", "guest.id"],
            name="guest_tenant_id_merged_into_guest_id_fkey",
            ondelete="SET NULL (merged_into_guest_id)",
        ),
        CheckConstraint(
            "gender IN ('male', 'female', 'other', 'undisclosed')", name="guest_gender_check"
        ),
        CheckConstraint("((vip_level >= 0) AND (vip_level <= 9))", name="guest_vip_level_check"),
        Index(
            "ix_guest_email",
            "tenant_id",
            text("lower(email)"),
            postgresql_where=text("email IS NOT NULL"),
        ),
        Index("ix_guest_phone", "tenant_id", "phone", postgresql_where=text("phone IS NOT NULL")),
        Index(
            "ix_guest_name_trgm",
            "full_name",
            postgresql_using="gin",
            postgresql_ops={"full_name": "gin_trgm_ops"},
        ),
        MIGRATION_ONLY,
    )

    full_name: str = Field(sa_type=Text, description="many Indonesians have a single name")
    given_name: str | None = Field(default=None, sa_type=Text)
    family_name: str | None = Field(default=None, sa_type=Text)
    email: str | None = Field(default=None, sa_type=Text)
    phone: str | None = Field(default=None, sa_type=Text, description="E.164")
    whatsapp_phone: str | None = Field(default=None, sa_type=Text)
    nationality: str | None = Field(default=None, sa_type=CHAR(2))
    gender: str | None = Field(default=None, sa_type=Text)
    birth_date: dt.date | None = Field(default=None)
    language: str | None = Field(default=None, sa_type=Text)
    address: dict[str, Any] = Field(
        default_factory=dict,
        sa_type=JSONB,
        sa_column_kwargs={"server_default": text("'{}'::jsonb")},
    )
    employer_account_id: UUID | None = Field(default=None, sa_type=Uuid)
    vip_level: int = Field(
        default=0, sa_type=SmallInteger, sa_column_kwargs={"server_default": text("0")}
    )
    tags: list[str] = Field(
        default_factory=list,
        sa_type=ARRAY(Text),
        sa_column_kwargs={"server_default": text("'{}'::text[]")},
    )
    is_blacklisted: bool = Field(default=False, sa_column_kwargs={"server_default": text("false")})
    blacklist_reason: str | None = Field(default=None, sa_type=Text)
    notes: str | None = Field(default=None, sa_type=Text)
    stay_count: int = Field(default=0, sa_column_kwargs={"server_default": text("0")})
    night_count: int = Field(default=0, sa_column_kwargs={"server_default": text("0")})
    total_spend: Decimal = Field(
        default=Decimal("0"),
        max_digits=18,
        decimal_places=2,
        sa_column_kwargs={"server_default": text("0")},
    )
    last_stay_on: dt.date | None = Field(default=None)
    merged_into_guest_id: UUID | None = Field(default=None, sa_type=Uuid)
    anonymized_at: dt.datetime | None = utc_datetime_field(nullable=True)  # type: ignore[assignment]


class GuestCreate(SQLModel):
    """Fields accepted when creating a Guest."""

    full_name: str
    given_name: str | None = None
    family_name: str | None = None
    email: str | None = None
    phone: str | None = None
    whatsapp_phone: str | None = None
    nationality: str | None = Field(default=None, min_length=2, max_length=2)
    gender: GuestGender | None = None
    birth_date: dt.date | None = None
    language: str | None = None
    address: dict[str, Any] = Field(default_factory=dict)
    employer_account_id: UUID | None = None
    vip_level: int = Field(default=0, ge=0, le=9)
    tags: list[str] = Field(default_factory=list)
    is_blacklisted: bool = False
    blacklist_reason: str | None = None
    notes: str | None = None
    stay_count: int = 0
    night_count: int = 0
    total_spend: Decimal = Field(default=Decimal("0"), max_digits=18, decimal_places=2)
    last_stay_on: dt.date | None = None
    merged_into_guest_id: UUID | None = None
    anonymized_at: dt.datetime | None = None


class GuestUpdate(SQLModel):
    """Fields accepted when patching a Guest (all optional)."""

    full_name: str | None = None
    given_name: str | None = None
    family_name: str | None = None
    email: str | None = None
    phone: str | None = None
    whatsapp_phone: str | None = None
    nationality: str | None = Field(default=None, min_length=2, max_length=2)
    gender: GuestGender | None = None
    birth_date: dt.date | None = None
    language: str | None = None
    address: dict[str, Any] | None = None
    employer_account_id: UUID | None = None
    vip_level: int | None = Field(default=None, ge=0, le=9)
    tags: list[str] | None = None
    is_blacklisted: bool | None = None
    blacklist_reason: str | None = None
    notes: str | None = None
    stay_count: int | None = None
    night_count: int | None = None
    total_spend: Decimal | None = Field(default=None, max_digits=18, decimal_places=2)
    last_stay_on: dt.date | None = None
    merged_into_guest_id: UUID | None = None
    anonymized_at: dt.datetime | None = None


class GuestRead(SQLModel):
    """Fields returned when reading a Guest."""

    id: UUID
    tenant_id: UUID
    full_name: str
    given_name: str | None
    family_name: str | None
    email: str | None
    phone: str | None
    whatsapp_phone: str | None
    nationality: str | None
    gender: str | None
    birth_date: dt.date | None
    language: str | None
    address: dict[str, Any]
    employer_account_id: UUID | None
    vip_level: int
    tags: list[str]
    is_blacklisted: bool
    blacklist_reason: str | None
    notes: str | None
    stay_count: int
    night_count: int
    total_spend: Decimal
    last_stay_on: dt.date | None
    merged_into_guest_id: UUID | None
    anonymized_at: dt.datetime | None
    created_at: dt.datetime
    updated_at: dt.datetime
    created_by: str | None
    updated_by: str | None
