"""bookings: a free-text note on why a booking was cancelled

Revision ID: 0008
Revises: 0007
Create Date: 2026-11-20 00:00:00.000000

``reservation.cancel_reason_id`` points at a coded reason list that staff do not
maintain yet. ``cancel_note`` holds what they type when cancelling.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0008"
down_revision: str | Sequence[str] | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("reservation", sa.Column("cancel_note", sa.Text(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("reservation", "cancel_note")
