"""Module entity — table ``module``.

Control-plane database, Control plane.

Sellable product modules (PMS Core and add-ons).

Mirrors .ttest/contexts/schema-control-plane.sql; the Alembic migration creates the table.
"""

import datetime as dt

from sqlalchemy import Text, text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlmodel import Field, SQLModel

from app.crud.base_model import MIGRATION_ONLY, utc_datetime_field


class Module(SQLModel, table=True):
    """Sellable product modules (PMS Core and add-ons)."""

    __table_args__ = (MIGRATION_ONLY,)

    code: str = Field(
        primary_key=True, sa_type=Text, description="e.g. 'pms_core', 'channel_manager'"
    )
    name: str = Field(sa_type=Text)
    description: str | None = Field(default=None, sa_type=Text)
    depends_on: list[str] = Field(
        default_factory=list,
        sa_type=ARRAY(Text),
        sa_column_kwargs={"server_default": text("'{}'::text[]")},
        description="module codes that must also be enabled",
    )
    is_active: bool = Field(default=True, sa_column_kwargs={"server_default": text("true")})
    sort_order: int = Field(default=0, sa_column_kwargs={"server_default": text("0")})
    created_at: dt.datetime = utc_datetime_field(
        nullable=False, default_now=True, server_default_now=True
    )  # type: ignore[assignment]
    updated_at: dt.datetime = utc_datetime_field(
        nullable=False, default_now=True, onupdate_now=True, server_default_now=True
    )  # type: ignore[assignment]


class ModuleCreate(SQLModel):
    """Fields accepted when creating a Module."""

    code: str
    name: str
    description: str | None = None
    depends_on: list[str] = Field(default_factory=list)
    is_active: bool = True
    sort_order: int = 0


class ModuleUpdate(SQLModel):
    """Fields accepted when patching a Module (all optional)."""

    name: str | None = None
    description: str | None = None
    depends_on: list[str] | None = None
    is_active: bool | None = None
    sort_order: int | None = None


class ModuleRead(SQLModel):
    """Fields returned when reading a Module."""

    code: str
    name: str
    description: str | None
    depends_on: list[str]
    is_active: bool
    sort_order: int
    created_at: dt.datetime
    updated_at: dt.datetime
