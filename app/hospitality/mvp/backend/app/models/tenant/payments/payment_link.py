"""PaymentLink entity — table ``paymentlink``.

Tenant database, I. Payments.

Shareable pay link (sent over WhatsApp/email). Token goes in the URL path.

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
    Text,
    UniqueConstraint,
    Uuid,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY
from sqlmodel import Field, SQLModel

from app.crud.base_model import MIGRATION_ONLY, TenantEntity, utc_datetime_field

PaymentLinkStatus = Literal[
    "active",
    "paid",
    "expired",
    "cancelled",
]
PaymentLinkSentVia = Literal[
    "whatsapp",
    "email",
    "sms",
    "copied",
]


class PaymentLink(TenantEntity, table=True):
    """Shareable pay link (sent over WhatsApp/email). Token goes in the URL path."""

    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="paymentlink_tenant_id_id_key"),
        UniqueConstraint("token_hash", name="paymentlink_token_hash_key"),
        ForeignKeyConstraint(
            ["tenant_id", "property_id"],
            ["property.tenant_id", "property.id"],
            name="paymentlink_tenant_id_property_id_fkey",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "reservation_id"],
            ["reservation.tenant_id", "reservation.id"],
            name="paymentlink_tenant_id_reservation_id_fkey",
            ondelete="SET NULL (reservation_id)",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "folio_id"],
            ["folio.tenant_id", "folio.id"],
            name="paymentlink_tenant_id_folio_id_fkey",
            ondelete="SET NULL (folio_id)",
        ),
        CheckConstraint("(amount > (0)::numeric)", name="paymentlink_amount_check"),
        CheckConstraint(
            "status IN ('active', 'paid', 'expired', 'cancelled')", name="paymentlink_status_check"
        ),
        CheckConstraint(
            "sent_via IN ('whatsapp', 'email', 'sms', 'copied')", name="paymentlink_sent_via_check"
        ),
        MIGRATION_ONLY,
    )

    property_id: UUID = Field(sa_type=Uuid)
    reservation_id: UUID | None = Field(default=None, sa_type=Uuid)
    folio_id: UUID | None = Field(default=None, sa_type=Uuid)
    token_hash: str = Field(sa_type=Text)
    amount: Decimal = Field(max_digits=18, decimal_places=2)
    currency: str = Field(
        default="IDR", sa_type=CHAR(3), sa_column_kwargs={"server_default": text("'IDR'::bpchar")}
    )
    description: str | None = Field(default=None, sa_type=Text)
    allowed_methods: list[str] = Field(
        default_factory=list,
        sa_type=ARRAY(Text),
        sa_column_kwargs={"server_default": text("'{}'::text[]")},
    )
    save_instrument: bool = Field(default=False, sa_column_kwargs={"server_default": text("false")})
    expires_at: dt.datetime = utc_datetime_field(nullable=False)  # type: ignore[assignment]
    status: str = Field(
        default="active", sa_type=Text, sa_column_kwargs={"server_default": text("'active'::text")}
    )
    sent_via: str | None = Field(default=None, sa_type=Text)
    paid_at: dt.datetime | None = utc_datetime_field(nullable=True)  # type: ignore[assignment]


class PaymentLinkCreate(SQLModel):
    """Fields accepted when creating a PaymentLink."""

    property_id: UUID
    reservation_id: UUID | None = None
    folio_id: UUID | None = None
    amount: Decimal = Field(max_digits=18, decimal_places=2, gt=0)
    currency: str = Field(default="IDR", min_length=3, max_length=3)
    description: str | None = None
    allowed_methods: list[str] = Field(default_factory=list)
    save_instrument: bool = False
    expires_at: dt.datetime
    status: PaymentLinkStatus = "active"
    sent_via: PaymentLinkSentVia | None = None
    paid_at: dt.datetime | None = None


class PaymentLinkUpdate(SQLModel):
    """Fields accepted when patching a PaymentLink (all optional)."""

    property_id: UUID | None = None
    reservation_id: UUID | None = None
    folio_id: UUID | None = None
    amount: Decimal | None = Field(default=None, max_digits=18, decimal_places=2, gt=0)
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    description: str | None = None
    allowed_methods: list[str] | None = None
    save_instrument: bool | None = None
    expires_at: dt.datetime | None = None
    status: PaymentLinkStatus | None = None
    sent_via: PaymentLinkSentVia | None = None
    paid_at: dt.datetime | None = None


class PaymentLinkRead(SQLModel):
    """Fields returned when reading a PaymentLink (never returns: token_hash)."""

    id: UUID
    tenant_id: UUID
    property_id: UUID
    reservation_id: UUID | None
    folio_id: UUID | None
    amount: Decimal
    currency: str
    description: str | None
    allowed_methods: list[str]
    save_instrument: bool
    expires_at: dt.datetime
    status: str
    sent_via: str | None
    paid_at: dt.datetime | None
    created_at: dt.datetime
    updated_at: dt.datetime
    created_by: str | None
    updated_by: str | None
