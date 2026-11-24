"""guest IDs: one document per guest and type, and indexes for reads and retention

Revision ID: 0017
Revises: 0016
Create Date: 2026-11-24 17:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0017"
down_revision: str | Sequence[str] | None = "0016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    # A corrected or renewed document replaces the old one, so a wrong number never lingers.
    op.create_index(
        "ux_guestdocument_guest_type",
        "guestdocument",
        ["tenant_id", "guest_id", "doc_type"],
        unique=True,
    )
    op.create_index(
        "ix_guestdocument_scan",
        "guestdocument",
        ["tenant_id", "scan_document_id"],
        postgresql_where=sa.text("scan_document_id IS NOT NULL"),
    )
    op.create_index(
        "ix_guestdocument_number_due",
        "guestdocument",
        ["tenant_id", "retention_until"],
        postgresql_where=sa.text("doc_number_encrypted IS NOT NULL"),
    )
    op.create_index(
        "ix_document_identity_due",
        "document",
        ["tenant_id", "retention_until"],
        postgresql_where=sa.text("kind = 'identity_scan' AND purged_at IS NULL"),
    )
    op.create_index("ix_reservationguest_guest", "reservationguest", ["tenant_id", "guest_id"])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_reservationguest_guest", table_name="reservationguest")
    op.drop_index("ix_document_identity_due", table_name="document")
    op.drop_index("ix_guestdocument_number_due", table_name="guestdocument")
    op.drop_index("ix_guestdocument_scan", table_name="guestdocument")
    op.drop_index("ux_guestdocument_guest_type", table_name="guestdocument")
