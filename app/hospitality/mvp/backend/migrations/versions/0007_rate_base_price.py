"""rate plans: a base nightly price per room type

Revision ID: 0007
Revises: 0006
Create Date: 2026-11-20 00:00:00.000000

``rateplanunittype`` says which room types a rate plan sells. It now also carries the
normal nightly price for that pair. The calendar (``ratedaily``) stores only the dates
whose price differs; a date without a row there is sold at this base price.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007"
down_revision: str | Sequence[str] | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLE = "rateplanunittype"
CHECK = "rateplanunittype_base_amount_check"


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        TABLE,
        sa.Column(
            "base_amount",
            sa.Numeric(precision=18, scale=2),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )
    op.create_check_constraint(CHECK, TABLE, "(base_amount >= (0)::numeric)")


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint(CHECK, TABLE, type_="check")
    op.drop_column(TABLE, "base_amount")
