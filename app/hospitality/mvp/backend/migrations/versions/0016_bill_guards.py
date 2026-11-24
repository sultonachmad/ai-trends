"""guest bill: one guest bill per booking, one void per line, frozen receipts

Revision ID: 0016
Revises: 0015
Create Date: 2026-11-24 15:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0016"
down_revision: str | Sequence[str] | None = "0015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PROTECT_RECEIPT = """
CREATE OR REPLACE FUNCTION protect_issued_receipt() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
  IF OLD.status = 'issued' AND OLD.kind = 'receipt'
     AND NEW.paid_amount IS DISTINCT FROM OLD.paid_amount THEN
    RAISE EXCEPTION 'issued receipt % is immutable', OLD.number
      USING ERRCODE = 'restrict_violation';
  END IF;
  RETURN NEW;
END $$
"""

PROTECT_LINE = """
CREATE OR REPLACE FUNCTION protect_issued_invoice_line() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM invoice
    WHERE invoice.tenant_id = OLD.tenant_id AND invoice.id = OLD.invoice_id
      AND invoice.status = 'issued'
  ) THEN
    RAISE EXCEPTION 'lines of an issued invoice are immutable'
      USING ERRCODE = 'restrict_violation';
  END IF;
  RETURN NEW;
END $$
"""


def upgrade() -> None:
    """Upgrade schema."""
    op.create_index(
        "ux_folio_guest_reservation",
        "folio",
        ["tenant_id", "reservation_id", "window_no"],
        unique=True,
        postgresql_where=sa.text("kind = 'guest' AND reservation_id IS NOT NULL"),
    )
    op.create_index(
        "ux_foliotransaction_reverses",
        "foliotransaction",
        ["tenant_id", "reverses_transaction_id"],
        unique=True,
        postgresql_where=sa.text("reverses_transaction_id IS NOT NULL"),
    )
    op.execute(PROTECT_RECEIPT)
    op.execute(
        "CREATE TRIGGER trg_receipt_protect BEFORE UPDATE ON invoice "
        "FOR EACH ROW EXECUTE FUNCTION protect_issued_receipt()"
    )
    op.execute(PROTECT_LINE)
    op.execute(
        "CREATE TRIGGER trg_invoiceline_protect BEFORE UPDATE ON invoiceline "
        "FOR EACH ROW EXECUTE FUNCTION protect_issued_invoice_line()"
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("DROP TRIGGER IF EXISTS trg_invoiceline_protect ON invoiceline")
    op.execute("DROP FUNCTION IF EXISTS protect_issued_invoice_line()")
    op.execute("DROP TRIGGER IF EXISTS trg_receipt_protect ON invoice")
    op.execute("DROP FUNCTION IF EXISTS protect_issued_receipt()")
    op.drop_index("ux_foliotransaction_reverses", table_name="foliotransaction")
    op.drop_index("ux_folio_guest_reservation", table_name="folio")
