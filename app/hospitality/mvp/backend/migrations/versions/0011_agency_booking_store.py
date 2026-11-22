"""the simulated agency's booking store

Revision ID: 0011
Revises: 0010
Create Date: 2026-11-22 00:00:00.000000

``channelsimulatorlisting.bookings`` holds the agency's booking events (new/modify/
cancel with versions) as the poller reports them — development and test only. Kept out
of 0010, which had already shipped.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0011"
down_revision: str | Sequence[str] | None = "0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "channelsimulatorlisting",
        sa.Column(
            "bookings",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("ALTER TABLE channelsimulatorlisting DROP COLUMN IF EXISTS bookings")
