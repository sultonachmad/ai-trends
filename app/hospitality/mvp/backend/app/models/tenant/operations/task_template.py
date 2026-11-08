"""TaskTemplate entity — table ``tasktemplate``.

Tenant database, M. Operations (housekeeping & maintenance).

Housekeeping tasks and checklists.

Mirrors .ttest/contexts/schema-tenant.sql; the Alembic migration creates the table.
"""

import datetime as dt
from typing import Any
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    ForeignKeyConstraint,
    SmallInteger,
    Text,
    UniqueConstraint,
    Uuid,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel

from app.crud.base_model import MIGRATION_ONLY, TenantEntity


class TaskTemplate(TenantEntity, table=True):
    """Housekeeping tasks and checklists."""

    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="tasktemplate_tenant_id_id_key"),
        UniqueConstraint(
            "tenant_id", "property_id", "code", name="tasktemplate_tenant_id_property_id_code_key"
        ),
        ForeignKeyConstraint(
            ["tenant_id", "property_id"],
            ["property.tenant_id", "property.id"],
            name="tasktemplate_tenant_id_property_id_fkey",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "unit_type_id"],
            ["unittype.tenant_id", "unittype.id"],
            name="tasktemplate_tenant_id_unit_type_id_fkey",
            ondelete="SET NULL (unit_type_id)",
        ),
        CheckConstraint("(standard_minutes > 0)", name="tasktemplate_standard_minutes_check"),
        MIGRATION_ONLY,
    )

    property_id: UUID = Field(sa_type=Uuid)
    code: str = Field(sa_type=Text)
    name: str = Field(sa_type=Text)
    task_kind: str = Field(sa_type=Text)
    unit_type_id: UUID | None = Field(default=None, sa_type=Uuid)
    checklist: list[Any] = Field(
        default_factory=list,
        sa_type=JSONB,
        sa_column_kwargs={"server_default": text("'[]'::jsonb")},
        description='[{"item":"Change sheets","mandatory":true,"photo":false}]',
    )
    standard_minutes: int = Field(default=30, sa_column_kwargs={"server_default": text("30")})
    required_photos: int = Field(
        default=0, sa_type=SmallInteger, sa_column_kwargs={"server_default": text("0")}
    )
    is_active: bool = Field(default=True, sa_column_kwargs={"server_default": text("true")})


class TaskTemplateCreate(SQLModel):
    """Fields accepted when creating a TaskTemplate."""

    property_id: UUID
    code: str
    name: str
    task_kind: str
    unit_type_id: UUID | None = None
    checklist: list[Any] = Field(default_factory=list)
    standard_minutes: int = Field(default=30, gt=0)
    required_photos: int = 0
    is_active: bool = True


class TaskTemplateUpdate(SQLModel):
    """Fields accepted when patching a TaskTemplate (all optional)."""

    property_id: UUID | None = None
    code: str | None = None
    name: str | None = None
    task_kind: str | None = None
    unit_type_id: UUID | None = None
    checklist: list[Any] | None = None
    standard_minutes: int | None = Field(default=None, gt=0)
    required_photos: int | None = None
    is_active: bool | None = None


class TaskTemplateRead(SQLModel):
    """Fields returned when reading a TaskTemplate."""

    id: UUID
    tenant_id: UUID
    property_id: UUID
    code: str
    name: str
    task_kind: str
    unit_type_id: UUID | None
    checklist: list[Any]
    standard_minutes: int
    required_photos: int
    is_active: bool
    created_at: dt.datetime
    updated_at: dt.datetime
    created_by: str | None
    updated_by: str | None
