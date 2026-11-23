"""direct booking page: page names, guest links, payment-link origin

Revision ID: 0013
Revises: 0012
Create Date: 2026-11-23 12:00:00.000000

* ``bookingpage`` — a property's public page: a short name unique across the product.
* ``guestbookinglink`` — the guest's private link to a booking. Its own small table, so
  the owner-only lookup policy never has to cover ``reservation``.
* ``paymentlink.origin`` — ``booking_page`` deposits do not count toward the plan's
  monthly link limit.
* ``resolve_booking_page`` / ``resolve_guest_booking`` — the only things an unscoped
  ``app_rw`` session can ask; each returns one tenant id or NULL.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0013"
down_revision: str | Sequence[str] | None = "0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

APP_ROLE = "app_rw"
PAGE = "bookingpage"
GUEST_LINK = "guestbookinglink"
SLUG_CHECK = "slug ~ '^[a-z0-9][a-z0-9-]{1,38}[a-z0-9]$'"

RESOLVE_PAGE = """
CREATE FUNCTION resolve_booking_page(page_slug text) RETURNS uuid
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public, pg_temp
AS $$
  SELECT tenant_id FROM public.bookingpage WHERE slug = page_slug AND is_published
$$
"""

RESOLVE_GUEST = """
CREATE FUNCTION resolve_guest_booking(link_token_hash text) RETURNS uuid
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public, pg_temp
AS $$
  SELECT tenant_id FROM public.guestbookinglink WHERE token_hash = link_token_hash
$$
"""


def _secure(table: str) -> None:
    op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
    op.execute(
        f"CREATE POLICY tenant_isolation ON {table} "
        "USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid) "
        "WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)"
    )
    op.execute(f"CREATE POLICY {table}_lookup ON {table} FOR SELECT TO CURRENT_USER USING (true)")
    op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON {table} TO {APP_ROLE}")


def _timestamp(name: str) -> sa.Column:
    return sa.Column(
        name, sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
    )


def _create_tables() -> None:
    op.create_table(
        PAGE,
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        _timestamp("created_at"),
        _timestamp("updated_at"),
        sa.Column("created_by", sa.Text(), nullable=True),
        sa.Column("updated_by", sa.Text(), nullable=True),
        sa.Column("property_id", sa.Uuid(), nullable=False),
        sa.Column("slug", sa.Text(), nullable=False),
        sa.Column("is_published", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.CheckConstraint(SLUG_CHECK, name=f"{PAGE}_slug_check"),
        sa.ForeignKeyConstraint(
            ["tenant_id", "property_id"],
            ["property.tenant_id", "property.id"],
            name=f"{PAGE}_tenant_id_property_id_fkey",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=f"{PAGE}_pkey"),
        sa.UniqueConstraint("tenant_id", "id", name=f"{PAGE}_tenant_id_id_key"),
        sa.UniqueConstraint("tenant_id", "property_id", name=f"{PAGE}_property_key"),
        sa.UniqueConstraint("slug", name=f"{PAGE}_slug_key"),
    )
    op.create_table(
        GUEST_LINK,
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("reservation_id", sa.Uuid(), nullable=False),
        sa.Column("token_hash", sa.Text(), nullable=False),
        sa.Column("token_seed", sa.Text(), nullable=False),
        _timestamp("created_at"),
        sa.ForeignKeyConstraint(
            ["tenant_id", "reservation_id"],
            ["reservation.tenant_id", "reservation.id"],
            name=f"{GUEST_LINK}_tenant_id_reservation_id_fkey",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=f"{GUEST_LINK}_pkey"),
        sa.UniqueConstraint("tenant_id", "id", name=f"{GUEST_LINK}_tenant_id_id_key"),
        sa.UniqueConstraint("tenant_id", "reservation_id", name=f"{GUEST_LINK}_reservation_key"),
        sa.UniqueConstraint("token_hash", name=f"{GUEST_LINK}_token_hash_key"),
    )


def upgrade() -> None:
    """Upgrade schema."""
    _create_tables()
    _secure(PAGE)
    _secure(GUEST_LINK)
    op.add_column(
        "paymentlink",
        sa.Column("origin", sa.Text(), server_default=sa.text("'staff'"), nullable=False),
    )
    op.create_check_constraint(
        "paymentlink_origin_check", "paymentlink", "origin IN ('staff', 'booking_page')"
    )
    op.create_index(
        "ix_reservation_holds",
        "reservation",
        ["tenant_id", "property_id", "option_expires_at"],
        postgresql_where=sa.text("status = 'tentative'"),
    )
    op.create_index(
        "ix_reservation_confirmation",
        "reservation",
        ["tenant_id"],
        postgresql_where=sa.text(
            "(source_detail -> 'confirmation' ->> 'status') IN ('pending', 'sending')"
        ),
    )
    for statement, name in (
        (RESOLVE_PAGE, "resolve_booking_page"),
        (RESOLVE_GUEST, "resolve_guest_booking"),
    ):
        op.execute(statement)
        op.execute(f"REVOKE ALL ON FUNCTION {name}(text) FROM PUBLIC")
        op.execute(f"GRANT EXECUTE ON FUNCTION {name}(text) TO {APP_ROLE}")


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("DROP FUNCTION resolve_guest_booking(text)")
    op.execute("DROP FUNCTION resolve_booking_page(text)")
    op.execute("DROP INDEX IF EXISTS ix_reservation_confirmation")
    op.drop_index("ix_reservation_holds", table_name="reservation")
    op.drop_constraint("paymentlink_origin_check", "paymentlink", type_="check")
    op.drop_column("paymentlink", "origin")
    op.drop_table(GUEST_LINK)
    op.drop_table(PAGE)
