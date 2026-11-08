"""Task entity — table ``task``.

Tenant database, M. Operations (housekeeping & maintenance).

Housekeeping and service tasks (not maintenance work orders).

Mirrors .ttest/contexts/schema-tenant.sql; the Alembic migration creates the table.
"""

import datetime as dt
from decimal import Decimal
from typing import Any, Literal
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    ForeignKeyConstraint,
    Index,
    Text,
    UniqueConstraint,
    Uuid,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlmodel import Field, SQLModel

from app.crud.base_model import MIGRATION_ONLY, TenantEntity, utc_datetime_field

TaskKind = Literal[
    "departure_clean",
    "stayover_clean",
    "turndown",
    "deep_clean",
    "linen_change",
    "inspection",
    "pre_arrival_check",
    "turnover",
    "guest_request",
    "public_area",
    "other",
]
TaskPriority = Literal[
    "low",
    "normal",
    "high",
    "urgent",
]
TaskStatus = Literal[
    "pending",
    "assigned",
    "in_progress",
    "paused",
    "done",
    "inspected",
    "failed_inspection",
    "skipped_dnd",
    "refused",
    "cancelled",
]
TaskInspectionResult = Literal[
    "pass",
    "fail",
]
TaskSource = Literal[
    "auto",
    "manual",
    "guest",
    "message",
    "inspection",
    "ai",
]


class Task(TenantEntity, table=True):
    """Housekeeping and service tasks (not maintenance work orders)."""

    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="task_tenant_id_id_key"),
        ForeignKeyConstraint(
            ["tenant_id", "property_id"],
            ["property.tenant_id", "property.id"],
            name="task_tenant_id_property_id_fkey",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "template_id"],
            ["tasktemplate.tenant_id", "tasktemplate.id"],
            name="task_tenant_id_template_id_fkey",
            ondelete="SET NULL (template_id)",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "unit_id"],
            ["unit.tenant_id", "unit.id"],
            name="task_tenant_id_unit_id_fkey",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "area_id"],
            ["propertyarea.tenant_id", "propertyarea.id"],
            name="task_tenant_id_area_id_fkey",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "reservation_unit_id"],
            ["reservationunit.tenant_id", "reservationunit.id"],
            name="task_tenant_id_reservation_unit_id_fkey",
            ondelete="SET NULL (reservation_unit_id)",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "assigned_staff_id"],
            ["staffmember.tenant_id", "staffmember.id"],
            name="task_tenant_id_assigned_staff_id_fkey",
            ondelete="SET NULL (assigned_staff_id)",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "assigned_vendor_id"],
            ["vendor.tenant_id", "vendor.id"],
            name="task_tenant_id_assigned_vendor_id_fkey",
            ondelete="SET NULL (assigned_vendor_id)",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "inspected_by_staff_id"],
            ["staffmember.tenant_id", "staffmember.id"],
            name="task_tenant_id_inspected_by_staff_id_fkey",
            ondelete="SET NULL (inspected_by_staff_id)",
        ),
        CheckConstraint(
            (
                "task_kind IN ('departure_clean', 'stayover_clean', 'turndown', "
                "'deep_clean', 'linen_change', 'inspection', 'pre_arrival_check', "
                "'turnover', 'guest_request', 'public_area', 'other')"
            ),
            name="task_task_kind_check",
        ),
        CheckConstraint(
            "priority IN ('low', 'normal', 'high', 'urgent')", name="task_priority_check"
        ),
        CheckConstraint(
            (
                "status IN ('pending', 'assigned', 'in_progress', 'paused', 'done', "
                "'inspected', 'failed_inspection', 'skipped_dnd', 'refused', 'cancelled')"
            ),
            name="task_status_check",
        ),
        CheckConstraint(
            "inspection_result IN ('pass', 'fail')", name="task_inspection_result_check"
        ),
        CheckConstraint(
            "source IN ('auto', 'manual', 'guest', 'message', 'inspection', 'ai')",
            name="task_source_check",
        ),
        CheckConstraint(
            ("((unit_id IS NOT NULL) OR (area_id IS NOT NULL) OR (task_kind = 'other'::text))"),
            name="task_check",
        ),
        Index("ix_task_board", "tenant_id", "property_id", "scheduled_for", "status"),
        Index(
            "ix_task_assignee",
            "tenant_id",
            "assigned_staff_id",
            "scheduled_for",
            postgresql_where=text("assigned_staff_id IS NOT NULL"),
        ),
        MIGRATION_ONLY,
    )

    property_id: UUID = Field(sa_type=Uuid)
    task_kind: str = Field(sa_type=Text)
    template_id: UUID | None = Field(default=None, sa_type=Uuid)
    unit_id: UUID | None = Field(default=None, sa_type=Uuid)
    area_id: UUID | None = Field(default=None, sa_type=Uuid)
    reservation_unit_id: UUID | None = Field(default=None, sa_type=Uuid)
    scheduled_for: dt.date = Field()
    due_at: dt.datetime | None = utc_datetime_field(nullable=True)  # type: ignore[assignment]
    priority: str = Field(
        default="normal", sa_type=Text, sa_column_kwargs={"server_default": text("'normal'::text")}
    )
    status: str = Field(
        default="pending",
        sa_type=Text,
        sa_column_kwargs={"server_default": text("'pending'::text")},
    )
    assigned_staff_id: UUID | None = Field(default=None, sa_type=Uuid)
    assigned_vendor_id: UUID | None = Field(default=None, sa_type=Uuid)
    standard_minutes: int | None = Field(default=None)
    started_at: dt.datetime | None = utc_datetime_field(nullable=True)  # type: ignore[assignment]
    completed_at: dt.datetime | None = utc_datetime_field(nullable=True)  # type: ignore[assignment]
    inspected_by_staff_id: UUID | None = Field(default=None, sa_type=Uuid)
    inspection_result: str | None = Field(default=None, sa_type=Text)
    checklist_result: list[Any] = Field(
        default_factory=list,
        sa_type=JSONB,
        sa_column_kwargs={"server_default": text("'[]'::jsonb")},
    )
    photo_document_ids: list[UUID] = Field(
        default_factory=list,
        sa_type=ARRAY(Uuid),
        sa_column_kwargs={"server_default": text("'{}'::uuid[]")},
    )
    notes: str | None = Field(default=None, sa_type=Text)
    source: str = Field(
        default="auto", sa_type=Text, sa_column_kwargs={"server_default": text("'auto'::text")}
    )
    vendor_fee: Decimal | None = Field(default=None, max_digits=18, decimal_places=2)


class TaskCreate(SQLModel):
    """Fields accepted when creating a Task."""

    property_id: UUID
    task_kind: TaskKind
    template_id: UUID | None = None
    unit_id: UUID | None = None
    area_id: UUID | None = None
    reservation_unit_id: UUID | None = None
    scheduled_for: dt.date
    due_at: dt.datetime | None = None
    priority: TaskPriority = "normal"
    status: TaskStatus = "pending"
    assigned_staff_id: UUID | None = None
    assigned_vendor_id: UUID | None = None
    standard_minutes: int | None = None
    started_at: dt.datetime | None = None
    completed_at: dt.datetime | None = None
    inspected_by_staff_id: UUID | None = None
    inspection_result: TaskInspectionResult | None = None
    checklist_result: list[Any] = Field(default_factory=list)
    photo_document_ids: list[UUID] = Field(default_factory=list)
    notes: str | None = None
    source: TaskSource = "auto"
    vendor_fee: Decimal | None = Field(default=None, max_digits=18, decimal_places=2)


class TaskUpdate(SQLModel):
    """Fields accepted when patching a Task (all optional)."""

    property_id: UUID | None = None
    task_kind: TaskKind | None = None
    template_id: UUID | None = None
    unit_id: UUID | None = None
    area_id: UUID | None = None
    reservation_unit_id: UUID | None = None
    scheduled_for: dt.date | None = None
    due_at: dt.datetime | None = None
    priority: TaskPriority | None = None
    status: TaskStatus | None = None
    assigned_staff_id: UUID | None = None
    assigned_vendor_id: UUID | None = None
    standard_minutes: int | None = None
    started_at: dt.datetime | None = None
    completed_at: dt.datetime | None = None
    inspected_by_staff_id: UUID | None = None
    inspection_result: TaskInspectionResult | None = None
    checklist_result: list[Any] | None = None
    photo_document_ids: list[UUID] | None = None
    notes: str | None = None
    source: TaskSource | None = None
    vendor_fee: Decimal | None = Field(default=None, max_digits=18, decimal_places=2)


class TaskRead(SQLModel):
    """Fields returned when reading a Task."""

    id: UUID
    tenant_id: UUID
    property_id: UUID
    task_kind: str
    template_id: UUID | None
    unit_id: UUID | None
    area_id: UUID | None
    reservation_unit_id: UUID | None
    scheduled_for: dt.date
    due_at: dt.datetime | None
    priority: str
    status: str
    assigned_staff_id: UUID | None
    assigned_vendor_id: UUID | None
    standard_minutes: int | None
    started_at: dt.datetime | None
    completed_at: dt.datetime | None
    inspected_by_staff_id: UUID | None
    inspection_result: str | None
    checklist_result: list[Any]
    photo_document_ids: list[UUID]
    notes: str | None
    source: str
    vendor_fee: Decimal | None
    created_at: dt.datetime
    updated_at: dt.datetime
    created_by: str | None
    updated_by: str | None
