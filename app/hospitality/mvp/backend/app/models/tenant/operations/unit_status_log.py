"""UnitStatusLog entity — table ``unitstatuslog``.

Tenant database, M. Operations (housekeeping & maintenance).

Unit status history (append-only).

Mirrors .ttest/contexts/schema-tenant.sql; the Alembic migration creates the table.
"""

import datetime as dt
from typing import Literal
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    ForeignKeyConstraint,
    Index,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlmodel import Field, SQLModel

from app.crud.base_model import MIGRATION_ONLY, TenantRecord, utc_datetime_field

UnitStatusLogField = Literal[
    "hk_status",
    "fo_status",
    "service_status",
]
UnitStatusLogSource = Literal[
    "staff",
    "mobile",
    "whatsapp",
    "system",
    "night_audit",
    "lock",
    "iot",
]


class UnitStatusLog(TenantRecord, table=True):
    """Unit status history (append-only)."""

    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="unitstatuslog_tenant_id_id_key"),
        ForeignKeyConstraint(
            ["tenant_id", "unit_id"],
            ["unit.tenant_id", "unit.id"],
            name="unitstatuslog_tenant_id_unit_id_fkey",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "task_id"],
            ["task.tenant_id", "task.id"],
            name="unitstatuslog_tenant_id_task_id_fkey",
            ondelete="SET NULL (task_id)",
        ),
        CheckConstraint(
            "field IN ('hk_status', 'fo_status', 'service_status')",
            name="unitstatuslog_field_check",
        ),
        CheckConstraint(
            ("source IN ('staff', 'mobile', 'whatsapp', 'system', 'night_audit', 'lock', 'iot')"),
            name="unitstatuslog_source_check",
        ),
        Index("ix_unitstatuslog_unit", "tenant_id", "unit_id", "changed_at"),
        MIGRATION_ONLY,
    )

    unit_id: UUID = Field(sa_type=Uuid)
    field: str = Field(sa_type=Text)
    old_value: str | None = Field(default=None, sa_type=Text)
    new_value: str = Field(sa_type=Text)
    source: str = Field(sa_type=Text)
    task_id: UUID | None = Field(default=None, sa_type=Uuid)
    changed_by: str | None = Field(default=None, sa_type=Text)
    changed_at: dt.datetime = utc_datetime_field(
        nullable=False, default_now=True, server_default_now=True
    )  # type: ignore[assignment]


class UnitStatusLogCreate(SQLModel):
    """Fields accepted when creating a UnitStatusLog."""

    unit_id: UUID
    field: UnitStatusLogField
    old_value: str | None = None
    new_value: str
    source: UnitStatusLogSource
    task_id: UUID | None = None
    changed_by: str | None = None
    changed_at: dt.datetime = Field(default_factory=lambda: dt.datetime.now(dt.UTC))


class UnitStatusLogUpdate(SQLModel):
    """Fields accepted when patching a UnitStatusLog (all optional)."""

    unit_id: UUID | None = None
    field: UnitStatusLogField | None = None
    old_value: str | None = None
    new_value: str | None = None
    source: UnitStatusLogSource | None = None
    task_id: UUID | None = None
    changed_by: str | None = None
    changed_at: dt.datetime | None = None


class UnitStatusLogRead(SQLModel):
    """Fields returned when reading a UnitStatusLog."""

    id: UUID
    tenant_id: UUID
    unit_id: UUID
    field: str
    old_value: str | None
    new_value: str
    source: str
    task_id: UUID | None
    changed_by: str | None
    changed_at: dt.datetime
