"""MarketSegment entity — table ``marketsegment``.

Tenant database, A. Organisation & property.

Code tables.

Mirrors .ttest/contexts/schema-tenant.sql; the Alembic migration creates the table.
"""

import datetime as dt
from uuid import UUID

from sqlalchemy import Text, UniqueConstraint, text
from sqlmodel import Field, SQLModel

from app.crud.base_model import MIGRATION_ONLY, TenantEntity


class MarketSegment(TenantEntity, table=True):
    """Code tables."""

    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="marketsegment_tenant_id_id_key"),
        UniqueConstraint("tenant_id", "code", name="marketsegment_tenant_id_code_key"),
        MIGRATION_ONLY,
    )

    code: str = Field(
        sa_type=Text, description="'leisure','corporate','government','group','long_stay'"
    )
    name: str = Field(sa_type=Text)
    is_active: bool = Field(default=True, sa_column_kwargs={"server_default": text("true")})


class MarketSegmentCreate(SQLModel):
    """Fields accepted when creating a MarketSegment."""

    code: str
    name: str
    is_active: bool = True


class MarketSegmentUpdate(SQLModel):
    """Fields accepted when patching a MarketSegment (all optional)."""

    code: str | None = None
    name: str | None = None
    is_active: bool | None = None


class MarketSegmentRead(SQLModel):
    """Fields returned when reading a MarketSegment."""

    id: UUID
    tenant_id: UUID
    code: str
    name: str
    is_active: bool
    created_at: dt.datetime
    updated_at: dt.datetime
    created_by: str | None
    updated_by: str | None
