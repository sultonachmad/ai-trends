"""Tenant database — M. Operations (housekeeping & maintenance)."""

from app.models.tenant.operations.asset import Asset, AssetCreate, AssetRead, AssetUpdate
from app.models.tenant.operations.preventive_schedule import (
    PreventiveSchedule,
    PreventiveScheduleCreate,
    PreventiveScheduleRead,
    PreventiveScheduleUpdate,
)
from app.models.tenant.operations.task import Task, TaskCreate, TaskRead, TaskUpdate
from app.models.tenant.operations.task_template import (
    TaskTemplate,
    TaskTemplateCreate,
    TaskTemplateRead,
    TaskTemplateUpdate,
)
from app.models.tenant.operations.unit_status_log import (
    UnitStatusLog,
    UnitStatusLogCreate,
    UnitStatusLogRead,
    UnitStatusLogUpdate,
)
from app.models.tenant.operations.work_order import (
    WorkOrder,
    WorkOrderCreate,
    WorkOrderRead,
    WorkOrderUpdate,
)

__all__ = [
    "TaskTemplate",
    "TaskTemplateCreate",
    "TaskTemplateRead",
    "TaskTemplateUpdate",
    "Task",
    "TaskCreate",
    "TaskRead",
    "TaskUpdate",
    "UnitStatusLog",
    "UnitStatusLogCreate",
    "UnitStatusLogRead",
    "UnitStatusLogUpdate",
    "Asset",
    "AssetCreate",
    "AssetRead",
    "AssetUpdate",
    "WorkOrder",
    "WorkOrderCreate",
    "WorkOrderRead",
    "WorkOrderUpdate",
    "PreventiveSchedule",
    "PreventiveScheduleCreate",
    "PreventiveScheduleRead",
    "PreventiveScheduleUpdate",
]
