"""Housekeeping on phone: problems on tasks, one open task per room and kind a day, invitations

Revision ID: 0020
Revises: 0019
Create Date: 2026-11-26 18:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0020"
down_revision: str | Sequence[str] | None = "0019"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PROBLEM_KINDS = "('dnd', 'refused', 'repair', 'empty', 'other')"
# One live cleaning task per room, kind and day. Finished tasks do not count, so a room
# re-let and left again the same day gets a new clean.
LIVE_CLEAN = (
    "unit_id IS NOT NULL AND task_kind IN ('departure_clean', 'stayover_clean') "
    "AND status IN ('pending', 'assigned', 'in_progress', 'paused', 'failed_inspection')"
)
OPEN_INVITE = "accepted_at IS NULL AND revoked_at IS NULL"


def _task_problem_columns() -> None:
    op.add_column("task", sa.Column("problem_kind", sa.Text(), nullable=True))
    op.add_column("task", sa.Column("problem_note", sa.Text(), nullable=True))
    op.add_column("task", sa.Column("problem_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("task", sa.Column("problem_by", sa.Text(), nullable=True))
    op.add_column(
        "task", sa.Column("problem_cleared_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column("task", sa.Column("problem_cleared_by", sa.Text(), nullable=True))
    op.create_check_constraint(
        "task_problem_kind_check",
        "task",
        f"problem_kind IS NULL OR problem_kind IN {PROBLEM_KINDS}",
    )
    op.create_check_constraint(
        "task_problem_at_check",
        "task",
        "(problem_kind IS NULL) = (problem_at IS NULL)",
    )


def upgrade() -> None:
    """Upgrade schema."""
    _task_problem_columns()
    # Tasks are made from the rooms each time the board is read: this keeps it to one
    # live clean per room, kind and day even when two phones read at the same moment.
    op.create_index(
        "ux_task_unit_day_kind",
        "task",
        ["tenant_id", "unit_id", "scheduled_for", "task_kind"],
        unique=True,
        postgresql_where=sa.text(LIVE_CLEAN),
    )
    # The front desk lists problems not yet dealt with.
    op.create_index(
        "ix_task_open_problem",
        "task",
        ["tenant_id", "property_id", "problem_at"],
        postgresql_where=sa.text("problem_kind IS NOT NULL AND problem_cleared_at IS NULL"),
    )
    # Staff join links: the name to give the new staff member, and the owner's list.
    op.add_column("tenantinvitation", sa.Column("display_name", sa.Text(), nullable=True))
    op.create_index(
        "ix_tenantinvitation_tenant", "tenantinvitation", ["tenant_id", "created_at"]
    )
    # One open join link per email and workspace, even when two are made at once.
    op.create_index(
        "ux_tenantinvitation_open_email",
        "tenantinvitation",
        ["tenant_id", sa.text("lower(email)")],
        unique=True,
        postgresql_where=sa.text(OPEN_INVITE),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ux_tenantinvitation_open_email", table_name="tenantinvitation")
    op.drop_index("ix_tenantinvitation_tenant", table_name="tenantinvitation")
    op.drop_column("tenantinvitation", "display_name")
    op.drop_index("ix_task_open_problem", table_name="task")
    op.drop_index("ux_task_unit_day_kind", table_name="task")
    op.drop_constraint("task_problem_at_check", "task", type_="check")
    op.drop_constraint("task_problem_kind_check", "task", type_="check")
    for column in (
        "problem_cleared_by",
        "problem_cleared_at",
        "problem_by",
        "problem_at",
        "problem_note",
        "problem_kind",
    ):
        op.drop_column("task", column)
