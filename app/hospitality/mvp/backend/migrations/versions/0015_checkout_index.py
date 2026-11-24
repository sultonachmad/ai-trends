"""front desk: find today's check-outs without scanning every stay

Revision ID: 0015
Revises: 0014
Create Date: 2026-11-24 12:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0015"
down_revision: str | Sequence[str] | None = "0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_index(
        "ix_reservationunit_checked_out",
        "reservationunit",
        ["tenant_id", "property_id", "checked_out_at"],
        postgresql_where=sa.text("checked_out_at IS NOT NULL"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_reservationunit_checked_out", table_name="reservationunit")
