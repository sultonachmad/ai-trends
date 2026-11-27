"""Maintenance: repair requests from staff and housekeeping, rooms off sale

Revision ID: 0021
Revises: 0020
Create Date: 2026-11-27 10:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0021"
down_revision: str | Sequence[str] | None = "0020"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    # A place that is not a room ("pool", "lobby"), the note of the last step (why it waits,
    # why it was cancelled, what was done), an outside repairer's name, and the cleaning
    # task a housekeeper reported it from.
    op.add_column("workorder", sa.Column("place", sa.Text(), nullable=True))
    op.add_column("workorder", sa.Column("status_note", sa.Text(), nullable=True))
    op.add_column("workorder", sa.Column("vendor_name", sa.Text(), nullable=True))
    op.add_column("workorder", sa.Column("task_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        "workorder_tenant_id_task_id_fkey",
        "workorder",
        "task",
        ["tenant_id", "task_id"],
        ["tenant_id", "id"],
        ondelete="SET NULL (task_id)",
    )
    # Earlier requests (if any) without a room keep their title as the place.
    op.execute("UPDATE workorder SET place = title WHERE unit_id IS NULL AND place IS NULL")
    op.create_check_constraint(
        "workorder_where_check", "workorder", "unit_id IS NOT NULL OR place IS NOT NULL"
    )
    # Requests by room (the room's history, "already reported"), and the task link.
    op.create_index(
        "ix_workorder_unit",
        "workorder",
        ["tenant_id", "unit_id", "created_at"],
        postgresql_where=sa.text("unit_id IS NOT NULL"),
    )
    op.create_index(
        "ux_workorder_task",
        "workorder",
        ["tenant_id", "task_id"],
        unique=True,
        postgresql_where=sa.text("task_id IS NOT NULL"),
    )
    # The repairs list: live requests and the last two weeks', newest first.
    op.create_index("ix_workorder_recent", "workorder", ["tenant_id", "property_id", "created_at"])
    # Blocks of a request (back on sale when it is fixed).
    op.create_index(
        "ix_unitblock_work_order",
        "unitblock",
        ["tenant_id", "work_order_id"],
        postgresql_where=sa.text("work_order_id IS NOT NULL"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_unitblock_work_order", table_name="unitblock")
    op.drop_index("ix_workorder_recent", table_name="workorder")
    op.drop_index("ux_workorder_task", table_name="workorder")
    op.drop_index("ix_workorder_unit", table_name="workorder")
    op.drop_constraint("workorder_where_check", "workorder", type_="check")
    op.drop_constraint("workorder_tenant_id_task_id_fkey", "workorder", type_="foreignkey")
    for column in ("task_id", "vendor_name", "status_note", "place"):
        op.drop_column("workorder", column)
