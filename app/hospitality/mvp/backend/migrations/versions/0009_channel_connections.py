"""channel connections: simulated agency, Free-plan channel limit, simulator listings

Revision ID: 0009
Revises: 0008
Create Date: 2026-11-20 00:00:00.000000

* ``channelcatalog`` gains the simulated agency that stands in for the agencies which
  need partner certification.
* The Free plan gets the channel manager with a limit of one connected channel, and so
  does every tenant already on that plan.
* ``channelsimulatorlisting`` holds the simulated agency's own listings (its property
  ID and its rooms and rates), one row per test listing. It is a tenant table like any
  other: same isolation policy, forced row-level security, same grants.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0009"
down_revision: str | Sequence[str] | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

APP_ROLE = "app_rw"
FREE_PLAN_CODE = "free"
MODULE = "channel_manager"
SIMULATOR_CODE = "simulator"
LISTINGS = "channelsimulatorlisting"
LIMITS = '{"connected_channels": 1}'

SEED_SIMULATOR = f"""
INSERT INTO channelcatalog (code, name, kind, connectivity, country_codes, features)
VALUES ('{SIMULATOR_CODE}', 'Simulated agency (test)', 'ota', 'direct_api', '{{}}',
        '{{ari_push,booking_pull}}')
ON CONFLICT (code) DO NOTHING
"""

SEED_PLAN_MODULE = f"""
INSERT INTO planmodule (plan_id, module_code, limits)
SELECT p.id, '{MODULE}', '{LIMITS}'::jsonb FROM plan p WHERE p.code = '{FREE_PLAN_CODE}'
ON CONFLICT (plan_id, module_code) DO NOTHING
"""

# Tenants that signed up before this migration get what new tenants get at onboarding.
BACKFILL_ENTITLEMENTS = f"""
INSERT INTO tenantentitlement (tenant_id, module_code, source, limits)
SELECT s.tenant_id, '{MODULE}', 'plan', '{LIMITS}'::jsonb
FROM tenantsubscription s
JOIN plan p ON p.id = s.plan_id AND p.code = '{FREE_PLAN_CODE}'
WHERE NOT EXISTS (
  SELECT 1 FROM tenantentitlement e
  WHERE e.tenant_id = s.tenant_id AND e.module_code = '{MODULE}'
)
"""

RLS_POLICY = f"""
CREATE POLICY tenant_isolation ON {LISTINGS}
  USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
  WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
"""


def upgrade() -> None:
    """Upgrade schema."""
    op.execute(SEED_SIMULATOR)
    op.execute(SEED_PLAN_MODULE)
    op.execute(BACKFILL_ENTITLEMENTS)
    op.create_table(
        LISTINGS,
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("property_id", sa.Uuid(), nullable=False),
        sa.Column("hotel_id", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column(
            "rooms",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "property_id"],
            ["property.tenant_id", "property.id"],
            name=f"{LISTINGS}_tenant_id_property_id_fkey",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=f"{LISTINGS}_pkey"),
        sa.UniqueConstraint("tenant_id", "id", name=f"{LISTINGS}_tenant_id_id_key"),
        sa.UniqueConstraint("tenant_id", "hotel_id", name=f"{LISTINGS}_tenant_id_hotel_id_key"),
    )
    op.execute(f"ALTER TABLE {LISTINGS} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {LISTINGS} FORCE ROW LEVEL SECURITY")
    op.execute(RLS_POLICY)
    op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON {LISTINGS} TO {APP_ROLE}")


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table(LISTINGS)
    op.execute(f"DELETE FROM tenantentitlement WHERE module_code = '{MODULE}' AND source = 'plan'")
    op.execute(
        f"DELETE FROM planmodule WHERE module_code = '{MODULE}' "
        f"AND plan_id IN (SELECT id FROM plan WHERE code = '{FREE_PLAN_CODE}')"
    )
    op.execute(f"DELETE FROM channelcatalog WHERE code = '{SIMULATOR_CODE}'")
