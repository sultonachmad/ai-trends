"""channel updates out: the pending-ARI queue and retry scheduling

Revision ID: 0010
Revises: 0009
Create Date: 2026-11-21 00:00:00.000000

* ``channelariupdate`` — one row per (connection, room type, date) whose availability,
  price or restrictions must (again) reach the channel. The unique key makes repeated
  changes collapse; the background sender deletes rows as the channel acknowledges.
* ``channelconnection.next_push_at`` — a failed push is not retried before this time
  (backoff). ``failing_since`` — set after repeated failures, cleared by a success.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from alembic import op

revision: str = "0010"
down_revision: str | Sequence[str] | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

APP_ROLE = "app_rw"
QUEUE = "channelariupdate"

RLS_POLICY = f"""
CREATE POLICY tenant_isolation ON {QUEUE}
  USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
  WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
"""


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        QUEUE,
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("property_id", sa.Uuid(), nullable=False),
        sa.Column("channel_connection_id", sa.Uuid(), nullable=False),
        sa.Column("unit_type_id", sa.Uuid(), nullable=False),
        sa.Column("stay_date", sa.Date(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "property_id"],
            ["property.tenant_id", "property.id"],
            name=f"{QUEUE}_tenant_id_property_id_fkey",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "channel_connection_id"],
            ["channelconnection.tenant_id", "channelconnection.id"],
            name=f"{QUEUE}_tenant_id_channel_connection_id_fkey",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "unit_type_id"],
            ["unittype.tenant_id", "unittype.id"],
            name=f"{QUEUE}_tenant_id_unit_type_id_fkey",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=f"{QUEUE}_pkey"),
        sa.UniqueConstraint("tenant_id", "id", name=f"{QUEUE}_tenant_id_id_key"),
        sa.UniqueConstraint(
            "tenant_id",
            "channel_connection_id",
            "unit_type_id",
            "stay_date",
            name=f"{QUEUE}_due_key",
        ),
    )
    op.create_index(
        f"ix_{QUEUE}_due",
        QUEUE,
        ["tenant_id", "channel_connection_id", "stay_date"],
    )
    op.execute(f"ALTER TABLE {QUEUE} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {QUEUE} FORCE ROW LEVEL SECURITY")
    op.execute(RLS_POLICY)
    op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON {QUEUE} TO {APP_ROLE}")

    op.add_column(
        "channelconnection", sa.Column("next_push_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column(
        "channelconnection", sa.Column("failing_since", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column(
        "channelsimulatorlisting",
        sa.Column(
            "ari",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
    )
    op.add_column(
        "channelsimulatorlisting",
        sa.Column("fail_next", sa.Integer(), server_default=sa.text("0"), nullable=False),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("channelconnection", "failing_since")
    op.drop_column("channelconnection", "next_push_at")
    # the listing columns exist only in the final revision of this migration; dropping
    # them fails on databases that applied the earlier revision, so guard with a check
    op.execute("ALTER TABLE channelsimulatorlisting DROP COLUMN IF EXISTS fail_next")
    op.execute("ALTER TABLE channelsimulatorlisting DROP COLUMN IF EXISTS ari")
    op.drop_table(QUEUE)
