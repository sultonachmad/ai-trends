"""control plane schema

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-08 15:37:37.336099

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel  # noqa: F401 — required for sqlmodel.sql.sqltypes.AutoString in generated migrations
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '0002'
down_revision: Union[str, Sequence[str], None] = '0001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

CONTROL_PLANE_TABLES = (
    "module", "channelcatalog", "plan", "dbcluster", "tenant", "tenantdatabase",
    "tenantmigration", "tenantdomain", "tenantsubscription", "tenantentitlement",
    "tenantmembership", "tenantinvitation", "tenantusagemonthly",
)

# Keeps updated_at fresh for raw-SQL writes too (the ORM also sets it).
SET_UPDATED_AT_FN = """
CREATE OR REPLACE FUNCTION set_updated_at() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
  NEW.updated_at := now();
  RETURN NEW;
END $$;
"""

SEED_MODULES = """
INSERT INTO module (code, name, depends_on, sort_order, description) VALUES
  ('pms_core',        'PMS Core',                   '{}',                    10, 'Inventory, rates, reservations, front desk, folio, night audit, reports'),
  ('payments',        'Payments',                   '{pms_core}',            20, 'QRIS, virtual accounts, e-wallets, cards, payment links, transfer-proof'),
  ('booking_engine',  'Booking Engine',             '{pms_core,payments}',   30, 'Direct booking website/widget, Google landing pages'),
  ('channel_manager', 'Channel Manager',            '{pms_core}',            40, 'OTA, Google and iCal connectivity'),
  ('crm',             'Guest CRM & Messaging',      '{pms_core}',            50, 'WhatsApp inbox, journeys, guest portal, reviews'),
  ('operations',      'Housekeeping & Maintenance', '{pms_core}',            60, 'Mobile tasks, inspections, work orders, vendors'),
  ('long_stay',       'Long Stay & Kos',            '{pms_core,payments}',   70, 'Leases, recurring billing, meters'),
  ('owner',           'Owner Management',           '{pms_core}',            80, 'Owner statements, payouts, owner portal'),
  ('rms',             'Revenue Management',         '{pms_core}',            90, 'Forecasts, price recommendations, competitor rates'),
  ('pos',             'POS Lite & Ancillary',       '{pms_core}',           100, 'Outlets, services, vouchers'),
  ('crs',             'Multi-Property / CRS Lite',  '{pms_core}',           110, 'Cross-property availability and reporting'),
  ('ai_assistant',    'AI Assistant',               '{pms_core}',           120, 'Drafting, extraction, translation, NL reports (metered)'),
  ('compliance_id',   'Indonesia Compliance Pack',  '{pms_core}',           130, 'APOA reporting, PBJT tax returns, KTP/passport capture')
ON CONFLICT (code) DO NOTHING;
"""

SEED_CHANNEL_CATALOG = """
INSERT INTO channelcatalog (code, name, kind, connectivity, country_codes, features, default_commission_pct) VALUES
  ('direct_web',     'Direct — Booking Engine', 'direct_web',      'manual',     '{}',    '{}',                                             0),
  ('direct_phone',   'Direct — Phone/Email',    'direct_phone',    'manual',     '{}',    '{}',                                             0),
  ('walk_in',        'Walk-in',                 'walk_in',         'manual',     '{}',    '{}',                                             0),
  ('whatsapp',       'WhatsApp / Social DM',    'messaging',       'manual',     '{}',    '{messaging}',                                    0),
  ('google_hotels',  'Google Hotels (Free Booking Links / Ads)', 'google', 'partner', '{}', '{ari_push,reviews}',                          0),
  ('traveloka',      'Traveloka',               'ota',             'partner',    '{ID,TH,VN,MY,PH,SG}', '{ari_push,booking_pull,content}', NULL),
  ('tiket',          'tiket.com',               'ota',             'partner',    '{ID}',  '{ari_push,booking_pull}',                        NULL),
  ('agoda',          'Agoda',                   'ota',             'partner',    '{}',    '{ari_push,booking_pull,content,vcc,messaging}', NULL),
  ('booking_com',    'Booking.com',             'ota',             'partner',    '{}',    '{ari_push,booking_pull,content,vcc,messaging,reviews}', NULL),
  ('airbnb',         'Airbnb',                  'vacation_rental', 'partner',    '{}',    '{ari_push,booking_pull,messaging,reviews}',      NULL),
  ('expedia',        'Expedia Group',           'ota',             'partner',    '{}',    '{ari_push,booking_pull,vcc}',                    NULL),
  ('trip_com',       'Trip.com',                'ota',             'partner',    '{}',    '{ari_push,booking_pull}',                        NULL),
  ('ical',           'iCal (generic)',          'ical',            'ical',       '{}',    '{}',                                             0)
ON CONFLICT (code) DO NOTHING;
"""


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")  # gen_random_uuid()
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('channelcatalog',
    sa.Column('code', sa.Text(), nullable=False),
    sa.Column('name', sa.Text(), nullable=False),
    sa.Column('kind', sa.Text(), nullable=False),
    sa.Column('connectivity', sa.Text(), nullable=False),
    sa.Column('certification_status', sa.Text(), server_default=sa.text("'planned'::text"), nullable=False),
    sa.Column('country_codes', postgresql.ARRAY(sa.Text()), server_default=sa.text("'{}'::text[]"), nullable=False),
    sa.Column('features', postgresql.ARRAY(sa.Text()), server_default=sa.text("'{}'::text[]"), nullable=False),
    sa.Column('default_commission_pct', sa.Numeric(precision=5, scale=2), nullable=True),
    sa.Column('is_active', sa.Boolean(), server_default=sa.text('true'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("certification_status IN ('planned', 'in_progress', 'certified', 'deprecated')", name='channelcatalog_certification_status_check'),
    sa.CheckConstraint("connectivity IN ('direct_api', 'partner', 'ical', 'manual')", name='channelcatalog_connectivity_check'),
    sa.CheckConstraint("kind IN ('ota', 'metasearch', 'google', 'gds', 'wholesaler', 'vacation_rental', 'ical', 'direct_web', 'direct_phone', 'walk_in', 'messaging', 'corporate', 'other')", name='channelcatalog_kind_check'),
    sa.PrimaryKeyConstraint('code')
    )
    op.create_table('dbcluster',
    sa.Column('id', sa.Uuid(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('created_by', sa.Text(), nullable=True),
    sa.Column('updated_by', sa.Text(), nullable=True),
    sa.Column('code', sa.Text(), nullable=False),
    sa.Column('region', sa.Text(), nullable=False),
    sa.Column('kind', sa.Text(), nullable=False),
    sa.Column('connection_secret_ref', sa.Text(), nullable=False),
    sa.Column('replica_secret_ref', sa.Text(), nullable=True),
    sa.Column('max_tenants', sa.Integer(), nullable=True),
    sa.Column('status', sa.Text(), server_default=sa.text("'active'::text"), nullable=False),
    sa.CheckConstraint("kind IN ('pooled', 'dedicated', 'mixed')", name='dbcluster_kind_check'),
    sa.CheckConstraint("status IN ('active', 'draining', 'read_only', 'retired')", name='dbcluster_status_check'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('code', name='dbcluster_code_key')
    )
    op.create_table('module',
    sa.Column('code', sa.Text(), nullable=False),
    sa.Column('name', sa.Text(), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('depends_on', postgresql.ARRAY(sa.Text()), server_default=sa.text("'{}'::text[]"), nullable=False),
    sa.Column('is_active', sa.Boolean(), server_default=sa.text('true'), nullable=False),
    sa.Column('sort_order', sa.Integer(), server_default=sa.text('0'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('code')
    )
    op.create_table('plan',
    sa.Column('id', sa.Uuid(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('created_by', sa.Text(), nullable=True),
    sa.Column('updated_by', sa.Text(), nullable=True),
    sa.Column('code', sa.Text(), nullable=False),
    sa.Column('name', sa.Text(), nullable=False),
    sa.Column('billing_basis', sa.Text(), nullable=False),
    sa.Column('price_amount', sa.Numeric(precision=18, scale=2), server_default=sa.text('0'), nullable=False),
    sa.Column('currency', sa.CHAR(length=3), server_default=sa.text("'IDR'::bpchar"), nullable=False),
    sa.Column('billing_period', sa.Text(), server_default=sa.text("'monthly'::text"), nullable=False),
    sa.Column('is_public', sa.Boolean(), server_default=sa.text('true'), nullable=False),
    sa.Column('is_active', sa.Boolean(), server_default=sa.text('true'), nullable=False),
    sa.CheckConstraint("billing_basis IN ('per_unit', 'flat', 'usage', 'free')", name='plan_billing_basis_check'),
    sa.CheckConstraint("billing_period IN ('monthly', 'yearly')", name='plan_billing_period_check'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('code', name='plan_code_key')
    )
    op.create_table('tenant',
    sa.Column('id', sa.Uuid(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('created_by', sa.Text(), nullable=True),
    sa.Column('updated_by', sa.Text(), nullable=True),
    sa.Column('code', sa.Text(), nullable=False),
    sa.Column('name', sa.Text(), nullable=False),
    sa.Column('legal_name', sa.Text(), nullable=True),
    sa.Column('status', sa.Text(), server_default=sa.text("'provisioning'::text"), nullable=False),
    sa.Column('country_code', sa.CHAR(length=2), server_default=sa.text("'ID'::bpchar"), nullable=False),
    sa.Column('data_region', sa.Text(), server_default=sa.text("'ap-southeast-3'::text"), nullable=False),
    sa.Column('default_locale', sa.Text(), server_default=sa.text("'id-ID'::text"), nullable=False),
    sa.Column('default_currency', sa.CHAR(length=3), server_default=sa.text("'IDR'::bpchar"), nullable=False),
    sa.Column('default_timezone', sa.Text(), server_default=sa.text("'Asia/Jakarta'::text"), nullable=False),
    sa.Column('isolation_tier', sa.Text(), server_default=sa.text("'pooled'::text"), nullable=False),
    sa.Column('trial_ends_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('suspended_reason', sa.Text(), nullable=True),
    sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
    sa.CheckConstraint("(code ~ '^[a-z0-9][a-z0-9-]{1,62}$'::text)", name='tenant_code_check'),
    sa.CheckConstraint("isolation_tier IN ('pooled', 'dedicated')", name='tenant_isolation_tier_check'),
    sa.CheckConstraint("status IN ('provisioning', 'trial', 'active', 'past_due', 'suspended', 'cancelled', 'deleted')", name='tenant_status_check'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('code', name='tenant_code_key')
    )
    op.create_table('planmodule',
    sa.Column('plan_id', sa.Uuid(), nullable=False),
    sa.Column('module_code', sa.Text(), nullable=False),
    sa.Column('limits', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
    sa.ForeignKeyConstraint(['module_code'], ['module.code'], name='planmodule_module_code_fkey'),
    sa.ForeignKeyConstraint(['plan_id'], ['plan.id'], name='planmodule_plan_id_fkey', ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('plan_id', 'module_code')
    )
    op.create_table('propertydirectory',
    sa.Column('property_id', sa.Uuid(), nullable=False),
    sa.Column('tenant_id', sa.Uuid(), nullable=False),
    sa.Column('code', sa.Text(), nullable=False),
    sa.Column('name', sa.Text(), nullable=False),
    sa.Column('property_type', sa.Text(), nullable=False),
    sa.Column('country_code', sa.CHAR(length=2), nullable=False),
    sa.Column('region_code', sa.Text(), nullable=True),
    sa.Column('city', sa.Text(), nullable=True),
    sa.Column('latitude', sa.Numeric(precision=9, scale=6), nullable=True),
    sa.Column('longitude', sa.Numeric(precision=9, scale=6), nullable=True),
    sa.Column('status', sa.Text(), nullable=False),
    sa.Column('synced_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['tenant_id'], ['tenant.id'], name='propertydirectory_tenant_id_fkey', ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('property_id')
    )
    op.create_index('ix_propertydirectory_tenant', 'propertydirectory', ['tenant_id'], unique=False)
    op.create_table('tenantdatabase',
    sa.Column('id', sa.Uuid(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('created_by', sa.Text(), nullable=True),
    sa.Column('updated_by', sa.Text(), nullable=True),
    sa.Column('tenant_id', sa.Uuid(), nullable=False),
    sa.Column('cluster_id', sa.Uuid(), nullable=False),
    sa.Column('isolation_mode', sa.Text(), nullable=False),
    sa.Column('database_name', sa.Text(), nullable=False),
    sa.Column('schema_name', sa.Text(), server_default=sa.text("'public'::text"), nullable=False),
    sa.Column('app_role_name', sa.Text(), nullable=True),
    sa.Column('credentials_secret_ref', sa.Text(), nullable=True),
    sa.Column('schema_version', sa.Text(), nullable=True),
    sa.Column('status', sa.Text(), server_default=sa.text("'provisioning'::text"), nullable=False),
    sa.Column('last_migrated_at', sa.DateTime(timezone=True), nullable=True),
    sa.CheckConstraint("isolation_mode IN ('pooled_rls', 'dedicated_schema', 'dedicated_db')", name='tenantdatabase_isolation_mode_check'),
    sa.CheckConstraint("status IN ('provisioning', 'ready', 'migrating', 'read_only', 'moving', 'archived', 'failed')", name='tenantdatabase_status_check'),
    sa.ForeignKeyConstraint(['cluster_id'], ['dbcluster.id'], name='tenantdatabase_cluster_id_fkey'),
    sa.ForeignKeyConstraint(['tenant_id'], ['tenant.id'], name='tenantdatabase_tenant_id_fkey', ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('tenant_id', name='tenantdatabase_tenant_id_key')
    )
    op.create_index('ix_tenantdatabase_cluster', 'tenantdatabase', ['cluster_id'], unique=False)
    op.create_table('tenantdomain',
    sa.Column('id', sa.Uuid(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('created_by', sa.Text(), nullable=True),
    sa.Column('updated_by', sa.Text(), nullable=True),
    sa.Column('tenant_id', sa.Uuid(), nullable=False),
    sa.Column('hostname', sa.Text(), nullable=False),
    sa.Column('purpose', sa.Text(), nullable=False),
    sa.Column('property_id', sa.Uuid(), nullable=True),
    sa.Column('verified_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('status', sa.Text(), server_default=sa.text("'pending'::text"), nullable=False),
    sa.CheckConstraint("purpose IN ('booking_engine', 'guest_portal', 'staff_app', 'api')", name='tenantdomain_purpose_check'),
    sa.CheckConstraint("status IN ('pending', 'active', 'failed', 'disabled')", name='tenantdomain_status_check'),
    sa.ForeignKeyConstraint(['tenant_id'], ['tenant.id'], name='tenantdomain_tenant_id_fkey', ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ux_tenantdomain_hostname', 'tenantdomain', [sa.literal_column('lower(hostname)')], unique=True)
    op.create_table('tenantentitlement',
    sa.Column('id', sa.Uuid(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('created_by', sa.Text(), nullable=True),
    sa.Column('updated_by', sa.Text(), nullable=True),
    sa.Column('tenant_id', sa.Uuid(), nullable=False),
    sa.Column('module_code', sa.Text(), nullable=False),
    sa.Column('enabled', sa.Boolean(), server_default=sa.text('true'), nullable=False),
    sa.Column('source', sa.Text(), server_default=sa.text("'plan'::text"), nullable=False),
    sa.Column('limits', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
    sa.Column('valid_from', sa.Date(), nullable=True),
    sa.Column('valid_to', sa.Date(), nullable=True),
    sa.CheckConstraint("source IN ('plan', 'addon', 'trial', 'manual')", name='tenantentitlement_source_check'),
    sa.ForeignKeyConstraint(['module_code'], ['module.code'], name='tenantentitlement_module_code_fkey'),
    sa.ForeignKeyConstraint(['tenant_id'], ['tenant.id'], name='tenantentitlement_tenant_id_fkey', ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('tenant_id', 'module_code', name='tenantentitlement_tenant_id_module_code_key')
    )
    op.create_table('tenantinvitation',
    sa.Column('id', sa.Uuid(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('created_by', sa.Text(), nullable=True),
    sa.Column('updated_by', sa.Text(), nullable=True),
    sa.Column('tenant_id', sa.Uuid(), nullable=False),
    sa.Column('email', sa.Text(), nullable=False),
    sa.Column('token_hash', sa.Text(), nullable=False),
    sa.Column('role_codes', postgresql.ARRAY(sa.Text()), server_default=sa.text("'{}'::text[]"), nullable=False),
    sa.Column('property_ids', postgresql.ARRAY(sa.Uuid()), server_default=sa.text("'{}'::uuid[]"), nullable=False),
    sa.Column('invited_by_user_id', sa.Integer(), nullable=True),
    sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('accepted_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['invited_by_user_id'], ['user.id'], name='tenantinvitation_invited_by_user_id_fkey', ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['tenant_id'], ['tenant.id'], name='tenantinvitation_tenant_id_fkey', ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('token_hash', name='tenantinvitation_token_hash_key')
    )
    op.create_index('ix_tenantinvitation_email', 'tenantinvitation', [sa.literal_column('lower(email)')], unique=False)
    op.create_table('tenantmembership',
    sa.Column('id', sa.Uuid(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('created_by', sa.Text(), nullable=True),
    sa.Column('updated_by', sa.Text(), nullable=True),
    sa.Column('tenant_id', sa.Uuid(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('status', sa.Text(), server_default=sa.text("'active'::text"), nullable=False),
    sa.Column('is_tenant_owner', sa.Boolean(), server_default=sa.text('false'), nullable=False),
    sa.Column('staff_member_id', sa.Uuid(), nullable=True),
    sa.Column('last_property_id', sa.Uuid(), nullable=True),
    sa.Column('joined_at', sa.DateTime(timezone=True), nullable=True),
    sa.CheckConstraint("status IN ('invited', 'active', 'suspended', 'removed')", name='tenantmembership_status_check'),
    sa.ForeignKeyConstraint(['tenant_id'], ['tenant.id'], name='tenantmembership_tenant_id_fkey', ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], ['user.id'], name='tenantmembership_user_id_fkey', ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('tenant_id', 'user_id', name='tenantmembership_tenant_id_user_id_key')
    )
    op.create_index('ix_tenantmembership_user', 'tenantmembership', ['user_id'], unique=False)
    op.create_table('tenantsubscription',
    sa.Column('id', sa.Uuid(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('created_by', sa.Text(), nullable=True),
    sa.Column('updated_by', sa.Text(), nullable=True),
    sa.Column('tenant_id', sa.Uuid(), nullable=False),
    sa.Column('plan_id', sa.Uuid(), nullable=False),
    sa.Column('status', sa.Text(), server_default=sa.text("'active'::text"), nullable=False),
    sa.Column('started_on', sa.Date(), nullable=False),
    sa.Column('ends_on', sa.Date(), nullable=True),
    sa.Column('billed_unit_count', sa.Integer(), nullable=True),
    sa.Column('external_billing_ref', sa.Text(), nullable=True),
    sa.CheckConstraint("status IN ('trialing', 'active', 'past_due', 'paused', 'cancelled', 'ended')", name='tenantsubscription_status_check'),
    sa.ForeignKeyConstraint(['plan_id'], ['plan.id'], name='tenantsubscription_plan_id_fkey'),
    sa.ForeignKeyConstraint(['tenant_id'], ['tenant.id'], name='tenantsubscription_tenant_id_fkey', ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_tenantsubscription_tenant', 'tenantsubscription', ['tenant_id'], unique=False)
    op.create_table('tenantusagemonthly',
    sa.Column('tenant_id', sa.Uuid(), nullable=False),
    sa.Column('month', sa.Date(), nullable=False),
    sa.Column('metric', sa.Text(), nullable=False),
    sa.Column('quantity', sa.Numeric(precision=20, scale=4), server_default=sa.text('0'), nullable=False),
    sa.Column('amount', sa.Numeric(precision=18, scale=2), nullable=True),
    sa.Column('currency', sa.CHAR(length=3), nullable=True),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("((date_trunc('month'::text, (month)::timestamp with time zone))::date = month)", name='tenantusagemonthly_month_check'),
    sa.ForeignKeyConstraint(['tenant_id'], ['tenant.id'], name='tenantusagemonthly_tenant_id_fkey', ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('tenant_id', 'month', 'metric')
    )
    op.create_table('tenantmigration',
    sa.Column('id', sa.Uuid(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('created_by', sa.Text(), nullable=True),
    sa.Column('updated_by', sa.Text(), nullable=True),
    sa.Column('tenant_database_id', sa.Uuid(), nullable=False),
    sa.Column('kind', sa.Text(), nullable=False),
    sa.Column('from_version', sa.Text(), nullable=True),
    sa.Column('to_version', sa.Text(), nullable=True),
    sa.Column('from_cluster_id', sa.Uuid(), nullable=True),
    sa.Column('to_cluster_id', sa.Uuid(), nullable=True),
    sa.Column('status', sa.Text(), server_default=sa.text("'pending'::text"), nullable=False),
    sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('finished_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('log', sa.Text(), nullable=True),
    sa.CheckConstraint("kind IN ('schema_upgrade', 'schema_downgrade', 'move_cluster', 'pooled_to_dedicated', 'dedicated_to_pooled', 'restore')", name='tenantmigration_kind_check'),
    sa.CheckConstraint("status IN ('pending', 'running', 'succeeded', 'failed', 'rolled_back')", name='tenantmigration_status_check'),
    sa.ForeignKeyConstraint(['from_cluster_id'], ['dbcluster.id'], name='tenantmigration_from_cluster_id_fkey'),
    sa.ForeignKeyConstraint(['tenant_database_id'], ['tenantdatabase.id'], name='tenantmigration_tenant_database_id_fkey', ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['to_cluster_id'], ['dbcluster.id'], name='tenantmigration_to_cluster_id_fkey'),
    sa.PrimaryKeyConstraint('id')
    )
    # ### end Alembic commands ###

    # ---- hand-written: triggers + catalog seeds (schema-control-plane.sql) ----
    op.execute(SET_UPDATED_AT_FN)
    for table in CONTROL_PLANE_TABLES:
        op.execute(
            f"CREATE TRIGGER trg_set_updated_at BEFORE UPDATE ON {table} "
            "FOR EACH ROW EXECUTE FUNCTION set_updated_at()"
        )
    op.execute(SEED_MODULES)
    op.execute(SEED_CHANNEL_CATALOG)


def downgrade() -> None:
    """Downgrade schema."""
    for table in CONTROL_PLANE_TABLES:
        op.execute(f"DROP TRIGGER IF EXISTS trg_set_updated_at ON {table}")
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table('tenantmigration')
    op.drop_table('tenantusagemonthly')
    op.drop_index('ix_tenantsubscription_tenant', table_name='tenantsubscription')
    op.drop_table('tenantsubscription')
    op.drop_index('ix_tenantmembership_user', table_name='tenantmembership')
    op.drop_table('tenantmembership')
    op.drop_index('ix_tenantinvitation_email', table_name='tenantinvitation')
    op.drop_table('tenantinvitation')
    op.drop_table('tenantentitlement')
    op.drop_index('ux_tenantdomain_hostname', table_name='tenantdomain')
    op.drop_table('tenantdomain')
    op.drop_index('ix_tenantdatabase_cluster', table_name='tenantdatabase')
    op.drop_table('tenantdatabase')
    op.drop_index('ix_propertydirectory_tenant', table_name='propertydirectory')
    op.drop_table('propertydirectory')
    op.drop_table('planmodule')
    op.drop_table('tenant')
    op.drop_table('plan')
    op.drop_table('module')
    op.drop_table('dbcluster')
    op.drop_table('channelcatalog')
    # ### end Alembic commands ###
    # 0002 owns set_updated_at(); 0003 (tenant schema) reuses it and leaves it alone.
    op.execute("DROP FUNCTION IF EXISTS set_updated_at()")
