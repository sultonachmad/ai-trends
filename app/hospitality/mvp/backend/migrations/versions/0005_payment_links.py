"""payment links: conversation, guest, down-payment total; simulator gateway; public lookup

Revision ID: 0005
Revises: 0004
Create Date: 2026-11-20 00:00:00.000000

* ``paymentlink`` gains ``conversation_id`` and ``guest_id`` (who the link was sent
  to) and ``deposit_of_total`` (set when the link is a down payment of a larger total).
* ``paymentgatewayaccount.provider`` may be ``simulator`` (PRD: simulated first).
* ``resolve_payment_link(token_hash)`` lets the public pay page find which tenant a
  link belongs to. It is the ONLY thing an unscoped ``app_rw`` session can learn:
  the function runs with its owner's rights (SECURITY DEFINER), takes the exact
  SHA-256 fingerprint of a 256-bit token, and returns one tenant id or NULL.
  Everything after that runs tenant-scoped under the normal row-level security.
* ``payment.gateway_reference`` becomes unique per gateway account.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: str | Sequence[str] | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

APP_ROLE = "app_rw"
PROVIDERS_BEFORE = (
    "midtrans",
    "xendit",
    "doku",
    "faspay",
    "stripe",
    "adyen",
    "manual_bank",
    "other",
)
PROVIDERS_AFTER = (*PROVIDERS_BEFORE[:-1], "simulator", "other")

RESOLVE_FUNCTION = """
CREATE FUNCTION resolve_payment_link(link_token_hash text) RETURNS uuid
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public, pg_temp
AS $$
  SELECT tenant_id FROM public.paymentlink WHERE token_hash = link_token_hash
$$
"""

# paymentlink has FORCE ROW LEVEL SECURITY, which binds the table owner too. The lookup
# function runs as its owner with no tenant set, so without this policy an owner that
# is not a superuser (and has no BYPASSRLS) would find nothing and every pay link
# would answer "not found". The policy lets the owner — and only the owner — read.
LOOKUP_POLICY = "payment_link_lookup"


def _provider_check(values: tuple[str, ...]) -> str:
    return "provider IN (" + ", ".join(f"'{v}'" for v in values) + ")"


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("paymentlink", sa.Column("conversation_id", sa.Uuid(), nullable=True))
    op.add_column("paymentlink", sa.Column("guest_id", sa.Uuid(), nullable=True))
    op.add_column(
        "paymentlink",
        sa.Column("deposit_of_total", sa.Numeric(precision=18, scale=2), nullable=True),
    )
    op.create_foreign_key(
        "paymentlink_tenant_id_conversation_id_fkey",
        "paymentlink",
        "conversation",
        ["tenant_id", "conversation_id"],
        ["tenant_id", "id"],
        ondelete="SET NULL (conversation_id)",
    )
    op.create_foreign_key(
        "paymentlink_tenant_id_guest_id_fkey",
        "paymentlink",
        "guest",
        ["tenant_id", "guest_id"],
        ["tenant_id", "id"],
        ondelete="SET NULL (guest_id)",
    )
    op.create_check_constraint(
        "paymentlink_deposit_of_total_check",
        "paymentlink",
        "((deposit_of_total IS NULL) OR (deposit_of_total >= amount))",
    )
    op.create_index(
        "ix_paymentlink_list",
        "paymentlink",
        ["tenant_id", "property_id", sa.literal_column("created_at DESC")],
    )
    op.create_index(
        "ix_paymentlink_conversation",
        "paymentlink",
        ["tenant_id", "conversation_id"],
        postgresql_where=sa.text("conversation_id IS NOT NULL"),
    )

    op.drop_constraint("paymentgatewayaccount_provider_check", "paymentgatewayaccount")
    op.create_check_constraint(
        "paymentgatewayaccount_provider_check",
        "paymentgatewayaccount",
        _provider_check(PROVIDERS_AFTER),
    )

    op.execute(
        f"CREATE POLICY {LOOKUP_POLICY} ON paymentlink FOR SELECT TO CURRENT_USER USING (true)"
    )
    # A gateway reference identifies one payment: notifications are matched on it.
    op.create_index(
        "ux_payment_gateway_ref",
        "payment",
        ["tenant_id", "gateway_account_id", "gateway_reference"],
        unique=True,
        postgresql_where=sa.text("gateway_reference IS NOT NULL"),
    )
    op.execute(RESOLVE_FUNCTION)
    op.execute("REVOKE ALL ON FUNCTION resolve_payment_link(text) FROM PUBLIC")
    op.execute(f"GRANT EXECUTE ON FUNCTION resolve_payment_link(text) TO {APP_ROLE}")


def downgrade() -> None:
    """Downgrade schema.

    Fails on purpose while a gateway account still uses the ``simulator`` provider.
    """
    op.execute("DROP FUNCTION IF EXISTS resolve_payment_link(text)")
    op.drop_index("ux_payment_gateway_ref", table_name="payment")
    op.execute(f"DROP POLICY IF EXISTS {LOOKUP_POLICY} ON paymentlink")
    op.drop_constraint("paymentgatewayaccount_provider_check", "paymentgatewayaccount")
    op.create_check_constraint(
        "paymentgatewayaccount_provider_check",
        "paymentgatewayaccount",
        _provider_check(PROVIDERS_BEFORE),
    )
    op.drop_index("ix_paymentlink_conversation", table_name="paymentlink")
    op.drop_index("ix_paymentlink_list", table_name="paymentlink")
    op.drop_constraint("paymentlink_deposit_of_total_check", "paymentlink")
    op.drop_constraint("paymentlink_tenant_id_guest_id_fkey", "paymentlink", type_="foreignkey")
    op.drop_constraint(
        "paymentlink_tenant_id_conversation_id_fkey", "paymentlink", type_="foreignkey"
    )
    op.drop_column("paymentlink", "deposit_of_total")
    op.drop_column("paymentlink", "guest_id")
    op.drop_column("paymentlink", "conversation_id")
