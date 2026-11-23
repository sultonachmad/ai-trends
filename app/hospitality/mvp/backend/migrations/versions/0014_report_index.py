"""channel report: read nightly revenue by date

Revision ID: 0014
Revises: 0013
Create Date: 2026-11-23 18:00:00.000000
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0014"
down_revision: str | Sequence[str] | None = "0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_index(
        "ix_reservationdailyrate_date", "reservationdailyrate", ["tenant_id", "stay_date"]
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_reservationdailyrate_date", table_name="reservationdailyrate")
