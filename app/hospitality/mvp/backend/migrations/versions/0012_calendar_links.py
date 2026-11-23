"""calendar links: iCal feeds per room type, imported busy dates, public token lookup

Revision ID: 0012
Revises: 0011
Create Date: 2026-11-23 00:00:00.000000

* ``icalfeed`` now belongs to a room type (rooms are sold by type, units are not
  assigned), and ``link_id`` pairs a site's import and export rows.
* ``icalblock`` — one row per (imported calendar, busy date), so a later import
  releases exactly what the site removed.
* ``resolve_ical_feed(token_hash)`` lets the public ``.ics`` route find a feed's tenant.
  Like ``resolve_payment_link`` it is the only thing an unscoped ``app_rw`` can ask.
* ``channelsimulatorlisting.calendar`` — a test calendar (development and test only).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0012"
down_revision: str | Sequence[str] | None = "0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

APP_ROLE = "app_rw"
BLOCK = "icalblock"
LOOKUP_POLICY = "ical_feed_lookup"

RLS_POLICY = f"""
CREATE POLICY tenant_isolation ON {BLOCK}
  USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
  WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
"""

RESOLVE_FUNCTION = """
CREATE FUNCTION resolve_ical_feed(feed_token_hash text) RETURNS uuid
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public, pg_temp
AS $$
  SELECT tenant_id FROM public.icalfeed
  WHERE export_token_hash = feed_token_hash AND is_active
$$
"""


def _alter_feed() -> None:
    for name in ("property_id", "unit_type_id"):
        op.add_column("icalfeed", sa.Column(name, sa.Uuid(), nullable=True))
    op.execute(
        "UPDATE icalfeed f SET property_id = u.property_id, unit_type_id = u.unit_type_id "
        "FROM unit u WHERE u.tenant_id = f.tenant_id AND u.id = f.unit_id"
    )
    op.alter_column("icalfeed", "property_id", nullable=False)
    op.alter_column("icalfeed", "unit_type_id", nullable=False)
    op.alter_column("icalfeed", "unit_id", nullable=True)
    op.add_column(
        "icalfeed",
        sa.Column(
            "link_id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False
        ),
    )
    op.alter_column("icalfeed", "link_id", server_default=None)
    op.add_column(
        "icalfeed", sa.Column("label", sa.Text(), server_default=sa.text("''"), nullable=False)
    )
    for name in ("last_attempt_at", "failing_since"):
        op.add_column("icalfeed", sa.Column(name, sa.DateTime(timezone=True), nullable=True))
    op.create_foreign_key(
        "icalfeed_tenant_id_property_id_fkey",
        "icalfeed",
        "property",
        ["tenant_id", "property_id"],
        ["tenant_id", "id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "icalfeed_tenant_id_unit_type_id_fkey",
        "icalfeed",
        "unittype",
        ["tenant_id", "unit_type_id"],
        ["tenant_id", "id"],
        ondelete="CASCADE",
    )
    op.create_unique_constraint(
        "icalfeed_link_direction_key", "icalfeed", ["tenant_id", "link_id", "direction"]
    )
    op.create_index(
        "ux_icalfeed_export_token",
        "icalfeed",
        ["export_token_hash"],
        unique=True,
        postgresql_where=sa.text("export_token_hash IS NOT NULL"),
    )


def _create_blocks() -> None:
    op.create_table(
        BLOCK,
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("feed_id", sa.Uuid(), nullable=False),
        sa.Column("unit_type_id", sa.Uuid(), nullable=False),
        sa.Column("stay_date", sa.Date(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "feed_id"],
            ["icalfeed.tenant_id", "icalfeed.id"],
            name=f"{BLOCK}_tenant_id_feed_id_fkey",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "unit_type_id"],
            ["unittype.tenant_id", "unittype.id"],
            name=f"{BLOCK}_tenant_id_unit_type_id_fkey",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=f"{BLOCK}_pkey"),
        sa.UniqueConstraint("tenant_id", "id", name=f"{BLOCK}_tenant_id_id_key"),
        sa.UniqueConstraint("tenant_id", "feed_id", "stay_date", name=f"{BLOCK}_feed_date_key"),
    )
    op.create_index(f"ix_{BLOCK}_room_date", BLOCK, ["tenant_id", "unit_type_id", "stay_date"])
    op.execute(f"ALTER TABLE {BLOCK} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {BLOCK} FORCE ROW LEVEL SECURITY")
    op.execute(RLS_POLICY)
    op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON {BLOCK} TO {APP_ROLE}")


def upgrade() -> None:
    """Upgrade schema."""
    _alter_feed()
    _create_blocks()
    op.add_column(
        "channelsimulatorlisting",
        sa.Column(
            "calendar",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
    )
    op.execute(RESOLVE_FUNCTION)
    op.execute("REVOKE ALL ON FUNCTION resolve_ical_feed(text) FROM PUBLIC")
    op.execute(f"GRANT EXECUTE ON FUNCTION resolve_ical_feed(text) TO {APP_ROLE}")
    # FORCE RLS binds the table owner too: let the owner, and only the owner, do the lookup.
    op.execute(f"CREATE POLICY {LOOKUP_POLICY} ON icalfeed FOR SELECT TO CURRENT_USER USING (true)")


def downgrade() -> None:
    """Downgrade schema. Calendar links are per room type, so they cannot be kept."""
    op.execute(f"DROP POLICY {LOOKUP_POLICY} ON icalfeed")
    op.execute("DROP FUNCTION resolve_ical_feed(text)")
    op.drop_column("channelsimulatorlisting", "calendar")
    op.execute(
        "UPDATE inventoryday d SET blocked = GREATEST(d.blocked - b.n, 0) FROM "
        "(SELECT tenant_id, unit_type_id, stay_date, count(*) AS n FROM icalblock "
        "GROUP BY 1, 2, 3) b WHERE b.tenant_id = d.tenant_id "
        "AND b.unit_type_id = d.unit_type_id AND b.stay_date = d.stay_date"
    )
    op.drop_table(BLOCK)
    op.execute("DELETE FROM icalfeed WHERE unit_id IS NULL")
    op.drop_index("ux_icalfeed_export_token", table_name="icalfeed")
    op.drop_constraint("icalfeed_link_direction_key", "icalfeed", type_="unique")
    op.drop_constraint("icalfeed_tenant_id_unit_type_id_fkey", "icalfeed", type_="foreignkey")
    op.drop_constraint("icalfeed_tenant_id_property_id_fkey", "icalfeed", type_="foreignkey")
    for name in ("failing_since", "last_attempt_at", "label", "link_id", "unit_type_id"):
        op.drop_column("icalfeed", name)
    op.drop_column("icalfeed", "property_id")
    op.alter_column("icalfeed", "unit_id", nullable=False)
