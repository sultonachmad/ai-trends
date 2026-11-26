"""end of day: cash movements, one open drawer per person, payment indexes, reopening a day

Revision ID: 0019
Revises: 0018
Create Date: 2026-11-26 15:00:00.000000

A closed business day can no longer be deleted or rewritten. Only the reopen action
(a reason, recorded in the history) may open it again: it names the row in
`set_config('app.reopen_day', <row id>, true)` for its own transaction only. A closed
cash drawer can no longer be changed.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0019"
down_revision: str | Sequence[str] | None = "0018"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

GUARDED = """
CREATE OR REPLACE FUNCTION protect_closed_businessday() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
  IF OLD.status <> 'closed' THEN
    RETURN CASE WHEN TG_OP = 'DELETE' THEN OLD ELSE NEW END;
  END IF;
  -- A closed day is neither deleted nor rewritten. Only the reopen action, which names
  -- this very row in its own transaction, may set it back to open.
  IF TG_OP = 'DELETE' OR NEW.status = 'closed'
     OR coalesce(current_setting('app.reopen_day', true), '') <> OLD.id::text THEN
    RAISE EXCEPTION 'business date % is closed', OLD.business_date
      USING ERRCODE = 'restrict_violation';
  END IF;
  RETURN NEW;
END $$
"""

PROTECT_SHIFT = """
CREATE OR REPLACE FUNCTION protect_closed_cashiershift() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
  IF OLD.status <> 'open' THEN
    RAISE EXCEPTION 'cash drawer % is closed', OLD.id USING ERRCODE = 'restrict_violation';
  END IF;
  RETURN CASE WHEN TG_OP = 'DELETE' THEN OLD ELSE NEW END;
END $$
"""

APP_ROLE = "app_rw"
MOVES = "cashmovement"
RLS_POLICY = f"""
CREATE POLICY tenant_isolation ON {MOVES}
  USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
  WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
"""

ORIGINAL = """
CREATE OR REPLACE FUNCTION protect_closed_businessday() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
  IF OLD.status = 'closed' AND NEW.status <> 'closed' THEN
    RAISE EXCEPTION 'business date % is closed', OLD.business_date
      USING ERRCODE = 'restrict_violation';
  END IF;
  RETURN NEW;
END $$
"""


def _create_moves() -> None:
    """Refunds and paid-outs: money out that is not a booking payment. Never changed."""
    op.create_table(
        MOVES,
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("property_id", sa.Uuid(), nullable=False),
        sa.Column("cashier_shift_id", sa.Uuid(), nullable=True),
        sa.Column("reservation_id", sa.Uuid(), nullable=True),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("method", sa.Text(), nullable=False),
        sa.Column("amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("recorded_by", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "property_id"],
            ["property.tenant_id", "property.id"],
            name=f"{MOVES}_tenant_id_property_id_fkey",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "cashier_shift_id"],
            ["cashiershift.tenant_id", "cashiershift.id"],
            name=f"{MOVES}_tenant_id_cashier_shift_id_fkey",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "reservation_id"],
            ["reservation.tenant_id", "reservation.id"],
            name=f"{MOVES}_tenant_id_reservation_id_fkey",
        ),
        sa.CheckConstraint("kind IN ('refund', 'paid_out')", name=f"{MOVES}_kind_check"),
        sa.CheckConstraint(
            "method IN ('cash', 'bank_transfer', 'other')", name=f"{MOVES}_method_check"
        ),
        sa.CheckConstraint("amount > 0", name=f"{MOVES}_amount_check"),
        sa.PrimaryKeyConstraint("id", name=f"{MOVES}_pkey"),
        sa.UniqueConstraint("tenant_id", "id", name=f"{MOVES}_tenant_id_id_key"),
    )
    op.create_index(f"ix_{MOVES}_day", MOVES, ["tenant_id", "property_id", "occurred_at"])
    op.create_index(
        f"ix_{MOVES}_reservation",
        MOVES,
        ["tenant_id", "reservation_id"],
        postgresql_where=sa.text("reservation_id IS NOT NULL"),
    )
    op.create_index(
        f"ix_{MOVES}_shift",
        MOVES,
        ["tenant_id", "cashier_shift_id"],
        postgresql_where=sa.text("cashier_shift_id IS NOT NULL"),
    )
    op.execute(f"ALTER TABLE {MOVES} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {MOVES} FORCE ROW LEVEL SECURITY")
    op.execute(RLS_POLICY)
    op.execute(f"GRANT SELECT, INSERT ON {MOVES} TO {APP_ROLE}")
    op.execute(
        f"CREATE TRIGGER trg_{MOVES}_no_update BEFORE UPDATE ON {MOVES} "
        "FOR EACH ROW EXECUTE FUNCTION forbid_update()"
    )
    op.execute(
        f"CREATE TRIGGER trg_{MOVES}_no_delete BEFORE DELETE ON {MOVES} "
        "FOR EACH ROW EXECUTE FUNCTION forbid_delete()"
    )


def _protect() -> None:
    op.execute(GUARDED)
    op.execute(
        "CREATE TRIGGER trg_businessday_no_delete BEFORE DELETE ON businessday "
        "FOR EACH ROW EXECUTE FUNCTION protect_closed_businessday()"
    )
    op.execute(PROTECT_SHIFT)
    op.execute(
        "CREATE TRIGGER trg_cashiershift_protect BEFORE UPDATE OR DELETE ON cashiershift "
        "FOR EACH ROW EXECUTE FUNCTION protect_closed_cashiershift()"
    )


def _summary_indexes() -> None:
    """The day summary counts check-ins and cancellations by time."""
    op.create_index(
        "ix_reservationunit_checked_in",
        "reservationunit",
        ["tenant_id", "property_id", "checked_in_at"],
        postgresql_where=sa.text("checked_in_at IS NOT NULL"),
    )
    op.create_index(
        "ix_reservation_cancelled",
        "reservation",
        ["tenant_id", "property_id", "cancelled_at"],
        postgresql_where=sa.text("cancelled_at IS NOT NULL"),
    )


def upgrade() -> None:
    """Upgrade schema."""
    _protect()
    _create_moves()
    _summary_indexes()
    op.create_index(
        "ux_cashiershift_open",
        "cashiershift",
        ["tenant_id", "property_id", "staff_member_id"],
        unique=True,
        postgresql_where=sa.text("status = 'open'"),
    )
    op.create_index(
        "ix_cashiershift_day", "cashiershift", ["tenant_id", "property_id", "business_date"]
    )
    op.create_index(
        "ix_payment_shift",
        "payment",
        ["tenant_id", "cashier_shift_id"],
        postgresql_where=sa.text("cashier_shift_id IS NOT NULL"),
    )
    op.create_index("ix_payment_captured", "payment", ["tenant_id", "property_id", "captured_at"])


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("DROP INDEX IF EXISTS ix_reservation_cancelled")
    op.execute("DROP INDEX IF EXISTS ix_reservationunit_checked_in")
    op.execute("DROP TRIGGER IF EXISTS trg_cashiershift_protect ON cashiershift")
    op.execute("DROP FUNCTION IF EXISTS protect_closed_cashiershift()")
    op.execute("DROP TRIGGER IF EXISTS trg_businessday_no_delete ON businessday")
    op.execute(f"DROP TABLE IF EXISTS {MOVES}")
    op.drop_index("ix_payment_captured", table_name="payment")
    op.drop_index("ix_payment_shift", table_name="payment")
    op.drop_index("ix_cashiershift_day", table_name="cashiershift")
    op.drop_index("ux_cashiershift_open", table_name="cashiershift")
    op.execute(ORIGINAL)
