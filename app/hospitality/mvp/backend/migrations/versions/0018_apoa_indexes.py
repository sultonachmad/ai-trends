"""APOA: find open and recent stays, and reports by guest or document

Revision ID: 0018
Revises: 0017
Create Date: 2026-11-26 12:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0018"
down_revision: str | Sequence[str] | None = "0017"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    # The APOA list and the front desk banner read in-house and recent checked-out stays.
    op.create_index(
        "ix_reservation_stay_open",
        "reservation",
        ["tenant_id", "property_id", "status", "departure_date"],
        postgresql_where=sa.text("status IN ('in_house', 'checked_out')"),
    )
    # Deleting a guest or an ID document checks these foreign keys.
    op.create_index("ix_foreignguestreport_guest", "foreignguestreport", ["tenant_id", "guest_id"])
    op.create_index(
        "ix_foreignguestreport_document",
        "foreignguestreport",
        ["tenant_id", "guest_document_id"],
        postgresql_where=sa.text("guest_document_id IS NOT NULL"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_foreignguestreport_document", table_name="foreignguestreport")
    op.drop_index("ix_foreignguestreport_guest", table_name="foreignguestreport")
    op.drop_index("ix_reservation_stay_open", table_name="reservation")
