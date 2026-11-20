"""transfer proofs: link, guest, expected amount, review trail; document purge stamp

Revision ID: 0006
Revises: 0005
Create Date: 2026-11-20 00:00:00.000000

* ``transferproof`` gains what a person needs to review a "bukti transfer": the pay
  link, guest and conversation it belongs to, the amount staff expect, what it was
  for, the rejection reason, the first of two approvers (above the threshold), an
  earlier proof with the same image, and when the guest agreed to the storage notice.
* ``document.purged_at`` records that the stored file was deleted after its retention
  period; the row itself is kept.
* Indexes for the review queue, proofs of a link, and duplicate-image look-up.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: str | Sequence[str] | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# column -> referenced table, for the tenant-safe foreign keys added below
PROOF_REFERENCES = {
    "payment_link_id": "paymentlink",
    "guest_id": "guest",
    "conversation_id": "conversation",
    "duplicate_of_proof_id": "transferproof",
}


def upgrade() -> None:
    """Upgrade schema."""
    for column in PROOF_REFERENCES:
        op.add_column("transferproof", sa.Column(column, sa.Uuid(), nullable=True))
    op.add_column(
        "transferproof", sa.Column("amount", sa.Numeric(precision=18, scale=2), nullable=True)
    )
    for column in ("description", "rejection_reason", "first_approved_by"):
        op.add_column("transferproof", sa.Column(column, sa.Text(), nullable=True))
    for column in ("first_approved_at", "consent_at"):
        op.add_column("transferproof", sa.Column(column, sa.DateTime(timezone=True), nullable=True))
    for column, table in PROOF_REFERENCES.items():
        op.create_foreign_key(
            f"transferproof_tenant_id_{column}_fkey",
            "transferproof",
            table,
            ["tenant_id", column],
            ["tenant_id", "id"],
            ondelete=f"SET NULL ({column})",
        )
    op.create_check_constraint(
        "transferproof_amount_check",
        "transferproof",
        "((amount IS NULL) OR (amount > (0)::numeric))",
    )
    op.create_index(
        "ix_transferproof_queue",
        "transferproof",
        ["tenant_id", "property_id", "match_status", sa.literal_column("created_at DESC")],
    )
    op.create_index(
        "ix_transferproof_link",
        "transferproof",
        ["tenant_id", "payment_link_id"],
        postgresql_where=sa.text("payment_link_id IS NOT NULL"),
    )

    op.add_column("document", sa.Column("purged_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index(
        "ix_document_sha256",
        "document",
        ["tenant_id", "sha256"],
        postgresql_where=sa.text("sha256 IS NOT NULL"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_document_sha256", table_name="document")
    op.drop_column("document", "purged_at")
    op.drop_index("ix_transferproof_link", table_name="transferproof")
    op.drop_index("ix_transferproof_queue", table_name="transferproof")
    op.drop_constraint("transferproof_amount_check", "transferproof")
    for column in PROOF_REFERENCES:
        op.drop_constraint(
            f"transferproof_tenant_id_{column}_fkey", "transferproof", type_="foreignkey"
        )
    for column in (
        "consent_at",
        "first_approved_at",
        "first_approved_by",
        "rejection_reason",
        "description",
        "amount",
        *reversed(PROOF_REFERENCES),
    ):
        op.drop_column("transferproof", column)
