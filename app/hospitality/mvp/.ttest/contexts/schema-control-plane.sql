-- =============================================================================
-- Hospitality Suite — CONTROL PLANE database (PostgreSQL 16+)
-- =============================================================================
-- One control-plane database per deployment. It knows WHO the tenants are,
-- WHERE each tenant's data lives (which cluster / database / schema), WHAT they
-- have licensed, and WHICH platform users belong to which tenant.
--
-- It holds NO operational hospitality data (no guests, reservations, folios).
--
-- Depends on the auth prefab's `user` table (backend/app/auth/models.py):
--     "user"(id int PK, email unique, hashed_password, created_at)
-- In single-database dev mode this file and schema-tenant.sql are applied to
-- the same database (prefab_db); table names do not collide.
--
-- Conventions: see database-design.md §3.
-- =============================================================================

CREATE EXTENSION IF NOT EXISTS pgcrypto;   -- gen_random_uuid() (built-in on PG13+, kept for clarity)

-- -----------------------------------------------------------------------------
-- Helper: keep updated_at fresh even for raw-SQL writes (ORM also sets it).
-- -----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION set_updated_at() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
  NEW.updated_at := now();
  RETURN NEW;
END $$;

-- =============================================================================
-- 1. Catalogs (platform-wide reference data)
-- =============================================================================

-- Sellable product modules (PMS Core and add-ons).
CREATE TABLE module (
  code          text PRIMARY KEY,                 -- e.g. 'pms_core', 'channel_manager'
  name          text NOT NULL,
  description   text,
  depends_on    text[] NOT NULL DEFAULT '{}',     -- module codes that must also be enabled
  is_active     boolean NOT NULL DEFAULT true,
  sort_order    integer NOT NULL DEFAULT 0,
  created_at    timestamptz NOT NULL DEFAULT now(),
  updated_at    timestamptz NOT NULL DEFAULT now()
);

-- Distribution channels the platform can connect to. Copied into each tenant DB
-- (tenant.channel) at provisioning so tenant data never references across DBs.
CREATE TABLE channelcatalog (
  code                  text PRIMARY KEY,         -- 'traveloka', 'google_hotels', 'airbnb', 'ical'
  name                  text NOT NULL,
  kind                  text NOT NULL CHECK (kind IN (
                          'ota','metasearch','google','gds','wholesaler','vacation_rental',
                          'ical','direct_web','direct_phone','walk_in','messaging','corporate','other')),
  connectivity          text NOT NULL CHECK (connectivity IN ('direct_api','partner','ical','manual')),
  certification_status  text NOT NULL DEFAULT 'planned'
                          CHECK (certification_status IN ('planned','in_progress','certified','deprecated')),
  country_codes         text[] NOT NULL DEFAULT '{}',   -- ISO-3166 alpha-2; empty = global
  features              text[] NOT NULL DEFAULT '{}',   -- 'ari_push','booking_pull','content','vcc','messaging','reviews'
  default_commission_pct numeric(5,2),
  is_active             boolean NOT NULL DEFAULT true,
  created_at            timestamptz NOT NULL DEFAULT now(),
  updated_at            timestamptz NOT NULL DEFAULT now()
);

-- Subscription plans.
CREATE TABLE plan (
  id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  code           text NOT NULL UNIQUE,
  name           text NOT NULL,
  billing_basis  text NOT NULL CHECK (billing_basis IN ('per_unit','flat','usage','free')),
  price_amount   numeric(18,2) NOT NULL DEFAULT 0,
  currency       char(3) NOT NULL DEFAULT 'IDR',
  billing_period text NOT NULL DEFAULT 'monthly' CHECK (billing_period IN ('monthly','yearly')),
  is_public      boolean NOT NULL DEFAULT true,
  is_active      boolean NOT NULL DEFAULT true,
  created_at     timestamptz NOT NULL DEFAULT now(),
  updated_at     timestamptz NOT NULL DEFAULT now(),
  created_by     text,
  updated_by     text
);

CREATE TABLE planmodule (
  plan_id      uuid NOT NULL REFERENCES plan(id) ON DELETE CASCADE,
  module_code  text NOT NULL REFERENCES module(code),
  limits       jsonb NOT NULL DEFAULT '{}',        -- e.g. {"max_units":30,"ai_budget_idr":150000}
  PRIMARY KEY (plan_id, module_code)
);

-- =============================================================================
-- 2. Database topology — where tenant data lives
-- =============================================================================

-- A PostgreSQL server/cluster that hosts tenant databases.
CREATE TABLE dbcluster (
  id                      uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  code                    text NOT NULL UNIQUE,     -- 'jkt-pooled-01', 'jkt-dedicated-07'
  region                  text NOT NULL,            -- cloud region, e.g. 'ap-southeast-3' (Jakarta)
  kind                    text NOT NULL CHECK (kind IN ('pooled','dedicated','mixed')),
  connection_secret_ref   text NOT NULL,            -- secret-manager key; NEVER a password
  replica_secret_ref      text,                     -- optional read replica for reporting/BI
  max_tenants             integer,                  -- capacity hint for pooled clusters
  status                  text NOT NULL DEFAULT 'active'
                            CHECK (status IN ('active','draining','read_only','retired')),
  created_at              timestamptz NOT NULL DEFAULT now(),
  updated_at              timestamptz NOT NULL DEFAULT now(),
  created_by              text,
  updated_by              text
);

-- =============================================================================
-- 3. Tenants
-- =============================================================================

CREATE TABLE tenant (
  id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  code              text NOT NULL UNIQUE CHECK (code ~ '^[a-z0-9][a-z0-9-]{1,62}$'),  -- slug, used in URLs
  name              text NOT NULL,
  legal_name        text,
  status            text NOT NULL DEFAULT 'provisioning'
                      CHECK (status IN ('provisioning','trial','active','past_due','suspended','cancelled','deleted')),
  country_code      char(2) NOT NULL DEFAULT 'ID',
  data_region       text NOT NULL DEFAULT 'ap-southeast-3',   -- residency requirement
  default_locale    text NOT NULL DEFAULT 'id-ID',
  default_currency  char(3) NOT NULL DEFAULT 'IDR',
  default_timezone  text NOT NULL DEFAULT 'Asia/Jakarta',
  isolation_tier    text NOT NULL DEFAULT 'pooled' CHECK (isolation_tier IN ('pooled','dedicated')),
  trial_ends_at     timestamptz,
  suspended_reason  text,
  deleted_at        timestamptz,
  metadata          jsonb NOT NULL DEFAULT '{}',
  created_at        timestamptz NOT NULL DEFAULT now(),
  updated_at        timestamptz NOT NULL DEFAULT now(),
  created_by        text,
  updated_by        text
);

-- Routing record: one per tenant. The API resolves tenant -> connection here,
-- caches it, and opens the session against the right database/schema.
CREATE TABLE tenantdatabase (
  id                     uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id              uuid NOT NULL UNIQUE REFERENCES tenant(id) ON DELETE CASCADE,
  cluster_id             uuid NOT NULL REFERENCES dbcluster(id),
  isolation_mode         text NOT NULL CHECK (isolation_mode IN (
                           'pooled_rls',        -- shared DB, rows isolated by tenant_id + RLS
                           'dedicated_schema',  -- shared server, own schema
                           'dedicated_db')),    -- own database (enterprise / residency / noisy neighbour)
  database_name          text NOT NULL,
  schema_name            text NOT NULL DEFAULT 'public',
  app_role_name          text,                  -- DB role the API uses for this tenant (dedicated modes)
  credentials_secret_ref text,                  -- secret-manager key for dedicated credentials
  schema_version         text,                  -- alembic revision applied
  status                 text NOT NULL DEFAULT 'provisioning'
                           CHECK (status IN ('provisioning','ready','migrating','read_only','moving','archived','failed')),
  last_migrated_at       timestamptz,
  created_at             timestamptz NOT NULL DEFAULT now(),
  updated_at             timestamptz NOT NULL DEFAULT now(),
  created_by             text,
  updated_by             text
);
CREATE INDEX ix_tenantdatabase_cluster ON tenantdatabase (cluster_id);

-- Migration / move history per tenant database.
CREATE TABLE tenantmigration (
  id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_database_id uuid NOT NULL REFERENCES tenantdatabase(id) ON DELETE CASCADE,
  kind               text NOT NULL CHECK (kind IN ('schema_upgrade','schema_downgrade','move_cluster','pooled_to_dedicated','dedicated_to_pooled','restore')),
  from_version       text,
  to_version         text,
  from_cluster_id    uuid REFERENCES dbcluster(id),
  to_cluster_id      uuid REFERENCES dbcluster(id),
  status             text NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','running','succeeded','failed','rolled_back')),
  started_at         timestamptz,
  finished_at        timestamptz,
  log                text,
  created_at         timestamptz NOT NULL DEFAULT now(),
  updated_at         timestamptz NOT NULL DEFAULT now(),
  created_by         text,
  updated_by         text
);

-- Custom hostnames (booking engine, guest portal) -> tenant routing.
CREATE TABLE tenantdomain (
  id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id    uuid NOT NULL REFERENCES tenant(id) ON DELETE CASCADE,
  hostname     text NOT NULL,
  purpose      text NOT NULL CHECK (purpose IN ('booking_engine','guest_portal','staff_app','api')),
  property_id  uuid,                         -- tenant-DB property id (no cross-DB FK)
  verified_at  timestamptz,
  status       text NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','active','failed','disabled')),
  created_at   timestamptz NOT NULL DEFAULT now(),
  updated_at   timestamptz NOT NULL DEFAULT now(),
  created_by   text,
  updated_by   text
);
CREATE UNIQUE INDEX ux_tenantdomain_hostname ON tenantdomain (lower(hostname));

-- Light directory of properties for routing and portfolio/CRS-style lookups
-- without opening every tenant DB. Written by tenant DB outbox events.
CREATE TABLE propertydirectory (
  property_id   uuid PRIMARY KEY,            -- same id as tenant-DB property.id
  tenant_id     uuid NOT NULL REFERENCES tenant(id) ON DELETE CASCADE,
  code          text NOT NULL,
  name          text NOT NULL,
  property_type text NOT NULL,
  country_code  char(2) NOT NULL,
  region_code   text,
  city          text,
  latitude      numeric(9,6),
  longitude     numeric(9,6),
  status        text NOT NULL,
  synced_at     timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_propertydirectory_tenant ON propertydirectory (tenant_id);

-- =============================================================================
-- 4. Subscriptions & entitlements (what the tenant can use)
-- =============================================================================

CREATE TABLE tenantsubscription (
  id                    uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id             uuid NOT NULL REFERENCES tenant(id) ON DELETE CASCADE,
  plan_id               uuid NOT NULL REFERENCES plan(id),
  status                text NOT NULL DEFAULT 'active'
                          CHECK (status IN ('trialing','active','past_due','paused','cancelled','ended')),
  started_on            date NOT NULL,
  ends_on               date,
  billed_unit_count     integer,
  external_billing_ref  text,
  created_at            timestamptz NOT NULL DEFAULT now(),
  updated_at            timestamptz NOT NULL DEFAULT now(),
  created_by            text,
  updated_by            text
);
CREATE INDEX ix_tenantsubscription_tenant ON tenantsubscription (tenant_id);

-- Effective module switches per tenant (plan + add-ons + trials + manual grants).
CREATE TABLE tenantentitlement (
  id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id    uuid NOT NULL REFERENCES tenant(id) ON DELETE CASCADE,
  module_code  text NOT NULL REFERENCES module(code),
  enabled      boolean NOT NULL DEFAULT true,
  source       text NOT NULL DEFAULT 'plan' CHECK (source IN ('plan','addon','trial','manual')),
  limits       jsonb NOT NULL DEFAULT '{}',
  valid_from   date,
  valid_to     date,
  created_at   timestamptz NOT NULL DEFAULT now(),
  updated_at   timestamptz NOT NULL DEFAULT now(),
  created_by   text,
  updated_by   text,
  UNIQUE (tenant_id, module_code)
);

-- =============================================================================
-- 5. Identity: platform users <-> tenants
-- =============================================================================
-- Login identity is the auth prefab's "user" table (one row per human, global).
-- A human may work for several tenants (e.g. a villa manager for many owners'
-- companies, a consultant). Tenant-specific profile, roles and property scope
-- live in the tenant DB (staffmember / staffroleassignment).

CREATE TABLE tenantmembership (
  id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id        uuid NOT NULL REFERENCES tenant(id) ON DELETE CASCADE,
  user_id          integer NOT NULL REFERENCES "user"(id) ON DELETE CASCADE,
  status           text NOT NULL DEFAULT 'active' CHECK (status IN ('invited','active','suspended','removed')),
  is_tenant_owner  boolean NOT NULL DEFAULT false,
  staff_member_id  uuid,                    -- tenant-DB staffmember.id (no cross-DB FK)
  last_property_id uuid,                    -- UI convenience: last property opened
  joined_at        timestamptz,
  created_at       timestamptz NOT NULL DEFAULT now(),
  updated_at       timestamptz NOT NULL DEFAULT now(),
  created_by       text,
  updated_by       text,
  UNIQUE (tenant_id, user_id)
);
CREATE INDEX ix_tenantmembership_user ON tenantmembership (user_id);

CREATE TABLE tenantinvitation (
  id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id           uuid NOT NULL REFERENCES tenant(id) ON DELETE CASCADE,
  email               text NOT NULL,
  token_hash          text NOT NULL UNIQUE,      -- store hash only; token goes in the URL path
  role_codes          text[] NOT NULL DEFAULT '{}',
  property_ids        uuid[] NOT NULL DEFAULT '{}',
  invited_by_user_id  integer REFERENCES "user"(id) ON DELETE SET NULL,
  expires_at          timestamptz NOT NULL,
  accepted_at         timestamptz,
  revoked_at          timestamptz,
  created_at          timestamptz NOT NULL DEFAULT now(),
  updated_at          timestamptz NOT NULL DEFAULT now(),
  created_by          text,
  updated_by          text
);
CREATE INDEX ix_tenantinvitation_email ON tenantinvitation (lower(email));

-- =============================================================================
-- 6. Platform-level usage metering (billing of AI and other metered features)
-- =============================================================================
-- Detailed per-call AI usage lives in the tenant DB (aiusage). This rolls it up
-- per tenant per month for billing and platform cost control.
CREATE TABLE tenantusagemonthly (
  tenant_id     uuid NOT NULL REFERENCES tenant(id) ON DELETE CASCADE,
  month         date NOT NULL CHECK (date_trunc('month', month)::date = month),
  metric        text NOT NULL,                -- 'ai_cost_idr','ai_tokens','whatsapp_messages','active_units'
  quantity      numeric(20,4) NOT NULL DEFAULT 0,
  amount        numeric(18,2),
  currency      char(3),
  updated_at    timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (tenant_id, month, metric)
);

-- =============================================================================
-- Triggers
-- =============================================================================
DO $$
DECLARE r record;
BEGIN
  FOR r IN
    SELECT c.table_name
    FROM information_schema.columns c
    JOIN information_schema.tables t
      ON t.table_schema = c.table_schema AND t.table_name = c.table_name
    WHERE c.table_schema = current_schema()
      AND c.column_name = 'updated_at'
      AND t.table_type = 'BASE TABLE'
      AND c.table_name IN ('module','channelcatalog','plan','dbcluster','tenant','tenantdatabase',
                           'tenantmigration','tenantdomain','tenantsubscription','tenantentitlement',
                           'tenantmembership','tenantinvitation','tenantusagemonthly')
  LOOP
    EXECUTE format('DROP TRIGGER IF EXISTS trg_set_updated_at ON %I', r.table_name);
    EXECUTE format('CREATE TRIGGER trg_set_updated_at BEFORE UPDATE ON %I
                    FOR EACH ROW EXECUTE FUNCTION set_updated_at()', r.table_name);
  END LOOP;
END $$;

-- =============================================================================
-- Seed data
-- =============================================================================
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
