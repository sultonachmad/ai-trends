"""WorkOrder entity — table ``workorder``.

Tenant database, M. Operations (housekeeping & maintenance).

Maintenance.

Mirrors .ttest/contexts/schema-tenant.sql; the Alembic migration creates the table.
"""

import datetime as dt
from decimal import Decimal
from typing import Literal
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
from sqlalchemy.dialects.postgresql import ARRAY
from sqlmodel import Field, SQLModel

from app.crud.base_model import MIGRATION_ONLY, TenantEntity, utc_datetime_field

WorkOrderPriority = Literal[
    "low",
    "normal",
    "high",
    "urgent",
]
WorkOrderStatus = Literal[
    "open",
    "assigned",
    "in_progress",
    "waiting_parts",
    "on_hold",
    "completed",
    "verified",
    "cancelled",
]
WorkOrderSource = Literal[
    "staff",
    "housekeeping",
    "guest",
    "inspection",
    "preventive",
    "iot",
    "ai",
]
WorkOrderRechargeTo = Literal[
    "none",
    "owner",
    "guest",
]


class WorkOrder(TenantEntity, table=True):
    """Maintenance."""

    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="workorder_tenant_id_id_key"),
        UniqueConstraint(
            "tenant_id", "property_id", "number", name="workorder_tenant_id_property_id_number_key"
        ),
        ForeignKeyConstraint(
            ["tenant_id", "property_id"],
            ["property.tenant_id", "property.id"],
            name="workorder_tenant_id_property_id_fkey",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "unit_id"],
            ["unit.tenant_id", "unit.id"],
            name="workorder_tenant_id_unit_id_fkey",
            ondelete="SET NULL (unit_id)",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "area_id"],
            ["propertyarea.tenant_id", "propertyarea.id"],
            name="workorder_tenant_id_area_id_fkey",
            ondelete="SET NULL (area_id)",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "asset_id"],
            ["asset.tenant_id", "asset.id"],
            name="workorder_tenant_id_asset_id_fkey",
            ondelete="SET NULL (asset_id)",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "reported_by_staff_id"],
            ["staffmember.tenant_id", "staffmember.id"],
            name="workorder_tenant_id_reported_by_staff_id_fkey",
            ondelete="SET NULL (reported_by_staff_id)",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "reported_by_guest_id"],
            ["guest.tenant_id", "guest.id"],
            name="workorder_tenant_id_reported_by_guest_id_fkey",
            ondelete="SET NULL (reported_by_guest_id)",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "assigned_staff_id"],
            ["staffmember.tenant_id", "staffmember.id"],
            name="workorder_tenant_id_assigned_staff_id_fkey",
            ondelete="SET NULL (assigned_staff_id)",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "vendor_id"],
            ["vendor.tenant_id", "vendor.id"],
            name="workorder_tenant_id_vendor_id_fkey",
            ondelete="SET NULL (vendor_id)",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "preventive_schedule_id"],
            ["preventiveschedule.tenant_id", "preventiveschedule.id"],
            name="workorder_tenant_id_preventive_schedule_id_fkey",
            ondelete="SET NULL (preventive_schedule_id)",
            use_alter=True,
        ),
        CheckConstraint(
            "priority IN ('low', 'normal', 'high', 'urgent')", name="workorder_priority_check"
        ),
        CheckConstraint(
            (
                "status IN ('open', 'assigned', 'in_progress', 'waiting_parts', "
                "'on_hold', 'completed', 'verified', 'cancelled')"
            ),
            name="workorder_status_check",
        ),
        CheckConstraint(
            (
                "source IN ('staff', 'housekeeping', 'guest', 'inspection', "
                "'preventive', 'iot', 'ai')"
            ),
            name="workorder_source_check",
        ),
        CheckConstraint(
            "recharge_to IN ('none', 'owner', 'guest')", name="workorder_recharge_to_check"
        ),
        Index(
            "ix_workorder_open",
            "tenant_id",
            "property_id",
            "status",
            postgresql_where=text("status <> ALL (ARRAY['verified'::text, 'cancelled'::text])"),
        ),
        MIGRATION_ONLY,
    )

    property_id: UUID = Field(sa_type=Uuid)
    number: str = Field(sa_type=Text)
    unit_id: UUID | None = Field(default=None, sa_type=Uuid)
    area_id: UUID | None = Field(default=None, sa_type=Uuid)
    asset_id: UUID | None = Field(default=None, sa_type=Uuid)
    category: str = Field(
        sa_type=Text, description="'plumbing','electrical','ac','furniture','it','pest',…"
    )
    priority: str = Field(
        default="normal", sa_type=Text, sa_column_kwargs={"server_default": text("'normal'::text")}
    )
    status: str = Field(
        default="open", sa_type=Text, sa_column_kwargs={"server_default": text("'open'::text")}
    )
    title: str = Field(sa_type=Text)
    description: str | None = Field(default=None, sa_type=Text)
    source: str = Field(
        default="staff", sa_type=Text, sa_column_kwargs={"server_default": text("'staff'::text")}
    )
    reported_by_staff_id: UUID | None = Field(default=None, sa_type=Uuid)
    reported_by_guest_id: UUID | None = Field(default=None, sa_type=Uuid)
    assigned_staff_id: UUID | None = Field(default=None, sa_type=Uuid)
    vendor_id: UUID | None = Field(default=None, sa_type=Uuid)
    is_guest_impacting: bool = Field(
        default=False, sa_column_kwargs={"server_default": text("false")}
    )
    sla_due_at: dt.datetime | None = utc_datetime_field(nullable=True)  # type: ignore[assignment]
    started_at: dt.datetime | None = utc_datetime_field(nullable=True)  # type: ignore[assignment]
    completed_at: dt.datetime | None = utc_datetime_field(nullable=True)  # type: ignore[assignment]
    verified_at: dt.datetime | None = utc_datetime_field(nullable=True)  # type: ignore[assignment]
    labour_minutes: int | None = Field(default=None)
    parts_cost: Decimal | None = Field(default=None, max_digits=18, decimal_places=2)
    vendor_cost: Decimal | None = Field(default=None, max_digits=18, decimal_places=2)
    recharge_to: str = Field(
        default="none", sa_type=Text, sa_column_kwargs={"server_default": text("'none'::text")}
    )
    photo_document_ids: list[UUID] = Field(
        default_factory=list,
        sa_type=ARRAY(Uuid),
        sa_column_kwargs={"server_default": text("'{}'::uuid[]")},
    )
    preventive_schedule_id: UUID | None = Field(
        default=None, sa_type=Uuid, description="FK added below"
    )


class WorkOrderCreate(SQLModel):
    """Fields accepted when creating a WorkOrder."""

    property_id: UUID
    number: str
    unit_id: UUID | None = None
    area_id: UUID | None = None
    asset_id: UUID | None = None
    category: str
    priority: WorkOrderPriority = "normal"
    status: WorkOrderStatus = "open"
    title: str
    description: str | None = None
    source: WorkOrderSource = "staff"
    reported_by_staff_id: UUID | None = None
    reported_by_guest_id: UUID | None = None
    assigned_staff_id: UUID | None = None
    vendor_id: UUID | None = None
    is_guest_impacting: bool = False
    sla_due_at: dt.datetime | None = None
    started_at: dt.datetime | None = None
    completed_at: dt.datetime | None = None
    verified_at: dt.datetime | None = None
    labour_minutes: int | None = None
    parts_cost: Decimal | None = Field(default=None, max_digits=18, decimal_places=2)
    vendor_cost: Decimal | None = Field(default=None, max_digits=18, decimal_places=2)
    recharge_to: WorkOrderRechargeTo = "none"
    photo_document_ids: list[UUID] = Field(default_factory=list)
    preventive_schedule_id: UUID | None = None


class WorkOrderUpdate(SQLModel):
    """Fields accepted when patching a WorkOrder (all optional)."""

    property_id: UUID | None = None
    number: str | None = None
    unit_id: UUID | None = None
    area_id: UUID | None = None
    asset_id: UUID | None = None
    category: str | None = None
    priority: WorkOrderPriority | None = None
    status: WorkOrderStatus | None = None
    title: str | None = None
    description: str | None = None
    source: WorkOrderSource | None = None
    reported_by_staff_id: UUID | None = None
    reported_by_guest_id: UUID | None = None
    assigned_staff_id: UUID | None = None
    vendor_id: UUID | None = None
    is_guest_impacting: bool | None = None
    sla_due_at: dt.datetime | None = None
    started_at: dt.datetime | None = None
    completed_at: dt.datetime | None = None
    verified_at: dt.datetime | None = None
    labour_minutes: int | None = None
    parts_cost: Decimal | None = Field(default=None, max_digits=18, decimal_places=2)
    vendor_cost: Decimal | None = Field(default=None, max_digits=18, decimal_places=2)
    recharge_to: WorkOrderRechargeTo | None = None
    photo_document_ids: list[UUID] | None = None
    preventive_schedule_id: UUID | None = None


class WorkOrderRead(SQLModel):
    """Fields returned when reading a WorkOrder."""

    id: UUID
    tenant_id: UUID
    property_id: UUID
    number: str
    unit_id: UUID | None
    area_id: UUID | None
    asset_id: UUID | None
    category: str
    priority: str
    status: str
    title: str
    description: str | None
    source: str
    reported_by_staff_id: UUID | None
    reported_by_guest_id: UUID | None
    assigned_staff_id: UUID | None
    vendor_id: UUID | None
    is_guest_impacting: bool
    sla_due_at: dt.datetime | None
    started_at: dt.datetime | None
    completed_at: dt.datetime | None
    verified_at: dt.datetime | None
    labour_minutes: int | None
    parts_cost: Decimal | None
    vendor_cost: Decimal | None
    recharge_to: str
    photo_document_ids: list[UUID]
    preventive_schedule_id: UUID | None
    created_at: dt.datetime
    updated_at: dt.datetime
    created_by: str | None
    updated_by: str | None
