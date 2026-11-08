"""PlanModule entity — table ``planmodule``.

Control-plane database, Control plane.

Subscription plans and the modules and limits they include.

Mirrors .ttest/contexts/schema-control-plane.sql; the Alembic migration creates the table.
"""

from typing import Any
from uuid import UUID

from sqlalchemy import ForeignKeyConstraint, Text, Uuid, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel

from app.crud.base_model import MIGRATION_ONLY


class PlanModule(SQLModel, table=True):
    """Subscription plans and the modules and limits they include."""

    __table_args__ = (
        ForeignKeyConstraint(
            ["plan_id"], ["plan.id"], name="planmodule_plan_id_fkey", ondelete="CASCADE"
        ),
        ForeignKeyConstraint(["module_code"], ["module.code"], name="planmodule_module_code_fkey"),
        MIGRATION_ONLY,
    )

    plan_id: UUID = Field(primary_key=True, sa_type=Uuid)
    module_code: str = Field(primary_key=True, sa_type=Text)
    limits: dict[str, Any] = Field(
        default_factory=dict,
        sa_type=JSONB,
        sa_column_kwargs={"server_default": text("'{}'::jsonb")},
        description='e.g. {"max_units":30,"ai_budget_idr":150000}',
    )


class PlanModuleCreate(SQLModel):
    """Fields accepted when creating a PlanModule."""

    plan_id: UUID
    module_code: str
    limits: dict[str, Any] = Field(default_factory=dict)


class PlanModuleUpdate(SQLModel):
    """Fields accepted when patching a PlanModule (all optional)."""

    limits: dict[str, Any] | None = None


class PlanModuleRead(SQLModel):
    """Fields returned when reading a PlanModule."""

    plan_id: UUID
    module_code: str
    limits: dict[str, Any]
