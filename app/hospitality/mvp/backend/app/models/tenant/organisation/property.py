"""Property entity — table ``property``.

Tenant database, A. Organisation & property.

Property of any type; timezone, business date, tax region, check-in rules, syariah flag.

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
    Text,
    UniqueConstraint,
    Uuid,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlmodel import Field, SQLModel

from app.crud.base_model import MIGRATION_ONLY, TenantEntity

PropertyType = Literal[
    "hotel",
    "resort",
    "serviced_apartment",
    "hostel",
    "guesthouse",
    "villa_portfolio",
    "campsite",
    "condo_hotel",
    "coliving_kos",
    "lodge",
    "marina",
    "day_use",
    "homestay_cluster",
]
PropertyStatus = Literal[
    "setup",
    "live",
    "seasonal_closed",
    "suspended",
    "archived",
]
PropertyNightAuditMode = Literal[
    "auto",
    "attended",
]
PropertyReadinessRule = Literal[
    "clean",
    "inspected",
]
PropertyPriceDisplayMode = Literal[
    "nett",
    "plus_plus",
]


class Property(TenantEntity, table=True):
    """
    Property of any type; timezone, business date, tax region, check-in rules, syariah flag.
    """

    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="property_tenant_id_id_key"),
        UniqueConstraint("tenant_id", "code", name="property_tenant_id_code_key"),
        ForeignKeyConstraint(
            ["tenant_id", "legal_entity_id"],
            ["legalentity.tenant_id", "legalentity.id"],
            name="property_tenant_id_legal_entity_id_fkey",
        ),
        CheckConstraint(
            (
                "property_type IN ('hotel', 'resort', 'serviced_apartment', 'hostel', "
                "'guesthouse', 'villa_portfolio', 'campsite', 'condo_hotel', "
                "'coliving_kos', 'lodge', 'marina', 'day_use', 'homestay_cluster')"
            ),
            name="property_property_type_check",
        ),
        CheckConstraint(
            "status IN ('setup', 'live', 'seasonal_closed', 'suspended', 'archived')",
            name="property_status_check",
        ),
        CheckConstraint(
            "night_audit_mode IN ('auto', 'attended')", name="property_night_audit_mode_check"
        ),
        CheckConstraint(
            "readiness_rule IN ('clean', 'inspected')", name="property_readiness_rule_check"
        ),
        CheckConstraint(
            "price_display_mode IN ('nett', 'plus_plus')", name="property_price_display_mode_check"
        ),
        MIGRATION_ONLY,
    )

    legal_entity_id: UUID = Field(sa_type=Uuid)
    code: str = Field(sa_type=Text)
    name: str = Field(sa_type=Text)
    property_type: str = Field(sa_type=Text)
    status: str = Field(
        default="setup", sa_type=Text, sa_column_kwargs={"server_default": text("'setup'::text")}
    )
    timezone: str = Field(
        default="Asia/Jakarta",
        sa_type=Text,
        sa_column_kwargs={"server_default": text("'Asia/Jakarta'::text")},
    )
    currency: str = Field(
        default="IDR", sa_type=CHAR(3), sa_column_kwargs={"server_default": text("'IDR'::bpchar")}
    )
    country_code: str = Field(
        default="ID", sa_type=CHAR(2), sa_column_kwargs={"server_default": text("'ID'::bpchar")}
    )
    region_code: str | None = Field(
        default=None, sa_type=Text, description="kab/kota code (drives PBJT tax pack, APOA office)"
    )
    address: dict[str, Any] = Field(
        default_factory=dict,
        sa_type=JSONB,
        sa_column_kwargs={"server_default": text("'{}'::jsonb")},
    )
    latitude: Decimal | None = Field(default=None, max_digits=9, decimal_places=6)
    longitude: Decimal | None = Field(default=None, max_digits=9, decimal_places=6)
    phone: str | None = Field(default=None, sa_type=Text)
    email: str | None = Field(default=None, sa_type=Text)
    whatsapp_phone: str | None = Field(default=None, sa_type=Text)
    star_rating: Decimal | None = Field(default=None, max_digits=2, decimal_places=1)
    check_in_time: dt.time = Field(
        default=dt.time(14, 0),
        sa_column_kwargs={"server_default": text("'14:00:00'::time without time zone")},
    )
    check_out_time: dt.time = Field(
        default=dt.time(12, 0),
        sa_column_kwargs={"server_default": text("'12:00:00'::time without time zone")},
    )
    current_business_date: dt.date = Field(
        default_factory=dt.date.today, sa_column_kwargs={"server_default": text("CURRENT_DATE")}
    )
    night_audit_mode: str = Field(
        default="auto", sa_type=Text, sa_column_kwargs={"server_default": text("'auto'::text")}
    )
    night_audit_time: dt.time = Field(
        default=dt.time(2, 0),
        sa_column_kwargs={"server_default": text("'02:00:00'::time without time zone")},
    )
    readiness_rule: str = Field(
        default="clean", sa_type=Text, sa_column_kwargs={"server_default": text("'clean'::text")}
    )
    price_display_mode: str = Field(
        default="nett",
        sa_type=Text,
        sa_column_kwargs={"server_default": text("'nett'::text")},
        description='"++" = excl. service & tax',
    )
    is_syariah: bool = Field(default=False, sa_column_kwargs={"server_default": text("false")})
    max_occupancy: int | None = Field(
        default=None, description="fire-safety cap for the whole property"
    )
    licences: dict[str, Any] = Field(
        default_factory=dict,
        sa_type=JSONB,
        sa_column_kwargs={"server_default": text("'{}'::jsonb")},
        description='{"tdup":"...","pondok_wisata":"...","chse":"..."}',
    )
    amenities: list[str] = Field(
        default_factory=list,
        sa_type=ARRAY(Text),
        sa_column_kwargs={"server_default": text("'{}'::text[]")},
    )
    content: dict[str, Any] = Field(
        default_factory=dict,
        sa_type=JSONB,
        sa_column_kwargs={"server_default": text("'{}'::jsonb")},
        description='{"id-ID":{"description":"...","house_rules":"..."},"en":{...}}',
    )
    settings: dict[str, Any] = Field(
        default_factory=dict,
        sa_type=JSONB,
        sa_column_kwargs={"server_default": text("'{}'::jsonb")},
    )


class PropertyCreate(SQLModel):
    """Fields accepted when creating a Property."""

    legal_entity_id: UUID
    code: str
    name: str
    property_type: PropertyType
    status: PropertyStatus = "setup"
    timezone: str = "Asia/Jakarta"
    currency: str = Field(default="IDR", min_length=3, max_length=3)
    country_code: str = Field(default="ID", min_length=2, max_length=2)
    region_code: str | None = None
    address: dict[str, Any] = Field(default_factory=dict)
    latitude: Decimal | None = Field(default=None, max_digits=9, decimal_places=6)
    longitude: Decimal | None = Field(default=None, max_digits=9, decimal_places=6)
    phone: str | None = None
    email: str | None = None
    whatsapp_phone: str | None = None
    star_rating: Decimal | None = Field(default=None, max_digits=2, decimal_places=1)
    check_in_time: dt.time = dt.time(14, 0)
    check_out_time: dt.time = dt.time(12, 0)
    current_business_date: dt.date = Field(default_factory=dt.date.today)
    night_audit_mode: PropertyNightAuditMode = "auto"
    night_audit_time: dt.time = dt.time(2, 0)
    readiness_rule: PropertyReadinessRule = "clean"
    price_display_mode: PropertyPriceDisplayMode = "nett"
    is_syariah: bool = False
    max_occupancy: int | None = None
    licences: dict[str, Any] = Field(default_factory=dict)
    amenities: list[str] = Field(default_factory=list)
    content: dict[str, Any] = Field(default_factory=dict)
    settings: dict[str, Any] = Field(default_factory=dict)


class PropertyUpdate(SQLModel):
    """Fields accepted when patching a Property (all optional)."""

    legal_entity_id: UUID | None = None
    code: str | None = None
    name: str | None = None
    property_type: PropertyType | None = None
    status: PropertyStatus | None = None
    timezone: str | None = None
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    country_code: str | None = Field(default=None, min_length=2, max_length=2)
    region_code: str | None = None
    address: dict[str, Any] | None = None
    latitude: Decimal | None = Field(default=None, max_digits=9, decimal_places=6)
    longitude: Decimal | None = Field(default=None, max_digits=9, decimal_places=6)
    phone: str | None = None
    email: str | None = None
    whatsapp_phone: str | None = None
    star_rating: Decimal | None = Field(default=None, max_digits=2, decimal_places=1)
    check_in_time: dt.time | None = None
    check_out_time: dt.time | None = None
    current_business_date: dt.date | None = None
    night_audit_mode: PropertyNightAuditMode | None = None
    night_audit_time: dt.time | None = None
    readiness_rule: PropertyReadinessRule | None = None
    price_display_mode: PropertyPriceDisplayMode | None = None
    is_syariah: bool | None = None
    max_occupancy: int | None = None
    licences: dict[str, Any] | None = None
    amenities: list[str] | None = None
    content: dict[str, Any] | None = None
    settings: dict[str, Any] | None = None


class PropertyRead(SQLModel):
    """Fields returned when reading a Property."""

    id: UUID
    tenant_id: UUID
    legal_entity_id: UUID
    code: str
    name: str
    property_type: str
    status: str
    timezone: str
    currency: str
    country_code: str
    region_code: str | None
    address: dict[str, Any]
    latitude: Decimal | None
    longitude: Decimal | None
    phone: str | None
    email: str | None
    whatsapp_phone: str | None
    star_rating: Decimal | None
    check_in_time: dt.time
    check_out_time: dt.time
    current_business_date: dt.date
    night_audit_mode: str
    night_audit_time: dt.time
    readiness_rule: str
    price_display_mode: str
    is_syariah: bool
    max_occupancy: int | None
    licences: dict[str, Any]
    amenities: list[str]
    content: dict[str, Any]
    settings: dict[str, Any]
    created_at: dt.datetime
    updated_at: dt.datetime
    created_by: str | None
    updated_by: str | None
