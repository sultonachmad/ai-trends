-- =============================================================================
-- Hospitality Suite — TENANT database schema (PostgreSQL 16+)
-- =============================================================================
-- The same DDL is used for every deployment mode recorded in the control
-- plane's tenantdatabase.isolation_mode:
--   pooled_rls        many tenants in one database, isolated by tenant_id + RLS
--   dedicated_schema  one schema per tenant on a shared server
--   dedicated_db      one database per tenant
-- Every table carries tenant_id (constant in dedicated modes) so a tenant can be
-- moved between modes by copying rows WHERE tenant_id = :t — no key rewrites,
-- because all ids are UUIDs.
--
-- Conventions (see database-design.md §3):
--   * Table name = lowercased SQLModel class name (scaffold rule, no __tablename__).
--   * id uuid PK; UNIQUE (tenant_id, id) on every table so child tables use
--     COMPOSITE foreign keys (tenant_id, parent_id) -> parent (tenant_id, id).
--     The database itself rejects any reference that crosses tenants.
--   * Nullable composite FKs use ON DELETE SET NULL (col) (PG15+) so tenant_id
--     is never nulled.
--   * Enumerations are text + CHECK (cheap to evolve in migrations).
--   * Money numeric(18,2) + currency char(3). Stay dates are `date` in property
--     local time; instants are timestamptz (UTC).
--   * created_at / updated_at / created_by / updated_by match TimestampMixin.
--   * References to the control-plane "user" table are plain integer columns
--     (no cross-database FK).
-- =============================================================================

CREATE EXTENSION IF NOT EXISTS pgcrypto;    -- gen_random_uuid()
CREATE EXTENSION IF NOT EXISTS btree_gist;  -- uuid '=' inside EXCLUDE constraints (no double-booking)
CREATE EXTENSION IF NOT EXISTS pg_trgm;     -- fuzzy guest-name search
-- Optional, when available: CREATE EXTENSION vector;  (see aichunk.embedding)

CREATE OR REPLACE FUNCTION set_updated_at() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
  NEW.updated_at := now();
  RETURN NEW;
END $$;

-- =============================================================================
-- A. ORGANISATION & PROPERTY
-- =============================================================================

-- Local mirror of the control-plane tenant (one row per tenant in this DB).
CREATE TABLE tenantprofile (
  id                uuid PRIMARY KEY,                -- == control plane tenant.id
  tenant_id         uuid NOT NULL CHECK (tenant_id = id),
  code              text NOT NULL,
  name              text NOT NULL,
  default_locale    text NOT NULL DEFAULT 'id-ID',
  default_currency  char(3) NOT NULL DEFAULT 'IDR',
  default_timezone  text NOT NULL DEFAULT 'Asia/Jakarta',
  enabled_modules   text[] NOT NULL DEFAULT '{}',    -- cached entitlements; control plane is the truth
  settings          jsonb NOT NULL DEFAULT '{}',
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  created_by text, updated_by text,
  UNIQUE (tenant_id, id)
);

-- Legal/fiscal entity that issues invoices (PT / CV / individual operator).
CREATE TABLE legalentity (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id     uuid NOT NULL,
  name          text NOT NULL,
  kind          text NOT NULL DEFAULT 'company' CHECK (kind IN ('company','individual','cooperative','government')),
  tax_id        text,                                -- NPWP in Indonesia
  business_id   text,                                -- NIB (OSS) in Indonesia
  country_code  char(2) NOT NULL DEFAULT 'ID',
  currency      char(3) NOT NULL DEFAULT 'IDR',
  address       jsonb NOT NULL DEFAULT '{}',
  is_vat_registered boolean NOT NULL DEFAULT false,  -- PKP
  is_active     boolean NOT NULL DEFAULT true,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  created_by text, updated_by text,
  UNIQUE (tenant_id, id),
  FOREIGN KEY (tenant_id) REFERENCES tenantprofile (id)
);

CREATE TABLE property (
  id                    uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id             uuid NOT NULL,
  legal_entity_id       uuid NOT NULL,
  code                  text NOT NULL,
  name                  text NOT NULL,
  property_type         text NOT NULL CHECK (property_type IN (
                          'hotel','resort','serviced_apartment','hostel','guesthouse','villa_portfolio',
                          'campsite','condo_hotel','coliving_kos','lodge','marina','day_use','homestay_cluster')),
  status                text NOT NULL DEFAULT 'setup' CHECK (status IN ('setup','live','seasonal_closed','suspended','archived')),
  timezone              text NOT NULL DEFAULT 'Asia/Jakarta',
  currency              char(3) NOT NULL DEFAULT 'IDR',
  country_code          char(2) NOT NULL DEFAULT 'ID',
  region_code           text,                       -- kab/kota code (drives PBJT tax pack, APOA office)
  address               jsonb NOT NULL DEFAULT '{}',
  latitude              numeric(9,6),
  longitude             numeric(9,6),
  phone                 text,
  email                 text,
  whatsapp_phone        text,
  star_rating           numeric(2,1),
  check_in_time         time NOT NULL DEFAULT '14:00',
  check_out_time        time NOT NULL DEFAULT '12:00',
  current_business_date date NOT NULL DEFAULT CURRENT_DATE,
  night_audit_mode      text NOT NULL DEFAULT 'auto' CHECK (night_audit_mode IN ('auto','attended')),
  night_audit_time      time NOT NULL DEFAULT '02:00',
  readiness_rule        text NOT NULL DEFAULT 'clean' CHECK (readiness_rule IN ('clean','inspected')),
  price_display_mode    text NOT NULL DEFAULT 'nett' CHECK (price_display_mode IN ('nett','plus_plus')),  -- "++" = excl. service & tax
  is_syariah            boolean NOT NULL DEFAULT false,
  max_occupancy         integer,                    -- fire-safety cap for the whole property
  licences              jsonb NOT NULL DEFAULT '{}',-- {"tdup":"...","pondok_wisata":"...","chse":"..."}
  amenities             text[] NOT NULL DEFAULT '{}',
  content               jsonb NOT NULL DEFAULT '{}',-- {"id-ID":{"description":"...","house_rules":"..."},"en":{...}}
  settings              jsonb NOT NULL DEFAULT '{}',
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  created_by text, updated_by text,
  UNIQUE (tenant_id, id),
  UNIQUE (tenant_id, code),
  FOREIGN KEY (tenant_id, legal_entity_id) REFERENCES legalentity (tenant_id, id)
);

-- Building / floor / wing / zone / campsite area. Self-referencing tree.
CREATE TABLE propertyarea (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id       uuid NOT NULL,
  property_id     uuid NOT NULL,
  parent_area_id  uuid,
  kind            text NOT NULL CHECK (kind IN ('building','floor','wing','zone','site','public_area')),
  name            text NOT NULL,
  sort_order      integer NOT NULL DEFAULT 0,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  created_by text, updated_by text,
  UNIQUE (tenant_id, id),
  FOREIGN KEY (tenant_id, property_id) REFERENCES property (tenant_id, id) ON DELETE CASCADE,
  FOREIGN KEY (tenant_id, parent_area_id) REFERENCES propertyarea (tenant_id, id) ON DELETE SET NULL (parent_area_id)
);

-- Amenity / feature dictionary (codes are referenced from text[] columns).
CREATE TABLE amenity (
  id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id  uuid NOT NULL,
  code       text NOT NULL,                         -- 'wifi','pool','kitchen','prayer_room','qibla'
  category   text NOT NULL DEFAULT 'general',
  name_i18n  jsonb NOT NULL DEFAULT '{}',
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  created_by text, updated_by text,
  UNIQUE (tenant_id, id),
  UNIQUE (tenant_id, code)
);

-- File metadata (scans, contracts, photos, PDFs). Bytes live in object storage.
CREATE TABLE document (
  id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id        uuid NOT NULL,
  property_id      uuid,
  kind             text NOT NULL CHECK (kind IN (
                     'identity_scan','registration_card','contract','invoice_pdf','report','photo',
                     'transfer_proof','manual','receipt','owner_statement','other')),
  classification   text NOT NULL DEFAULT 'internal' CHECK (classification IN ('public','internal','personal','identity','financial')),
  storage_key      text NOT NULL,                   -- object-storage key; never exposed to clients
  original_name    text,
  content_type     text NOT NULL,
  size_bytes       bigint NOT NULL CHECK (size_bytes >= 0),
  sha256           text,
  retention_until  date,
  uploaded_by      text,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  created_by text, updated_by text,
  UNIQUE (tenant_id, id),
  FOREIGN KEY (tenant_id, property_id) REFERENCES property (tenant_id, id) ON DELETE SET NULL (property_id)
);

-- Distribution / booking-source channels (seeded from control-plane channelcatalog).
CREATE TABLE channel (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id       uuid NOT NULL,
  code            text NOT NULL,                    -- 'traveloka','direct_web','walk_in','whatsapp'
  name            text NOT NULL,
  kind            text NOT NULL CHECK (kind IN (
                    'ota','metasearch','google','gds','wholesaler','vacation_rental',
                    'ical','direct_web','direct_phone','walk_in','messaging','corporate','other')),
  commission_pct  numeric(5,2),
  is_direct       boolean NOT NULL DEFAULT false,
  is_active       boolean NOT NULL DEFAULT true,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  created_by text, updated_by text,
  UNIQUE (tenant_id, id),
  UNIQUE (tenant_id, code)
);

CREATE TABLE marketsegment (
  id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id  uuid NOT NULL,
  code       text NOT NULL,                         -- 'leisure','corporate','government','group','long_stay'
  name       text NOT NULL,
  is_active  boolean NOT NULL DEFAULT true,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  created_by text, updated_by text,
  UNIQUE (tenant_id, id),
  UNIQUE (tenant_id, code)
);

-- Reason codes for cancellations, voids, discounts, upgrades, OOO, comps …
CREATE TABLE reasoncode (
  id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id  uuid NOT NULL,
  kind       text NOT NULL CHECK (kind IN ('cancellation','void','adjustment','discount','upgrade','room_move',
                                           'out_of_order','complimentary','no_show_waiver','refund','blacklist','other')),
  code       text NOT NULL,
  name       text NOT NULL,
  requires_approval boolean NOT NULL DEFAULT false,
  is_active  boolean NOT NULL DEFAULT true,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  created_by text, updated_by text,
  UNIQUE (tenant_id, id),
  UNIQUE (tenant_id, kind, code)
);

-- =============================================================================
-- B. STAFF, VENDORS & TENANT-SCOPED ROLES
-- =============================================================================

CREATE TABLE vendor (
  id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id      uuid NOT NULL,
  name           text NOT NULL,
  kind           text NOT NULL CHECK (kind IN ('cleaning','maintenance','laundry','transport','supplies','activity','other')),
  phone          text,
  email          text,
  tax_id         text,
  payment_terms_days integer,
  bank_details   jsonb NOT NULL DEFAULT '{}',       -- masked; full numbers in secret store
  is_active      boolean NOT NULL DEFAULT true,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  created_by text, updated_by text,
  UNIQUE (tenant_id, id)
);

-- Tenant-specific staff profile. Login identity = control-plane "user".
CREATE TABLE staffmember (
  id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id      uuid NOT NULL,
  user_id        integer,                           -- control-plane "user".id; NULL for PIN-only staff
  vendor_id      uuid,                              -- set for external vendor workers
  display_name   text NOT NULL,
  email          text,
  phone          text,
  employee_code  text,
  department     text CHECK (department IN ('front_office','housekeeping','maintenance','fnb','sales','revenue','finance','management','other')),
  language       text NOT NULL DEFAULT 'id-ID',
  ui_mode        text NOT NULL DEFAULT 'classic' CHECK (ui_mode IN ('classic','guided')),
  pin_hash       text,                              -- quick login on shared housekeeping devices
  status         text NOT NULL DEFAULT 'active' CHECK (status IN ('active','suspended','left')),
  valid_until    date,                              -- seasonal / temporary staff
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  created_by text, updated_by text,
  UNIQUE (tenant_id, id),
  FOREIGN KEY (tenant_id, vendor_id) REFERENCES vendor (tenant_id, id) ON DELETE SET NULL (vendor_id)
);
CREATE UNIQUE INDEX ux_staffmember_user ON staffmember (tenant_id, user_id) WHERE user_id IS NOT NULL;

-- Tenant-defined role (front desk, housekeeper, revenue manager …).
CREATE TABLE staffrole (
  id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id    uuid NOT NULL,
  code         text NOT NULL,
  name         text NOT NULL,
  description  text,
  is_system    boolean NOT NULL DEFAULT false,      -- seeded template, not deletable
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  created_by text, updated_by text,
  UNIQUE (tenant_id, id),
  UNIQUE (tenant_id, code)
);

-- Permission codes are the same codes as backend/docs/rbac-spec.yaml (module:action).
CREATE TABLE staffrolepermission (
  tenant_id        uuid NOT NULL,
  role_id          uuid NOT NULL,
  permission_code  text NOT NULL,
  PRIMARY KEY (tenant_id, role_id, permission_code),
  FOREIGN KEY (tenant_id, role_id) REFERENCES staffrole (tenant_id, id) ON DELETE CASCADE
);

-- Role grant, optionally limited to one property (NULL property = all properties).
CREATE TABLE staffroleassignment (
  id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id        uuid NOT NULL,
  staff_member_id  uuid NOT NULL,
  role_id          uuid NOT NULL,
  property_id      uuid,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  created_by text, updated_by text,
  UNIQUE (tenant_id, id),
  UNIQUE NULLS NOT DISTINCT (tenant_id, staff_member_id, role_id, property_id),
  FOREIGN KEY (tenant_id, staff_member_id) REFERENCES staffmember (tenant_id, id) ON DELETE CASCADE,
  FOREIGN KEY (tenant_id, role_id) REFERENCES staffrole (tenant_id, id) ON DELETE CASCADE,
  FOREIGN KEY (tenant_id, property_id) REFERENCES property (tenant_id, id) ON DELETE CASCADE
);

-- =============================================================================
-- C. INVENTORY (one "unit" abstraction for rooms, beds, villas, pitches …)
-- =============================================================================

CREATE TABLE unittype (
  id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id           uuid NOT NULL,
  property_id         uuid NOT NULL,
  code                text NOT NULL,
  name                text NOT NULL,
  category            text NOT NULL CHECK (category IN ('room','bed','apartment','villa','pitch','cabin','pod','berth','space','other')),
  sell_mode           text NOT NULL DEFAULT 'unit' CHECK (sell_mode IN ('unit','bed')),   -- bed = dorm sold per bed
  time_grain          text NOT NULL DEFAULT 'night' CHECK (time_grain IN ('night','day','hour_block','month')),
  hour_block_minutes  integer CHECK (hour_block_minutes > 0),
  turnaround_minutes  integer NOT NULL DEFAULT 0 CHECK (turnaround_minutes >= 0),
  base_occupancy      integer NOT NULL DEFAULT 2 CHECK (base_occupancy > 0),
  max_adults          integer NOT NULL DEFAULT 2 CHECK (max_adults > 0),
  max_children        integer NOT NULL DEFAULT 0 CHECK (max_children >= 0),
  max_occupancy       integer NOT NULL DEFAULT 2 CHECK (max_occupancy > 0),
  gender_policy       text NOT NULL DEFAULT 'any' CHECK (gender_policy IN ('any','male','female','mixed')),
  bed_config          jsonb NOT NULL DEFAULT '[]',  -- [{"type":"king","count":1}]
  size_sqm            numeric(7,2),
  amenities           text[] NOT NULL DEFAULT '{}',
  content             jsonb NOT NULL DEFAULT '{}',  -- multilingual name/description/photos
  is_virtual          boolean NOT NULL DEFAULT false, -- run-of-house
  sort_order          integer NOT NULL DEFAULT 0,
  is_active           boolean NOT NULL DEFAULT true,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  created_by text, updated_by text,
  UNIQUE (tenant_id, id),
  UNIQUE (tenant_id, property_id, code),
  CHECK (time_grain <> 'hour_block' OR hour_block_minutes IS NOT NULL),
  FOREIGN KEY (tenant_id, property_id) REFERENCES property (tenant_id, id) ON DELETE CASCADE
);

-- Physical, assignable unit. parent_unit_id models beds-in-a-dorm and
-- bedrooms-in-a-villa (combinable units).
CREATE TABLE unit (
  id                    uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id             uuid NOT NULL,
  property_id           uuid NOT NULL,
  unit_type_id          uuid NOT NULL,
  area_id               uuid,
  parent_unit_id        uuid,
  code                  text NOT NULL,              -- room number / bed label / pitch no.
  name                  text,
  floor                 text,
  features              text[] NOT NULL DEFAULT '{}', -- 'sea_view','smoking','pet_friendly','connecting'
  is_accessible         boolean NOT NULL DEFAULT false,
  is_sellable           boolean NOT NULL DEFAULT true,  -- false = staff/owner/model unit
  gender_restriction    text CHECK (gender_restriction IN ('male','female','mixed')),
  max_vehicle_length_m  numeric(4,1),               -- pitches / berths
  hookups               jsonb NOT NULL DEFAULT '{}',-- {"electric_amp":16,"water":true}
  hk_status             text NOT NULL DEFAULT 'clean' CHECK (hk_status IN ('dirty','in_progress','clean','inspected')),
  fo_status             text NOT NULL DEFAULT 'vacant' CHECK (fo_status IN ('vacant','occupied')),
  service_status        text NOT NULL DEFAULT 'in_service' CHECK (service_status IN ('in_service','out_of_order','out_of_service')),
  hk_status_changed_at  timestamptz,
  sort_order            integer NOT NULL DEFAULT 0,
  is_active             boolean NOT NULL DEFAULT true,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  created_by text, updated_by text,
  UNIQUE (tenant_id, id),
  UNIQUE (tenant_id, property_id, code),
  CHECK (parent_unit_id IS NULL OR parent_unit_id <> id),
  FOREIGN KEY (tenant_id, property_id) REFERENCES property (tenant_id, id) ON DELETE CASCADE,
  FOREIGN KEY (tenant_id, unit_type_id) REFERENCES unittype (tenant_id, id),
  FOREIGN KEY (tenant_id, area_id) REFERENCES propertyarea (tenant_id, id) ON DELETE SET NULL (area_id),
  FOREIGN KEY (tenant_id, parent_unit_id) REFERENCES unit (tenant_id, id) ON DELETE SET NULL (parent_unit_id)
);
CREATE INDEX ix_unit_type ON unit (tenant_id, unit_type_id);
CREATE INDEX ix_unit_parent ON unit (tenant_id, parent_unit_id) WHERE parent_unit_id IS NOT NULL;

-- Countable non-unit inventory: parking, cots, extra beds, lockers, bikes, EV chargers.
CREATE TABLE inventoryitem (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id       uuid NOT NULL,
  property_id     uuid NOT NULL,
  code            text NOT NULL,
  name            text NOT NULL,
  kind            text NOT NULL CHECK (kind IN ('parking','cot','extra_bed','locker','equipment','ev_charger','other')),
  total_quantity  integer NOT NULL CHECK (total_quantity >= 0),
  is_active       boolean NOT NULL DEFAULT true,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  created_by text, updated_by text,
  UNIQUE (tenant_id, id),
  UNIQUE (tenant_id, property_id, code),
  FOREIGN KEY (tenant_id, property_id) REFERENCES property (tenant_id, id) ON DELETE CASCADE
);

-- Per unit-type per date availability counters. Booking flows lock the row
-- (SELECT … FOR UPDATE) and bump `sold`; channel overbookings are allowed and
-- flagged by the application, so there is no hard capacity CHECK here.
CREATE TABLE inventoryday (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id       uuid NOT NULL,
  property_id     uuid NOT NULL,
  unit_type_id    uuid NOT NULL,
  stay_date       date NOT NULL,
  physical        integer NOT NULL DEFAULT 0 CHECK (physical >= 0),
  sold            integer NOT NULL DEFAULT 0 CHECK (sold >= 0),
  blocked         integer NOT NULL DEFAULT 0 CHECK (blocked >= 0),   -- group/allotment holds
  out_of_order    integer NOT NULL DEFAULT 0 CHECK (out_of_order >= 0),
  overbook_limit  integer NOT NULL DEFAULT 0 CHECK (overbook_limit >= 0),
  available       integer GENERATED ALWAYS AS (physical + overbook_limit - sold - blocked - out_of_order) STORED,
  version         integer NOT NULL DEFAULT 1,
  updated_at      timestamptz NOT NULL DEFAULT now(),
  UNIQUE (tenant_id, id),
  UNIQUE (tenant_id, unit_type_id, stay_date),
  FOREIGN KEY (tenant_id, property_id) REFERENCES property (tenant_id, id) ON DELETE CASCADE,
  FOREIGN KEY (tenant_id, unit_type_id) REFERENCES unittype (tenant_id, id) ON DELETE CASCADE
);
CREATE INDEX ix_inventoryday_property_date ON inventoryday (tenant_id, property_id, stay_date);

-- =============================================================================
-- D. FINANCE CONFIGURATION (needed by products & rates)
-- =============================================================================

CREATE TABLE taxrule (
  id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id        uuid NOT NULL,
  property_id      uuid,                            -- NULL = tenant-wide
  code             text NOT NULL,
  name             text NOT NULL,
  report_category  text NOT NULL CHECK (report_category IN ('pbjt_hotel','pbjt_restaurant','vat','service_charge','tourist_tax','other')),
  calc_kind        text NOT NULL CHECK (calc_kind IN ('percent','fixed_per_unit_night','fixed_per_person_night','fixed_per_stay','fixed_per_item')),
  rate_pct         numeric(7,4),
  fixed_amount     numeric(18,2),
  is_inclusive     boolean NOT NULL DEFAULT false,  -- included in price ("nett") vs added ("++")
  compound_order   integer NOT NULL DEFAULT 0,      -- service charge (0) before PBJT (1) when PBJT applies on top
  region_code      text,
  effective_from   date NOT NULL,
  effective_to     date,
  exemptions       jsonb NOT NULL DEFAULT '{}',     -- {"max_nights":30,"min_age":12,"long_stay_exempt_after":30}
  is_active        boolean NOT NULL DEFAULT true,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  created_by text, updated_by text,
  UNIQUE (tenant_id, id),
  UNIQUE (tenant_id, code, effective_from),
  CHECK (effective_to IS NULL OR effective_to >= effective_from),
  CHECK ((calc_kind = 'percent' AND rate_pct IS NOT NULL) OR (calc_kind <> 'percent' AND fixed_amount IS NOT NULL)),
  FOREIGN KEY (tenant_id, property_id) REFERENCES property (tenant_id, id) ON DELETE CASCADE
);

CREATE TABLE transactioncode (
  id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id          uuid NOT NULL,
  property_id        uuid,                          -- NULL = tenant-wide
  code               text NOT NULL,
  name               text NOT NULL,
  kind               text NOT NULL CHECK (kind IN ('charge','payment','tax','fee','deposit','adjustment','transfer','commission')),
  department         text NOT NULL DEFAULT 'rooms' CHECK (department IN ('rooms','fnb','spa','activities','retail','parking','utilities','other')),
  revenue_category   text,
  gl_account         text,
  allow_manual_post  boolean NOT NULL DEFAULT true,
  is_active          boolean NOT NULL DEFAULT true,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  created_by text, updated_by text,
  UNIQUE (tenant_id, id),
  UNIQUE NULLS NOT DISTINCT (tenant_id, property_id, code),
  FOREIGN KEY (tenant_id, property_id) REFERENCES property (tenant_id, id) ON DELETE CASCADE
);

CREATE TABLE transactioncodetax (
  tenant_id            uuid NOT NULL,
  transaction_code_id  uuid NOT NULL,
  tax_rule_id          uuid NOT NULL,
  sequence             integer NOT NULL DEFAULT 0,
  PRIMARY KEY (tenant_id, transaction_code_id, tax_rule_id),
  FOREIGN KEY (tenant_id, transaction_code_id) REFERENCES transactioncode (tenant_id, id) ON DELETE CASCADE,
  FOREIGN KEY (tenant_id, tax_rule_id) REFERENCES taxrule (tenant_id, id) ON DELETE CASCADE
);

CREATE TABLE exchangerate (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id       uuid NOT NULL,
  base_currency   char(3) NOT NULL,
  quote_currency  char(3) NOT NULL,
  rate            numeric(20,8) NOT NULL CHECK (rate > 0),
  effective_date  date NOT NULL,
  source          text NOT NULL DEFAULT 'manual',
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  created_by text, updated_by text,
  UNIQUE (tenant_id, id),
  UNIQUE (tenant_id, base_currency, quote_currency, effective_date)
);

-- =============================================================================
-- E. RATES, POLICIES, PRODUCTS & RESTRICTIONS
-- =============================================================================

CREATE TABLE cancellationpolicy (
  id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id        uuid NOT NULL,
  property_id      uuid,
  code             text NOT NULL,
  name             text NOT NULL,
  -- [{"before_arrival_hours":72,"fee":{"kind":"percent","value":0}},
  --  {"before_arrival_hours":0,"fee":{"kind":"first_night"}}]
  rules            jsonb NOT NULL DEFAULT '[]',
  no_show_rule     jsonb NOT NULL DEFAULT '{"kind":"first_night"}',
  description_i18n jsonb NOT NULL DEFAULT '{}',
  is_non_refundable boolean NOT NULL DEFAULT false,
  is_active        boolean NOT NULL DEFAULT true,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  created_by text, updated_by text,
  UNIQUE (tenant_id, id),
  UNIQUE NULLS NOT DISTINCT (tenant_id, property_id, code),
  FOREIGN KEY (tenant_id, property_id) REFERENCES property (tenant_id, id) ON DELETE CASCADE
);

CREATE TABLE paymentpolicy (
  id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id        uuid NOT NULL,
  property_id      uuid,
  code             text NOT NULL,
  name             text NOT NULL,
  guarantee_kind   text NOT NULL CHECK (guarantee_kind IN ('none','card','deposit','full_prepay','company','voucher')),
  -- [{"due":"at_booking","percent":50},{"due":"days_before_arrival","days":7,"percent":50}]
  schedule         jsonb NOT NULL DEFAULT '[]',
  auto_cancel_unpaid_after_hours integer,           -- release unpaid DP holds
  description_i18n jsonb NOT NULL DEFAULT '{}',
  is_active        boolean NOT NULL DEFAULT true,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  created_by text, updated_by text,
  UNIQUE (tenant_id, id),
  UNIQUE NULLS NOT DISTINCT (tenant_id, property_id, code),
  FOREIGN KEY (tenant_id, property_id) REFERENCES property (tenant_id, id) ON DELETE CASCADE
);

-- Anything sellable besides the unit itself: breakfast, parking, fees, services, package parts.
CREATE TABLE product (
  id                   uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id            uuid NOT NULL,
  property_id          uuid NOT NULL,
  code                 text NOT NULL,
  name                 text NOT NULL,
  kind                 text NOT NULL CHECK (kind IN ('meal','fee','service','parking','rental','retail','activity','transfer','upgrade','other')),
  pricing_unit         text NOT NULL CHECK (pricing_unit IN ('per_stay','per_night','per_person','per_person_night','per_item','per_hour','per_month')),
  price                numeric(18,2) NOT NULL DEFAULT 0 CHECK (price >= 0),
  is_mandatory         boolean NOT NULL DEFAULT false, -- resort/cleaning fee auto-added
  is_bookable_online   boolean NOT NULL DEFAULT false,
  inventory_item_id    uuid,
  transaction_code_id  uuid NOT NULL,
  content              jsonb NOT NULL DEFAULT '{}',
  is_active            boolean NOT NULL DEFAULT true,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  created_by text, updated_by text,
  UNIQUE (tenant_id, id),
  UNIQUE (tenant_id, property_id, code),
  FOREIGN KEY (tenant_id, property_id) REFERENCES property (tenant_id, id) ON DELETE CASCADE,
  FOREIGN KEY (tenant_id, inventory_item_id) REFERENCES inventoryitem (tenant_id, id) ON DELETE SET NULL (inventory_item_id),
  FOREIGN KEY (tenant_id, transaction_code_id) REFERENCES transactioncode (tenant_id, id)
);

CREATE TABLE rateplan (
  id                     uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id              uuid NOT NULL,
  property_id            uuid NOT NULL,
  code                   text NOT NULL,
  name                   text NOT NULL,
  parent_rate_plan_id    uuid,                      -- derived rates
  derivation_kind        text NOT NULL DEFAULT 'none' CHECK (derivation_kind IN ('none','percent','amount')),
  derivation_value       numeric(18,4),
  pricing_model          text NOT NULL DEFAULT 'per_unit' CHECK (pricing_model IN ('per_unit','per_person','per_bed','base_plus_extra')),
  meal_plan              text NOT NULL DEFAULT 'room_only' CHECK (meal_plan IN ('room_only','breakfast','half_board','full_board','all_inclusive')),
  cancellation_policy_id uuid NOT NULL,
  payment_policy_id      uuid NOT NULL,
  market_segment_id      uuid,
  price_includes_tax     boolean NOT NULL DEFAULT true,   -- nett vs ++
  is_public              boolean NOT NULL DEFAULT true,
  requires_code          boolean NOT NULL DEFAULT false,  -- corporate / member / promo-only
  restricted_account_ids uuid[] NOT NULL DEFAULT '{}',    -- negotiated rates (validated in app)
  los_pricing            jsonb NOT NULL DEFAULT '[]',     -- [{"min_nights":7,"discount_pct":10}]
  valid_from             date,
  valid_to               date,
  sort_order             integer NOT NULL DEFAULT 0,
  content                jsonb NOT NULL DEFAULT '{}',
  status                 text NOT NULL DEFAULT 'active' CHECK (status IN ('draft','active','inactive','archived')),
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  created_by text, updated_by text,
  UNIQUE (tenant_id, id),
  UNIQUE (tenant_id, property_id, code),
  CHECK (parent_rate_plan_id IS NULL OR parent_rate_plan_id <> id),
  CHECK ((derivation_kind = 'none') = (parent_rate_plan_id IS NULL)),
  FOREIGN KEY (tenant_id, property_id) REFERENCES property (tenant_id, id) ON DELETE CASCADE,
  FOREIGN KEY (tenant_id, parent_rate_plan_id) REFERENCES rateplan (tenant_id, id),
  FOREIGN KEY (tenant_id, cancellation_policy_id) REFERENCES cancellationpolicy (tenant_id, id),
  FOREIGN KEY (tenant_id, payment_policy_id) REFERENCES paymentpolicy (tenant_id, id),
  FOREIGN KEY (tenant_id, market_segment_id) REFERENCES marketsegment (tenant_id, id) ON DELETE SET NULL (market_segment_id)
);

CREATE TABLE rateplanunittype (
  tenant_id     uuid NOT NULL,
  rate_plan_id  uuid NOT NULL,
  unit_type_id  uuid NOT NULL,
  PRIMARY KEY (tenant_id, rate_plan_id, unit_type_id),
  FOREIGN KEY (tenant_id, rate_plan_id) REFERENCES rateplan (tenant_id, id) ON DELETE CASCADE,
  FOREIGN KEY (tenant_id, unit_type_id) REFERENCES unittype (tenant_id, id) ON DELETE CASCADE
);

-- Package inclusions (breakfast in BB rate, spa credit …).
CREATE TABLE rateplanproduct (
  tenant_id          uuid NOT NULL,
  rate_plan_id       uuid NOT NULL,
  product_id         uuid NOT NULL,
  quantity           numeric(10,2) NOT NULL DEFAULT 1,
  allocation_amount  numeric(18,2),                 -- revenue split to the product's department
  PRIMARY KEY (tenant_id, rate_plan_id, product_id),
  FOREIGN KEY (tenant_id, rate_plan_id) REFERENCES rateplan (tenant_id, id) ON DELETE CASCADE,
  FOREIGN KEY (tenant_id, product_id) REFERENCES product (tenant_id, id) ON DELETE CASCADE
);

-- Price per rate plan x unit type x date. Amount = one time unit of the unit
-- type's grain (night, day, hour block, month) starting on stay_date.
CREATE TABLE ratedaily (
  id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id         uuid NOT NULL,
  rate_plan_id      uuid NOT NULL,
  unit_type_id      uuid NOT NULL,
  stay_date         date NOT NULL,
  amount            numeric(18,2) NOT NULL CHECK (amount >= 0),     -- base occupancy price
  occupancy_prices  jsonb NOT NULL DEFAULT '{}',                    -- {"1":450000,"3":650000}
  extra_adult       numeric(18,2),
  extra_child       numeric(18,2),
  source            text NOT NULL DEFAULT 'manual' CHECK (source IN ('manual','bulk','rms','rule','import','derived')),
  updated_at        timestamptz NOT NULL DEFAULT now(),
  updated_by        text,
  UNIQUE (tenant_id, id),
  UNIQUE (tenant_id, rate_plan_id, unit_type_id, stay_date),
  FOREIGN KEY (tenant_id, rate_plan_id) REFERENCES rateplan (tenant_id, id) ON DELETE CASCADE,
  FOREIGN KEY (tenant_id, unit_type_id) REFERENCES unittype (tenant_id, id) ON DELETE CASCADE
);

-- Restrictions. NULL scope column = applies to all (all unit types / rate plans / channels).
CREATE TABLE restriction (
  id                   uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id            uuid NOT NULL,
  property_id          uuid NOT NULL,
  stay_date            date NOT NULL,
  unit_type_id         uuid,
  rate_plan_id         uuid,
  channel_id           uuid,
  stop_sell            boolean NOT NULL DEFAULT false,
  closed_to_arrival    boolean NOT NULL DEFAULT false,
  closed_to_departure  boolean NOT NULL DEFAULT false,
  min_stay_arrival     integer CHECK (min_stay_arrival > 0),
  min_stay_through     integer CHECK (min_stay_through > 0),
  max_stay             integer CHECK (max_stay > 0),
  min_advance_days     integer CHECK (min_advance_days >= 0),
  max_advance_days     integer CHECK (max_advance_days >= 0),
  source               text NOT NULL DEFAULT 'manual' CHECK (source IN ('manual','bulk','rms','rule','import')),
  updated_at           timestamptz NOT NULL DEFAULT now(),
  updated_by           text,
  UNIQUE (tenant_id, id),
  UNIQUE NULLS NOT DISTINCT (tenant_id, property_id, stay_date, unit_type_id, rate_plan_id, channel_id),
  FOREIGN KEY (tenant_id, property_id) REFERENCES property (tenant_id, id) ON DELETE CASCADE,
  FOREIGN KEY (tenant_id, unit_type_id) REFERENCES unittype (tenant_id, id) ON DELETE CASCADE,
  FOREIGN KEY (tenant_id, rate_plan_id) REFERENCES rateplan (tenant_id, id) ON DELETE CASCADE,
  FOREIGN KEY (tenant_id, channel_id) REFERENCES channel (tenant_id, id) ON DELETE CASCADE
);

CREATE TABLE promotion (
  id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id        uuid NOT NULL,
  property_id      uuid,                            -- NULL = all properties
  code             text NOT NULL,                   -- promo code the guest types (stored upper-case)
  name             text NOT NULL,
  discount_kind    text NOT NULL CHECK (discount_kind IN ('percent','amount','free_nights')),
  discount_value   numeric(18,2) NOT NULL CHECK (discount_value >= 0),
  booking_from     date,
  booking_to       date,
  stay_from        date,
  stay_to          date,
  max_uses         integer,
  uses_count       integer NOT NULL DEFAULT 0,
  is_combinable    boolean NOT NULL DEFAULT false,
  conditions       jsonb NOT NULL DEFAULT '{}',     -- {"min_nights":2,"rate_plan_ids":[...],"channels":["direct_web"]}
  is_active        boolean NOT NULL DEFAULT true,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  created_by text, updated_by text,
  UNIQUE (tenant_id, id),
  UNIQUE (tenant_id, code),
  FOREIGN KEY (tenant_id, property_id) REFERENCES property (tenant_id, id) ON DELETE CASCADE
);

-- =============================================================================
-- F. ACCOUNTS (companies, agents, OTAs) & GUESTS
-- =============================================================================

CREATE TABLE account (
  id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id           uuid NOT NULL,
  kind                text NOT NULL CHECK (kind IN ('company','travel_agent','ota','wholesaler','government','group_organizer','other')),
  name                text NOT NULL,
  tax_id              text,
  email               text,
  phone               text,
  billing_address     jsonb NOT NULL DEFAULT '{}',
  is_ar_enabled       boolean NOT NULL DEFAULT false,   -- direct bill / city ledger
  credit_limit        numeric(18,2),
  payment_terms_days  integer,
  commission_pct      numeric(5,2),
  channel_id          uuid,                             -- for kind = 'ota'
  status              text NOT NULL DEFAULT 'active' CHECK (status IN ('active','on_hold','closed')),
  notes               text,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  created_by text, updated_by text,
  UNIQUE (tenant_id, id),
  FOREIGN KEY (tenant_id, channel_id) REFERENCES channel (tenant_id, id) ON DELETE SET NULL (channel_id)
);
CREATE INDEX ix_account_name ON account USING gin (name gin_trgm_ops);

CREATE TABLE guest (
  id                    uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id             uuid NOT NULL,
  full_name             text NOT NULL,              -- many Indonesians have a single name
  given_name            text,
  family_name           text,
  email                 text,
  phone                 text,                       -- E.164
  whatsapp_phone        text,
  nationality           char(2),
  gender                text CHECK (gender IN ('male','female','other','undisclosed')),
  birth_date            date,
  language              text,
  address               jsonb NOT NULL DEFAULT '{}',
  employer_account_id   uuid,
  vip_level             smallint NOT NULL DEFAULT 0 CHECK (vip_level BETWEEN 0 AND 9),
  tags                  text[] NOT NULL DEFAULT '{}',
  is_blacklisted        boolean NOT NULL DEFAULT false,
  blacklist_reason      text,
  notes                 text,
  -- denormalised stats (maintained by events)
  stay_count            integer NOT NULL DEFAULT 0,
  night_count           integer NOT NULL DEFAULT 0,
  total_spend           numeric(18,2) NOT NULL DEFAULT 0,
  last_stay_on          date,
  merged_into_guest_id  uuid,
  anonymized_at         timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  created_by text, updated_by text,
  UNIQUE (tenant_id, id),
  FOREIGN KEY (tenant_id, employer_account_id) REFERENCES account (tenant_id, id) ON DELETE SET NULL (employer_account_id),
  FOREIGN KEY (tenant_id, merged_into_guest_id) REFERENCES guest (tenant_id, id) ON DELETE SET NULL (merged_into_guest_id)
);
CREATE INDEX ix_guest_email ON guest (tenant_id, lower(email)) WHERE email IS NOT NULL;
CREATE INDEX ix_guest_phone ON guest (tenant_id, phone) WHERE phone IS NOT NULL;
CREATE INDEX ix_guest_name_trgm ON guest USING gin (full_name gin_trgm_ops);

-- Identity documents (KTP, passport, KITAS …). Number stored encrypted + hash.
CREATE TABLE guestdocument (
  id                    uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id             uuid NOT NULL,
  guest_id              uuid NOT NULL,
  doc_type              text NOT NULL CHECK (doc_type IN ('ktp','passport','kitas','kitap','sim','visa','marriage_certificate','student_id','other')),
  doc_number_encrypted  bytea,                      -- application-level encryption (KMS)
  doc_number_hash       text,                       -- HMAC for exact-match lookup / dedupe
  doc_number_last4      text,
  issuing_country       char(2),
  issued_on             date,
  expires_on            date,
  visa_type             text,                       -- 'voa','b211','kitas', …
  entry_stamp_date      date,
  scan_document_id      uuid,
  verified_at           timestamptz,
  verified_by           text,
  extracted_by_ai       boolean NOT NULL DEFAULT false,
  retention_until       date,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  created_by text, updated_by text,
  UNIQUE (tenant_id, id),
  FOREIGN KEY (tenant_id, guest_id) REFERENCES guest (tenant_id, id) ON DELETE CASCADE,
  FOREIGN KEY (tenant_id, scan_document_id) REFERENCES document (tenant_id, id) ON DELETE SET NULL (scan_document_id)
);
CREATE INDEX ix_guestdocument_hash ON guestdocument (tenant_id, doc_type, doc_number_hash);

CREATE TABLE guestpreference (
  id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id  uuid NOT NULL,
  guest_id   uuid NOT NULL,
  category   text NOT NULL CHECK (category IN ('unit','bed','pillow','diet','allergy','accessibility','floor','view','communication','other')),
  value      text NOT NULL,
  note       text,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  created_by text, updated_by text,
  UNIQUE (tenant_id, id),
  FOREIGN KEY (tenant_id, guest_id) REFERENCES guest (tenant_id, id) ON DELETE CASCADE
);

-- Consent per purpose and channel (PDP Law / GDPR).
CREATE TABLE guestconsent (
  id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id        uuid NOT NULL,
  guest_id         uuid NOT NULL,
  purpose          text NOT NULL CHECK (purpose IN ('marketing','survey','profiling','ai_processing','cross_border_transfer','data_sharing')),
  channel          text NOT NULL DEFAULT 'any' CHECK (channel IN ('any','email','sms','whatsapp','phone','push')),
  granted          boolean NOT NULL,
  wording_version  text NOT NULL,
  source           text NOT NULL,                   -- 'booking_engine','portal','front_desk','whatsapp_optin'
  captured_at      timestamptz NOT NULL DEFAULT now(),
  withdrawn_at     timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  created_by text, updated_by text,
  UNIQUE (tenant_id, id),
  FOREIGN KEY (tenant_id, guest_id) REFERENCES guest (tenant_id, id) ON DELETE CASCADE
);
CREATE INDEX ix_guestconsent_guest ON guestconsent (tenant_id, guest_id, purpose, channel);

-- =============================================================================
-- G. GROUPS & RESERVATIONS
-- =============================================================================

CREATE TABLE groupblock (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id       uuid NOT NULL,
  property_id     uuid NOT NULL,
  account_id      uuid,
  code            text NOT NULL,
  name            text NOT NULL,
  kind            text NOT NULL DEFAULT 'group' CHECK (kind IN ('group','allotment','wedding','event','buyout')),
  status          text NOT NULL DEFAULT 'tentative' CHECK (status IN ('enquiry','tentative','definite','released','cancelled','completed')),
  arrival_date    date NOT NULL,
  departure_date  date NOT NULL,
  cutoff_date     date,
  release_rule    jsonb NOT NULL DEFAULT '{}',      -- rolling releases
  rate_plan_id    uuid,
  contact         jsonb NOT NULL DEFAULT '{}',
  notes           text,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  created_by text, updated_by text,
  UNIQUE (tenant_id, id),
  UNIQUE (tenant_id, property_id, code),
  CHECK (departure_date > arrival_date),
  FOREIGN KEY (tenant_id, property_id) REFERENCES property (tenant_id, id) ON DELETE CASCADE,
  FOREIGN KEY (tenant_id, account_id) REFERENCES account (tenant_id, id) ON DELETE SET NULL (account_id),
  FOREIGN KEY (tenant_id, rate_plan_id) REFERENCES rateplan (tenant_id, id) ON DELETE SET NULL (rate_plan_id)
);

CREATE TABLE groupblockday (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id       uuid NOT NULL,
  group_block_id  uuid NOT NULL,
  unit_type_id    uuid NOT NULL,
  stay_date       date NOT NULL,
  contracted      integer NOT NULL CHECK (contracted >= 0),
  picked_up       integer NOT NULL DEFAULT 0 CHECK (picked_up >= 0),
  rate_amount     numeric(18,2),
  UNIQUE (tenant_id, id),
  UNIQUE (tenant_id, group_block_id, unit_type_id, stay_date),
  FOREIGN KEY (tenant_id, group_block_id) REFERENCES groupblock (tenant_id, id) ON DELETE CASCADE,
  FOREIGN KEY (tenant_id, unit_type_id) REFERENCES unittype (tenant_id, id)
);

CREATE TABLE reservation (
  id                         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id                  uuid NOT NULL,
  property_id                uuid NOT NULL,
  confirmation_no            text NOT NULL,
  status                     text NOT NULL DEFAULT 'confirmed' CHECK (status IN (
                               'quote','tentative','waitlisted','confirmed','guaranteed',
                               'in_house','checked_out','cancelled','no_show','expired')),
  option_expires_at          timestamptz,           -- quote / tentative / unpaid-DP hold
  booker_guest_id            uuid,
  company_account_id         uuid,
  agent_account_id           uuid,
  group_block_id             uuid,
  channel_id                 uuid NOT NULL,
  channel_reference          text,                  -- OTA booking id
  market_segment_id          uuid,
  source_detail              jsonb NOT NULL DEFAULT '{}',   -- {"utm_source":"google","landing":"free_booking_link"}
  arrival_date               date NOT NULL,         -- min over reservation units
  departure_date             date NOT NULL,         -- max over reservation units
  adults                     integer NOT NULL DEFAULT 1 CHECK (adults >= 0),
  children                   integer NOT NULL DEFAULT 0 CHECK (children >= 0),
  currency                   char(3) NOT NULL DEFAULT 'IDR',
  total_amount               numeric(18,2) NOT NULL DEFAULT 0,
  total_tax                  numeric(18,2) NOT NULL DEFAULT 0,
  paid_amount                numeric(18,2) NOT NULL DEFAULT 0,
  balance_due                numeric(18,2) NOT NULL DEFAULT 0,
  commission_amount          numeric(18,2),
  payment_collect_model      text NOT NULL DEFAULT 'property' CHECK (payment_collect_model IN ('property','channel','mixed')),
  guarantee_kind             text NOT NULL DEFAULT 'none' CHECK (guarantee_kind IN ('none','card','deposit','full_prepay','company','voucher','ota')),
  cancellation_policy_snapshot jsonb NOT NULL DEFAULT '{}',  -- policy as booked (BR-06)
  payment_policy_snapshot    jsonb NOT NULL DEFAULT '{}',
  promotion_id               uuid,
  eta                        time,
  transport                  jsonb NOT NULL DEFAULT '{}',   -- flight, vehicle plate, RV length
  special_requests           text,
  internal_notes             text,
  language                   text,
  booked_at                  timestamptz NOT NULL DEFAULT now(),
  booked_by                  text,
  cancelled_at               timestamptz,
  cancel_reason_id           uuid,
  cancellation_fee           numeric(18,2),
  is_complimentary           boolean NOT NULL DEFAULT false,
  is_house_use               boolean NOT NULL DEFAULT false,
  is_owner_stay              boolean NOT NULL DEFAULT false,
  version                    integer NOT NULL DEFAULT 1,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  created_by text, updated_by text,
  UNIQUE (tenant_id, id),
  UNIQUE (tenant_id, confirmation_no),
  CHECK (departure_date >= arrival_date),
  FOREIGN KEY (tenant_id, property_id) REFERENCES property (tenant_id, id),
  FOREIGN KEY (tenant_id, booker_guest_id) REFERENCES guest (tenant_id, id) ON DELETE SET NULL (booker_guest_id),
  FOREIGN KEY (tenant_id, company_account_id) REFERENCES account (tenant_id, id) ON DELETE SET NULL (company_account_id),
  FOREIGN KEY (tenant_id, agent_account_id) REFERENCES account (tenant_id, id) ON DELETE SET NULL (agent_account_id),
  FOREIGN KEY (tenant_id, group_block_id) REFERENCES groupblock (tenant_id, id) ON DELETE SET NULL (group_block_id),
  FOREIGN KEY (tenant_id, channel_id) REFERENCES channel (tenant_id, id),
  FOREIGN KEY (tenant_id, market_segment_id) REFERENCES marketsegment (tenant_id, id) ON DELETE SET NULL (market_segment_id),
  FOREIGN KEY (tenant_id, promotion_id) REFERENCES promotion (tenant_id, id) ON DELETE SET NULL (promotion_id),
  FOREIGN KEY (tenant_id, cancel_reason_id) REFERENCES reasoncode (tenant_id, id) ON DELETE SET NULL (cancel_reason_id)
);
CREATE INDEX ix_reservation_dates ON reservation (tenant_id, property_id, arrival_date, departure_date);
CREATE INDEX ix_reservation_status ON reservation (tenant_id, property_id, status);
CREATE UNIQUE INDEX ux_reservation_channel_ref ON reservation (tenant_id, channel_id, channel_reference)
  WHERE channel_reference IS NOT NULL;

-- One line per unit (room/bed/villa/pitch/slot) in a reservation.
-- The EXCLUDE constraint makes it impossible to assign the same unit to two
-- overlapping active stays (including turnaround buffer).
CREATE TABLE reservationunit (
  id                    uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id             uuid NOT NULL,
  reservation_id        uuid NOT NULL,
  property_id           uuid NOT NULL,
  unit_type_id          uuid NOT NULL,
  unit_id               uuid,                       -- NULL until assigned
  rate_plan_id          uuid NOT NULL,
  status                text NOT NULL DEFAULT 'confirmed' CHECK (status IN (
                          'quote','tentative','waitlisted','confirmed','guaranteed',
                          'in_house','checked_out','cancelled','no_show','expired')),
  arrival_date          date NOT NULL,
  departure_date        date NOT NULL,
  start_at              timestamptz NOT NULL,       -- arrival date + check-in time (or hour-block start)
  end_at                timestamptz NOT NULL,       -- departure date + check-out time (or block end)
  blocked_until         timestamptz NOT NULL,       -- end_at + turnaround buffer (set by app)
  occupancy             tstzrange GENERATED ALWAYS AS (tstzrange(start_at, blocked_until, '[)')) STORED,
  adults                integer NOT NULL DEFAULT 1 CHECK (adults >= 0),
  children              integer NOT NULL DEFAULT 0 CHECK (children >= 0),
  infants               integer NOT NULL DEFAULT 0 CHECK (infants >= 0),
  child_ages            integer[] NOT NULL DEFAULT '{}',
  is_assignment_locked  boolean NOT NULL DEFAULT false,   -- "do not move"
  upgrade_reason_id     uuid,
  total_amount          numeric(18,2) NOT NULL DEFAULT 0,
  checked_in_at         timestamptz,
  checked_in_by         text,
  checked_out_at        timestamptz,
  checked_out_by        text,
  version               integer NOT NULL DEFAULT 1,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  created_by text, updated_by text,
  UNIQUE (tenant_id, id),
  CHECK (departure_date >= arrival_date),
  CHECK (end_at > start_at AND blocked_until >= end_at),
  FOREIGN KEY (tenant_id, reservation_id) REFERENCES reservation (tenant_id, id) ON DELETE CASCADE,
  FOREIGN KEY (tenant_id, property_id) REFERENCES property (tenant_id, id),
  FOREIGN KEY (tenant_id, unit_type_id) REFERENCES unittype (tenant_id, id),
  FOREIGN KEY (tenant_id, unit_id) REFERENCES unit (tenant_id, id) ON DELETE SET NULL (unit_id),
  FOREIGN KEY (tenant_id, rate_plan_id) REFERENCES rateplan (tenant_id, id),
  FOREIGN KEY (tenant_id, upgrade_reason_id) REFERENCES reasoncode (tenant_id, id) ON DELETE SET NULL (upgrade_reason_id),
  CONSTRAINT ex_reservationunit_no_double_booking EXCLUDE USING gist (
    unit_id WITH =, occupancy WITH &&
  ) WHERE (unit_id IS NOT NULL AND status IN ('tentative','confirmed','guaranteed','in_house'))
);
CREATE INDEX ix_reservationunit_reservation ON reservationunit (tenant_id, reservation_id);
CREATE INDEX ix_reservationunit_dates ON reservationunit (tenant_id, property_id, arrival_date, departure_date);
CREATE INDEX ix_reservationunit_unit ON reservationunit (tenant_id, unit_id) WHERE unit_id IS NOT NULL;

-- Occupants per reservation unit.
CREATE TABLE reservationguest (
  id                    uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id             uuid NOT NULL,
  reservation_unit_id   uuid NOT NULL,
  guest_id              uuid NOT NULL,
  is_primary            boolean NOT NULL DEFAULT false,
  age_category          text NOT NULL DEFAULT 'adult' CHECK (age_category IN ('adult','teen','child','infant')),
  registration_status   text NOT NULL DEFAULT 'pending' CHECK (registration_status IN ('pending','pre_checked_in','registered')),
  registration_card_id  uuid,                       -- signed card (document)
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  created_by text, updated_by text,
  UNIQUE (tenant_id, id),
  UNIQUE (tenant_id, reservation_unit_id, guest_id),
  FOREIGN KEY (tenant_id, reservation_unit_id) REFERENCES reservationunit (tenant_id, id) ON DELETE CASCADE,
  FOREIGN KEY (tenant_id, guest_id) REFERENCES guest (tenant_id, id),
  FOREIGN KEY (tenant_id, registration_card_id) REFERENCES document (tenant_id, id) ON DELETE SET NULL (registration_card_id)
);
CREATE UNIQUE INDEX ux_reservationguest_primary ON reservationguest (tenant_id, reservation_unit_id) WHERE is_primary;

-- Price per stay date, frozen at booking (BR-04). Night audit posts from here.
CREATE TABLE reservationdailyrate (
  id                    uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id             uuid NOT NULL,
  reservation_unit_id   uuid NOT NULL,
  stay_date             date NOT NULL,
  rate_plan_id          uuid NOT NULL,
  unit_type_id          uuid NOT NULL,
  amount                numeric(18,2) NOT NULL CHECK (amount >= 0),
  discount_amount       numeric(18,2) NOT NULL DEFAULT 0,
  is_price_locked       boolean NOT NULL DEFAULT false,
  posted_at             timestamptz,                -- set when night audit posts the charge
  UNIQUE (tenant_id, id),
  UNIQUE (tenant_id, reservation_unit_id, stay_date),
  FOREIGN KEY (tenant_id, reservation_unit_id) REFERENCES reservationunit (tenant_id, id) ON DELETE CASCADE,
  FOREIGN KEY (tenant_id, rate_plan_id) REFERENCES rateplan (tenant_id, id),
  FOREIGN KEY (tenant_id, unit_type_id) REFERENCES unittype (tenant_id, id)
);

-- Extras booked with the stay (breakfast, parking, cot, transfer …).
CREATE TABLE reservationproduct (
  id                    uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id             uuid NOT NULL,
  reservation_id        uuid NOT NULL,
  reservation_unit_id   uuid,
  product_id            uuid NOT NULL,
  quantity              numeric(10,2) NOT NULL DEFAULT 1 CHECK (quantity > 0),
  unit_price            numeric(18,2) NOT NULL CHECK (unit_price >= 0),
  start_date            date,
  end_date              date,
  is_included_in_rate   boolean NOT NULL DEFAULT false,
  status                text NOT NULL DEFAULT 'active' CHECK (status IN ('active','cancelled','consumed')),
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  created_by text, updated_by text,
  UNIQUE (tenant_id, id),
  FOREIGN KEY (tenant_id, reservation_id) REFERENCES reservation (tenant_id, id) ON DELETE CASCADE,
  FOREIGN KEY (tenant_id, reservation_unit_id) REFERENCES reservationunit (tenant_id, id) ON DELETE CASCADE,
  FOREIGN KEY (tenant_id, product_id) REFERENCES product (tenant_id, id)
);

-- Notes, check-in alerts and follow-up traces.
CREATE TABLE reservationtrace (
  id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id        uuid NOT NULL,
  reservation_id   uuid NOT NULL,
  kind             text NOT NULL CHECK (kind IN ('note','alert','trace')),
  department       text,
  body             text NOT NULL,
  due_at           timestamptz,
  show_at_checkin  boolean NOT NULL DEFAULT false,
  resolved_at      timestamptz,
  resolved_by      text,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  created_by text, updated_by text,
  UNIQUE (tenant_id, id),
  FOREIGN KEY (tenant_id, reservation_id) REFERENCES reservation (tenant_id, id) ON DELETE CASCADE
);

-- Field-level change history (FR-RES-023). Append-only.
CREATE TABLE reservationchange (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id       uuid NOT NULL,
  reservation_id  uuid NOT NULL,
  changed_at      timestamptz NOT NULL DEFAULT now(),
  actor           text,
  source          text NOT NULL CHECK (source IN ('staff','guest','channel','api','system','ai')),
  action          text NOT NULL,                    -- 'created','modified','cancelled','checked_in','room_moved',…
  changes         jsonb NOT NULL DEFAULT '{}',      -- {"field":{"old":..,"new":..}}
  UNIQUE (tenant_id, id),
  FOREIGN KEY (tenant_id, reservation_id) REFERENCES reservation (tenant_id, id) ON DELETE CASCADE
);
CREATE INDEX ix_reservationchange_res ON reservationchange (tenant_id, reservation_id, changed_at);

-- =============================================================================
-- H. FOLIOS, POSTINGS, INVOICES, END-OF-DAY
-- =============================================================================

CREATE TABLE folio (
  id                    uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id             uuid NOT NULL,
  property_id           uuid NOT NULL,
  kind                  text NOT NULL CHECK (kind IN ('guest','master','house','passer_by','ar','deposit')),
  reservation_id        uuid,
  reservation_unit_id   uuid,
  group_block_id        uuid,
  guest_id              uuid,
  account_id            uuid,
  window_no             smallint NOT NULL DEFAULT 1 CHECK (window_no BETWEEN 1 AND 9),
  status                text NOT NULL DEFAULT 'open' CHECK (status IN ('open','settled','closed','transferred')),
  currency              char(3) NOT NULL DEFAULT 'IDR',
  balance               numeric(18,2) NOT NULL DEFAULT 0,   -- denormalised; truth = sum(foliotransaction)
  credit_limit          numeric(18,2),
  closed_at             timestamptz,
  version               integer NOT NULL DEFAULT 1,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  created_by text, updated_by text,
  UNIQUE (tenant_id, id),
  CHECK (kind <> 'ar' OR account_id IS NOT NULL),
  FOREIGN KEY (tenant_id, property_id) REFERENCES property (tenant_id, id),
  FOREIGN KEY (tenant_id, reservation_id) REFERENCES reservation (tenant_id, id),
  FOREIGN KEY (tenant_id, reservation_unit_id) REFERENCES reservationunit (tenant_id, id),
  FOREIGN KEY (tenant_id, group_block_id) REFERENCES groupblock (tenant_id, id),
  FOREIGN KEY (tenant_id, guest_id) REFERENCES guest (tenant_id, id),
  FOREIGN KEY (tenant_id, account_id) REFERENCES account (tenant_id, id)
);
CREATE INDEX ix_folio_reservation ON folio (tenant_id, reservation_id) WHERE reservation_id IS NOT NULL;
CREATE INDEX ix_folio_account_open ON folio (tenant_id, account_id) WHERE account_id IS NOT NULL AND status = 'open';

ALTER TABLE groupblock ADD COLUMN master_folio_id uuid,
  ADD FOREIGN KEY (tenant_id, master_folio_id) REFERENCES folio (tenant_id, id) ON DELETE SET NULL (master_folio_id);

-- Charge routing (e.g. accommodation -> company folio, extras -> guest folio).
CREATE TABLE routinginstruction (
  id                   uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id            uuid NOT NULL,
  reservation_id       uuid NOT NULL,
  target_folio_id      uuid NOT NULL,
  transaction_code_id  uuid,                         -- one of code / department must be set
  department           text,
  valid_from           date,
  valid_to             date,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  created_by text, updated_by text,
  UNIQUE (tenant_id, id),
  CHECK (transaction_code_id IS NOT NULL OR department IS NOT NULL),
  FOREIGN KEY (tenant_id, reservation_id) REFERENCES reservation (tenant_id, id) ON DELETE CASCADE,
  FOREIGN KEY (tenant_id, target_folio_id) REFERENCES folio (tenant_id, id) ON DELETE CASCADE,
  FOREIGN KEY (tenant_id, transaction_code_id) REFERENCES transactioncode (tenant_id, id) ON DELETE CASCADE
);

CREATE TABLE cashiershift (
  id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id        uuid NOT NULL,
  property_id      uuid NOT NULL,
  staff_member_id  uuid NOT NULL,
  outlet_code      text,                             -- front desk / bar / shop
  business_date    date NOT NULL,
  opened_at        timestamptz NOT NULL DEFAULT now(),
  closed_at        timestamptz,
  opening_float    numeric(18,2) NOT NULL DEFAULT 0,
  expected_cash    numeric(18,2),
  counted_cash     numeric(18,2),
  variance         numeric(18,2) GENERATED ALWAYS AS (counted_cash - expected_cash) STORED,
  status           text NOT NULL DEFAULT 'open' CHECK (status IN ('open','closed','reconciled')),
  notes            text,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  created_by text, updated_by text,
  UNIQUE (tenant_id, id),
  FOREIGN KEY (tenant_id, property_id) REFERENCES property (tenant_id, id),
  FOREIGN KEY (tenant_id, staff_member_id) REFERENCES staffmember (tenant_id, id)
);

-- =============================================================================
-- I. PAYMENTS
-- =============================================================================

CREATE TABLE paymentgatewayaccount (
  id                     uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id              uuid NOT NULL,
  property_id            uuid,                        -- NULL = tenant-wide
  provider               text NOT NULL CHECK (provider IN ('midtrans','xendit','doku','faspay','stripe','adyen','manual_bank','other')),
  display_name           text NOT NULL,
  merchant_ref           text,
  credentials_secret_ref text,                        -- secret-manager key; never the key itself
  supported_methods      text[] NOT NULL DEFAULT '{}',-- 'qris','virtual_account','ewallet','card'
  settlement_currency    char(3) NOT NULL DEFAULT 'IDR',
  is_default             boolean NOT NULL DEFAULT false,
  status                 text NOT NULL DEFAULT 'active' CHECK (status IN ('setup','active','disabled','error')),
  settings               jsonb NOT NULL DEFAULT '{}',
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  created_by text, updated_by text,
  UNIQUE (tenant_id, id),
  FOREIGN KEY (tenant_id, property_id) REFERENCES property (tenant_id, id) ON DELETE CASCADE
);

-- Stored, tokenised instrument (card token, OTA virtual card, e-wallet binding). No PAN ever.
CREATE TABLE paymentinstrument (
  id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id           uuid NOT NULL,
  gateway_account_id  uuid NOT NULL,
  guest_id            uuid,
  account_id          uuid,
  reservation_id      uuid,                          -- OTA VCC belongs to one reservation
  kind                text NOT NULL CHECK (kind IN ('card','network_token','ewallet','bank_account','ota_vcc')),
  token               text NOT NULL,
  brand               text,
  last4               text,
  expiry_month        smallint CHECK (expiry_month BETWEEN 1 AND 12),
  expiry_year         smallint,
  holder_name         text,
  vcc_activation_on   date,
  vcc_amount          numeric(18,2),
  consent_scope       text[] NOT NULL DEFAULT '{}',  -- 'guarantee','incidentals','scheduled_payments'
  status              text NOT NULL DEFAULT 'active' CHECK (status IN ('active','expired','revoked')),
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  created_by text, updated_by text,
  UNIQUE (tenant_id, id),
  FOREIGN KEY (tenant_id, gateway_account_id) REFERENCES paymentgatewayaccount (tenant_id, id),
  FOREIGN KEY (tenant_id, guest_id) REFERENCES guest (tenant_id, id) ON DELETE SET NULL (guest_id),
  FOREIGN KEY (tenant_id, account_id) REFERENCES account (tenant_id, id) ON DELETE SET NULL (account_id),
  FOREIGN KEY (tenant_id, reservation_id) REFERENCES reservation (tenant_id, id) ON DELETE SET NULL (reservation_id)
);

-- Shareable pay link (sent over WhatsApp/email). Token goes in the URL path.
CREATE TABLE paymentlink (
  id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id           uuid NOT NULL,
  property_id         uuid NOT NULL,
  reservation_id      uuid,
  folio_id            uuid,
  token_hash          text NOT NULL,
  amount              numeric(18,2) NOT NULL CHECK (amount > 0),
  currency            char(3) NOT NULL DEFAULT 'IDR',
  description         text,
  allowed_methods     text[] NOT NULL DEFAULT '{}',
  save_instrument     boolean NOT NULL DEFAULT false,
  expires_at          timestamptz NOT NULL,
  status              text NOT NULL DEFAULT 'active' CHECK (status IN ('active','paid','expired','cancelled')),
  sent_via            text CHECK (sent_via IN ('whatsapp','email','sms','copied')),
  paid_at             timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  created_by text, updated_by text,
  UNIQUE (tenant_id, id),
  UNIQUE (token_hash),
  FOREIGN KEY (tenant_id, property_id) REFERENCES property (tenant_id, id),
  FOREIGN KEY (tenant_id, reservation_id) REFERENCES reservation (tenant_id, id) ON DELETE SET NULL (reservation_id),
  FOREIGN KEY (tenant_id, folio_id) REFERENCES folio (tenant_id, id) ON DELETE SET NULL (folio_id)
);

-- Deposit / balance / instalment schedule (DP 50% culture).
CREATE TABLE paymentschedule (
  id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id        uuid NOT NULL,
  reservation_id   uuid NOT NULL,
  sequence         smallint NOT NULL,
  due_at           timestamptz NOT NULL,
  amount           numeric(18,2) NOT NULL CHECK (amount > 0),
  description      text,
  auto_charge      boolean NOT NULL DEFAULT false,
  instrument_id    uuid,
  payment_link_id  uuid,
  status           text NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','paid','overdue','failed','waived','cancelled')),
  attempts         integer NOT NULL DEFAULT 0,
  last_attempt_at  timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  created_by text, updated_by text,
  UNIQUE (tenant_id, id),
  UNIQUE (tenant_id, reservation_id, sequence),
  FOREIGN KEY (tenant_id, reservation_id) REFERENCES reservation (tenant_id, id) ON DELETE CASCADE,
  FOREIGN KEY (tenant_id, instrument_id) REFERENCES paymentinstrument (tenant_id, id) ON DELETE SET NULL (instrument_id),
  FOREIGN KEY (tenant_id, payment_link_id) REFERENCES paymentlink (tenant_id, id) ON DELETE SET NULL (payment_link_id)
);
CREATE INDEX ix_paymentschedule_due ON paymentschedule (tenant_id, due_at) WHERE status IN ('pending','overdue','failed');

CREATE TABLE payment (
  id                    uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id             uuid NOT NULL,
  property_id           uuid NOT NULL,
  folio_id              uuid,
  reservation_id        uuid,
  gateway_account_id    uuid,
  instrument_id         uuid,
  payment_link_id       uuid,
  payment_schedule_id   uuid,
  refund_of_payment_id  uuid,
  direction             text NOT NULL DEFAULT 'inbound' CHECK (direction IN ('inbound','refund')),
  method                text NOT NULL CHECK (method IN ('qris','virtual_account','ewallet','card','bank_transfer','cash','voucher','ota_vcc','direct_bill','points','other')),
  method_detail         text,                       -- 'BCA','GoPay','VISA'
  status                text NOT NULL DEFAULT 'pending' CHECK (status IN (
                          'pending','requires_action','authorized','captured','partially_refunded',
                          'refunded','failed','cancelled','expired','awaiting_verification')),
  amount                numeric(18,2) NOT NULL CHECK (amount > 0),
  currency              char(3) NOT NULL DEFAULT 'IDR',
  authorized_amount     numeric(18,2) NOT NULL DEFAULT 0,
  captured_amount       numeric(18,2) NOT NULL DEFAULT 0,
  refunded_amount       numeric(18,2) NOT NULL DEFAULT 0,
  fee_amount            numeric(18,2),
  gateway_reference     text,
  idempotency_key       text NOT NULL,
  authorization_expires_at timestamptz,
  captured_at           timestamptz,
  cashier_shift_id      uuid,
  failure_reason        text,
  metadata              jsonb NOT NULL DEFAULT '{}',
  version               integer NOT NULL DEFAULT 1,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  created_by text, updated_by text,
  UNIQUE (tenant_id, id),
  UNIQUE (tenant_id, idempotency_key),
  CHECK (captured_amount <= authorized_amount OR authorized_amount = 0),
  CHECK (refunded_amount <= captured_amount OR direction = 'refund'),
  CHECK ((direction = 'refund') = (refund_of_payment_id IS NOT NULL)),
  FOREIGN KEY (tenant_id, property_id) REFERENCES property (tenant_id, id),
  FOREIGN KEY (tenant_id, folio_id) REFERENCES folio (tenant_id, id),
  FOREIGN KEY (tenant_id, reservation_id) REFERENCES reservation (tenant_id, id),
  FOREIGN KEY (tenant_id, gateway_account_id) REFERENCES paymentgatewayaccount (tenant_id, id),
  FOREIGN KEY (tenant_id, instrument_id) REFERENCES paymentinstrument (tenant_id, id),
  FOREIGN KEY (tenant_id, payment_link_id) REFERENCES paymentlink (tenant_id, id),
  FOREIGN KEY (tenant_id, payment_schedule_id) REFERENCES paymentschedule (tenant_id, id),
  FOREIGN KEY (tenant_id, refund_of_payment_id) REFERENCES payment (tenant_id, id),
  FOREIGN KEY (tenant_id, cashier_shift_id) REFERENCES cashiershift (tenant_id, id)
);
CREATE INDEX ix_payment_reservation ON payment (tenant_id, reservation_id) WHERE reservation_id IS NOT NULL;
CREATE INDEX ix_payment_gateway_ref ON payment (tenant_id, gateway_reference) WHERE gateway_reference IS NOT NULL;

-- Raw gateway callbacks / webhooks (append-only).
CREATE TABLE paymentevent (
  id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id         uuid NOT NULL,
  payment_id        uuid,
  gateway_account_id uuid NOT NULL,
  gateway_event_id  text NOT NULL,
  event_type        text NOT NULL,
  status            text,
  raw               jsonb NOT NULL,
  signature_valid   boolean NOT NULL,
  received_at       timestamptz NOT NULL DEFAULT now(),
  processed_at      timestamptz,
  UNIQUE (tenant_id, id),
  UNIQUE (tenant_id, gateway_account_id, gateway_event_id),
  FOREIGN KEY (tenant_id, payment_id) REFERENCES payment (tenant_id, id),
  FOREIGN KEY (tenant_id, gateway_account_id) REFERENCES paymentgatewayaccount (tenant_id, id)
);

-- Imported bank statement lines (manual transfers without VA).
CREATE TABLE bankstatementline (
  id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id           uuid NOT NULL,
  property_id         uuid NOT NULL,
  bank_code           text NOT NULL,                -- 'BCA','MANDIRI','BRI','BNI'
  account_masked      text NOT NULL,
  booked_on           date NOT NULL,
  amount              numeric(18,2) NOT NULL,
  currency            char(3) NOT NULL DEFAULT 'IDR',
  description         text,
  reference           text,
  source_document_id  uuid,
  matched_payment_id  uuid,
  match_status        text NOT NULL DEFAULT 'unmatched' CHECK (match_status IN ('unmatched','matched','ignored')),
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  created_by text, updated_by text,
  UNIQUE (tenant_id, id),
  FOREIGN KEY (tenant_id, property_id) REFERENCES property (tenant_id, id),
  FOREIGN KEY (tenant_id, source_document_id) REFERENCES document (tenant_id, id) ON DELETE SET NULL (source_document_id),
  FOREIGN KEY (tenant_id, matched_payment_id) REFERENCES payment (tenant_id, id) ON DELETE SET NULL (matched_payment_id)
);

-- Guest-submitted "bukti transfer" screenshot, AI-extracted and matched.
CREATE TABLE transferproof (
  id                     uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id              uuid NOT NULL,
  property_id            uuid NOT NULL,
  reservation_id         uuid,
  payment_id             uuid,
  document_id            uuid NOT NULL,
  submitted_via          text NOT NULL CHECK (submitted_via IN ('whatsapp','portal','email','staff_upload')),
  extracted              jsonb NOT NULL DEFAULT '{}',  -- {"bank":"BCA","amount":1500000,"date":"…","ref":"…","sender":"…"}
  extraction_confidence  numeric(4,3),
  match_status           text NOT NULL DEFAULT 'pending' CHECK (match_status IN (
                           'pending','matched','amount_mismatch','not_found','suspected_tampered',
                           'manually_confirmed','rejected')),
  bank_statement_line_id uuid,
  reviewed_by            text,
  reviewed_at            timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  created_by text, updated_by text,
  UNIQUE (tenant_id, id),
  FOREIGN KEY (tenant_id, property_id) REFERENCES property (tenant_id, id),
  FOREIGN KEY (tenant_id, reservation_id) REFERENCES reservation (tenant_id, id) ON DELETE SET NULL (reservation_id),
  FOREIGN KEY (tenant_id, payment_id) REFERENCES payment (tenant_id, id) ON DELETE SET NULL (payment_id),
  FOREIGN KEY (tenant_id, document_id) REFERENCES document (tenant_id, id),
  FOREIGN KEY (tenant_id, bank_statement_line_id) REFERENCES bankstatementline (tenant_id, id) ON DELETE SET NULL (bank_statement_line_id)
);

CREATE TABLE settlement (
  id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id           uuid NOT NULL,
  gateway_account_id  uuid NOT NULL,
  settlement_ref      text NOT NULL,
  settled_on          date NOT NULL,
  currency            char(3) NOT NULL,
  gross_amount        numeric(18,2) NOT NULL,
  fee_amount          numeric(18,2) NOT NULL DEFAULT 0,
  net_amount          numeric(18,2) NOT NULL,
  status              text NOT NULL DEFAULT 'imported' CHECK (status IN ('imported','reconciled','exceptions')),
  source_document_id  uuid,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  created_by text, updated_by text,
  UNIQUE (tenant_id, id),
  UNIQUE (tenant_id, gateway_account_id, settlement_ref),
  FOREIGN KEY (tenant_id, gateway_account_id) REFERENCES paymentgatewayaccount (tenant_id, id),
  FOREIGN KEY (tenant_id, source_document_id) REFERENCES document (tenant_id, id) ON DELETE SET NULL (source_document_id)
);

CREATE TABLE settlementline (
  id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id          uuid NOT NULL,
  settlement_id      uuid NOT NULL,
  payment_id         uuid,
  gateway_reference  text NOT NULL,
  amount             numeric(18,2) NOT NULL,
  fee_amount         numeric(18,2) NOT NULL DEFAULT 0,
  match_status       text NOT NULL DEFAULT 'unmatched' CHECK (match_status IN ('unmatched','matched','amount_mismatch','ignored')),
  UNIQUE (tenant_id, id),
  FOREIGN KEY (tenant_id, settlement_id) REFERENCES settlement (tenant_id, id) ON DELETE CASCADE,
  FOREIGN KEY (tenant_id, payment_id) REFERENCES payment (tenant_id, id) ON DELETE SET NULL (payment_id)
);

CREATE TABLE chargeback (
  id                     uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id              uuid NOT NULL,
  payment_id             uuid NOT NULL,
  reason_code            text,
  amount                 numeric(18,2) NOT NULL,
  status                 text NOT NULL DEFAULT 'open' CHECK (status IN ('open','evidence_submitted','won','lost','accepted')),
  respond_by             date,
  evidence_document_ids  uuid[] NOT NULL DEFAULT '{}',
  outcome_note           text,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  created_by text, updated_by text,
  UNIQUE (tenant_id, id),
  FOREIGN KEY (tenant_id, payment_id) REFERENCES payment (tenant_id, id)
);

-- Ledger postings. APPEND-ONLY: corrections are new rows (void / adjustment).
CREATE TABLE foliotransaction (
  id                       uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id                uuid NOT NULL,
  folio_id                 uuid NOT NULL,
  property_id              uuid NOT NULL,
  business_date            date NOT NULL,
  posted_at                timestamptz NOT NULL DEFAULT now(),
  transaction_code_id      uuid NOT NULL,
  kind                     text NOT NULL CHECK (kind IN ('charge','tax','payment','refund','deposit','adjustment','void','transfer_in','transfer_out')),
  description              text NOT NULL,
  quantity                 numeric(10,2) NOT NULL DEFAULT 1,
  unit_price               numeric(18,2),
  amount                   numeric(18,2) NOT NULL,          -- signed: charges +, payments −
  currency                 char(3) NOT NULL DEFAULT 'IDR',
  parent_transaction_id    uuid,                            -- tax/service line -> its charge
  reverses_transaction_id  uuid,                            -- void/adjustment target
  transfer_counterpart_id  uuid,
  tax_rule_id              uuid,
  reservation_daily_rate_id uuid,
  reservation_product_id   uuid,
  payment_id               uuid,
  reason_code_id           uuid,
  cashier_shift_id         uuid,
  source                   text NOT NULL CHECK (source IN ('night_audit','manual','pos','channel','payment','system','import')),
  source_ref               text,
  posted_by                text,
  UNIQUE (tenant_id, id),
  FOREIGN KEY (tenant_id, folio_id) REFERENCES folio (tenant_id, id),
  FOREIGN KEY (tenant_id, property_id) REFERENCES property (tenant_id, id),
  FOREIGN KEY (tenant_id, transaction_code_id) REFERENCES transactioncode (tenant_id, id),
  FOREIGN KEY (tenant_id, parent_transaction_id) REFERENCES foliotransaction (tenant_id, id),
  FOREIGN KEY (tenant_id, reverses_transaction_id) REFERENCES foliotransaction (tenant_id, id),
  FOREIGN KEY (tenant_id, transfer_counterpart_id) REFERENCES foliotransaction (tenant_id, id),
  FOREIGN KEY (tenant_id, tax_rule_id) REFERENCES taxrule (tenant_id, id),
  FOREIGN KEY (tenant_id, reservation_daily_rate_id) REFERENCES reservationdailyrate (tenant_id, id),
  FOREIGN KEY (tenant_id, reservation_product_id) REFERENCES reservationproduct (tenant_id, id),
  FOREIGN KEY (tenant_id, payment_id) REFERENCES payment (tenant_id, id),
  FOREIGN KEY (tenant_id, reason_code_id) REFERENCES reasoncode (tenant_id, id),
  FOREIGN KEY (tenant_id, cashier_shift_id) REFERENCES cashiershift (tenant_id, id)
);
CREATE INDEX ix_foliotransaction_folio ON foliotransaction (tenant_id, folio_id, posted_at);
CREATE INDEX ix_foliotransaction_bizdate ON foliotransaction (tenant_id, property_id, business_date);
-- One room charge per daily rate (night audit idempotency).
CREATE UNIQUE INDEX ux_foliotransaction_dailyrate ON foliotransaction (tenant_id, reservation_daily_rate_id)
  WHERE reservation_daily_rate_id IS NOT NULL AND kind = 'charge';

-- Gapless numbering per legal entity + series (lock row FOR UPDATE when issuing).
CREATE TABLE documentsequence (
  id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id        uuid NOT NULL,
  legal_entity_id  uuid NOT NULL,
  series           text NOT NULL CHECK (series IN ('invoice','credit_note','receipt','deposit_invoice','owner_statement','work_order','quote')),
  period_key       text NOT NULL DEFAULT '',         -- '' (never reset) or '2026' / '2026-11'
  prefix           text NOT NULL DEFAULT '',
  next_number      bigint NOT NULL DEFAULT 1 CHECK (next_number > 0),
  padding          smallint NOT NULL DEFAULT 6,
  updated_at       timestamptz NOT NULL DEFAULT now(),
  UNIQUE (tenant_id, id),
  UNIQUE (tenant_id, legal_entity_id, series, period_key),
  FOREIGN KEY (tenant_id, legal_entity_id) REFERENCES legalentity (tenant_id, id)
);

CREATE TABLE invoice (
  id                         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id                  uuid NOT NULL,
  legal_entity_id            uuid NOT NULL,
  property_id                uuid NOT NULL,
  folio_id                   uuid NOT NULL,
  kind                       text NOT NULL CHECK (kind IN ('invoice','credit_note','deposit_invoice','receipt')),
  series                     text NOT NULL,
  number                     text,                   -- assigned at issue
  credit_note_for_invoice_id uuid,
  status                     text NOT NULL DEFAULT 'draft' CHECK (status IN ('draft','issued','cancelled_draft')),
  business_date              date,
  issued_at                  timestamptz,
  account_id                 uuid,
  guest_id                   uuid,
  bill_to                    jsonb NOT NULL DEFAULT '{}',   -- addressee snapshot (name, tax id, address)
  currency                   char(3) NOT NULL DEFAULT 'IDR',
  subtotal                   numeric(18,2) NOT NULL DEFAULT 0,
  tax_total                  numeric(18,2) NOT NULL DEFAULT 0,
  total                      numeric(18,2) NOT NULL DEFAULT 0,
  due_on                     date,
  paid_amount                numeric(18,2) NOT NULL DEFAULT 0,
  fiscal_reference           text,                   -- e-invoice / e-Faktur ref when applicable
  pdf_document_id            uuid,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  created_by text, updated_by text,
  UNIQUE (tenant_id, id),
  UNIQUE (tenant_id, legal_entity_id, series, number),
  CHECK (status <> 'issued' OR (number IS NOT NULL AND issued_at IS NOT NULL)),
  CHECK ((kind = 'credit_note') = (credit_note_for_invoice_id IS NOT NULL)),
  FOREIGN KEY (tenant_id, legal_entity_id) REFERENCES legalentity (tenant_id, id),
  FOREIGN KEY (tenant_id, property_id) REFERENCES property (tenant_id, id),
  FOREIGN KEY (tenant_id, folio_id) REFERENCES folio (tenant_id, id),
  FOREIGN KEY (tenant_id, credit_note_for_invoice_id) REFERENCES invoice (tenant_id, id),
  FOREIGN KEY (tenant_id, account_id) REFERENCES account (tenant_id, id),
  FOREIGN KEY (tenant_id, guest_id) REFERENCES guest (tenant_id, id),
  FOREIGN KEY (tenant_id, pdf_document_id) REFERENCES document (tenant_id, id)
);
CREATE INDEX ix_invoice_account_open ON invoice (tenant_id, account_id) WHERE status = 'issued' AND paid_amount < total;

CREATE TABLE invoiceline (
  id                    uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id             uuid NOT NULL,
  invoice_id            uuid NOT NULL,
  line_no               integer NOT NULL,
  folio_transaction_id  uuid,
  description           text NOT NULL,
  quantity              numeric(10,2) NOT NULL DEFAULT 1,
  unit_price            numeric(18,2) NOT NULL,
  amount                numeric(18,2) NOT NULL,
  tax_amount            numeric(18,2) NOT NULL DEFAULT 0,
  tax_breakdown         jsonb NOT NULL DEFAULT '[]',
  UNIQUE (tenant_id, id),
  UNIQUE (tenant_id, invoice_id, line_no),
  FOREIGN KEY (tenant_id, invoice_id) REFERENCES invoice (tenant_id, id),
  FOREIGN KEY (tenant_id, folio_transaction_id) REFERENCES foliotransaction (tenant_id, id)
);

-- AR: allocate payments to issued invoices (city ledger).
CREATE TABLE paymentallocation (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id   uuid NOT NULL,
  payment_id  uuid NOT NULL,
  invoice_id  uuid NOT NULL,
  amount      numeric(18,2) NOT NULL CHECK (amount > 0),
  allocated_at timestamptz NOT NULL DEFAULT now(),
  allocated_by text,
  UNIQUE (tenant_id, id),
  UNIQUE (tenant_id, payment_id, invoice_id),
  FOREIGN KEY (tenant_id, payment_id) REFERENCES payment (tenant_id, id),
  FOREIGN KEY (tenant_id, invoice_id) REFERENCES invoice (tenant_id, id)
);

-- Night audit / end-of-day per property per business date.
CREATE TABLE businessday (
  id                   uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id            uuid NOT NULL,
  property_id          uuid NOT NULL,
  business_date        date NOT NULL,
  status               text NOT NULL DEFAULT 'open' CHECK (status IN ('open','closing','closed','failed')),
  opened_at            timestamptz NOT NULL DEFAULT now(),
  closed_at            timestamptz,
  closed_by            text,
  run_mode             text CHECK (run_mode IN ('auto','attended')),
  checklist            jsonb NOT NULL DEFAULT '{}',   -- pre-check results
  stats                jsonb NOT NULL DEFAULT '{}',   -- occupancy, ADR, RevPAR, revenue by dept (snapshot)
  report_document_ids  uuid[] NOT NULL DEFAULT '{}',
  error                text,
  UNIQUE (tenant_id, id),
  UNIQUE (tenant_id, property_id, business_date),
  FOREIGN KEY (tenant_id, property_id) REFERENCES property (tenant_id, id)
);

-- =============================================================================
-- J. FRONT DESK EXTRAS
-- =============================================================================

CREATE TABLE accesscredential (
  id                    uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id             uuid NOT NULL,
  property_id           uuid NOT NULL,
  unit_id               uuid,
  reservation_unit_id   uuid,
  holder_kind           text NOT NULL CHECK (holder_kind IN ('guest','staff','vendor')),
  holder_staff_id       uuid,
  kind                  text NOT NULL CHECK (kind IN ('rfid_card','pin_code','mobile_key','physical_key')),
  code_hash             text,                       -- PIN stored hashed; delivered once to guest
  code_hint             text,                       -- e.g. last 2 digits
  lock_system_ref       text,
  valid_from            timestamptz NOT NULL,
  valid_to              timestamptz NOT NULL,
  status                text NOT NULL DEFAULT 'active' CHECK (status IN ('pending','active','revoked','expired','failed')),
  issued_by             text,
  revoked_at            timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  created_by text, updated_by text,
  UNIQUE (tenant_id, id),
  CHECK (valid_to > valid_from),
  FOREIGN KEY (tenant_id, property_id) REFERENCES property (tenant_id, id),
  FOREIGN KEY (tenant_id, unit_id) REFERENCES unit (tenant_id, id) ON DELETE SET NULL (unit_id),
  FOREIGN KEY (tenant_id, reservation_unit_id) REFERENCES reservationunit (tenant_id, id) ON DELETE CASCADE,
  FOREIGN KEY (tenant_id, holder_staff_id) REFERENCES staffmember (tenant_id, id) ON DELETE SET NULL (holder_staff_id)
);

CREATE TABLE lostfounditem (
  id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id         uuid NOT NULL,
  property_id       uuid NOT NULL,
  unit_id           uuid,
  found_at          timestamptz NOT NULL DEFAULT now(),
  found_by_staff_id uuid,
  description       text NOT NULL,
  storage_location  text,
  photo_document_id uuid,
  guest_id          uuid,
  status            text NOT NULL DEFAULT 'stored' CHECK (status IN ('stored','guest_contacted','returned','shipped','disposed','donated')),
  resolved_at       timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  created_by text, updated_by text,
  UNIQUE (tenant_id, id),
  FOREIGN KEY (tenant_id, property_id) REFERENCES property (tenant_id, id),
  FOREIGN KEY (tenant_id, unit_id) REFERENCES unit (tenant_id, id) ON DELETE SET NULL (unit_id),
  FOREIGN KEY (tenant_id, found_by_staff_id) REFERENCES staffmember (tenant_id, id) ON DELETE SET NULL (found_by_staff_id),
  FOREIGN KEY (tenant_id, photo_document_id) REFERENCES document (tenant_id, id) ON DELETE SET NULL (photo_document_id),
  FOREIGN KEY (tenant_id, guest_id) REFERENCES guest (tenant_id, id) ON DELETE SET NULL (guest_id)
);

-- =============================================================================
-- K. DISTRIBUTION (Channel Manager)
-- =============================================================================

CREATE TABLE channelconnection (
  id                       uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id                uuid NOT NULL,
  property_id              uuid NOT NULL,
  channel_id               uuid NOT NULL,
  external_property_id     text,
  connection_via           text NOT NULL CHECK (connection_via IN ('direct_api','partner','ical')),
  partner_name             text,
  credentials_secret_ref   text,
  status                   text NOT NULL DEFAULT 'draft' CHECK (status IN ('draft','testing','live','paused','error','disconnected')),
  currency                 char(3) NOT NULL DEFAULT 'IDR',
  rate_markup_pct          numeric(6,2) NOT NULL DEFAULT 0,
  payment_collect_model    text NOT NULL DEFAULT 'property' CHECK (payment_collect_model IN ('property','channel','mixed')),
  last_ari_success_at      timestamptz,
  last_booking_pull_at     timestamptz,
  error_message            text,
  settings                 jsonb NOT NULL DEFAULT '{}',
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  created_by text, updated_by text,
  UNIQUE (tenant_id, id),
  UNIQUE (tenant_id, property_id, channel_id, external_property_id),
  FOREIGN KEY (tenant_id, property_id) REFERENCES property (tenant_id, id) ON DELETE CASCADE,
  FOREIGN KEY (tenant_id, channel_id) REFERENCES channel (tenant_id, id)
);

-- Local product -> channel room/rate ids.
CREATE TABLE channelmapping (
  id                     uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id              uuid NOT NULL,
  channel_connection_id  uuid NOT NULL,
  unit_type_id           uuid NOT NULL,
  rate_plan_id           uuid,
  external_room_id       text NOT NULL,
  external_rate_id       text,
  occupancy              smallint,
  markup_pct             numeric(6,2),
  allocation_cap         integer CHECK (allocation_cap >= 0),
  is_active              boolean NOT NULL DEFAULT true,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  created_by text, updated_by text,
  UNIQUE (tenant_id, id),
  UNIQUE NULLS NOT DISTINCT (tenant_id, channel_connection_id, external_room_id, external_rate_id, occupancy),
  FOREIGN KEY (tenant_id, channel_connection_id) REFERENCES channelconnection (tenant_id, id) ON DELETE CASCADE,
  FOREIGN KEY (tenant_id, unit_type_id) REFERENCES unittype (tenant_id, id) ON DELETE CASCADE,
  FOREIGN KEY (tenant_id, rate_plan_id) REFERENCES rateplan (tenant_id, id) ON DELETE CASCADE
);

-- Inbound channel booking envelope (idempotent by external id + version).
CREATE TABLE channelbooking (
  id                     uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id              uuid NOT NULL,
  channel_connection_id  uuid NOT NULL,
  external_booking_id    text NOT NULL,
  external_version       text NOT NULL DEFAULT '1',
  event_kind             text NOT NULL CHECK (event_kind IN ('new','modify','cancel')),
  raw                    jsonb NOT NULL,
  reservation_id         uuid,
  processing_status      text NOT NULL DEFAULT 'pending' CHECK (processing_status IN (
                           'pending','applied','needs_attention','duplicate_ignored','failed')),
  attention_reason       text,                       -- 'unmapped_product','overbooking_risk','price_mismatch'
  received_at            timestamptz NOT NULL DEFAULT now(),
  processed_at           timestamptz,
  acknowledged_at        timestamptz,
  UNIQUE (tenant_id, id),
  UNIQUE (tenant_id, channel_connection_id, external_booking_id, external_version),
  FOREIGN KEY (tenant_id, channel_connection_id) REFERENCES channelconnection (tenant_id, id),
  FOREIGN KEY (tenant_id, reservation_id) REFERENCES reservation (tenant_id, id) ON DELETE SET NULL (reservation_id)
);
CREATE INDEX ix_channelbooking_attention ON channelbooking (tenant_id, processing_status) WHERE processing_status IN ('pending','needs_attention','failed');

-- Outbound/inbound message log (ARI pushes, acks, errors). High volume -> partition later.
CREATE TABLE channelmessage (
  id                     uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id              uuid NOT NULL,
  channel_connection_id  uuid NOT NULL,
  direction              text NOT NULL CHECK (direction IN ('outbound','inbound')),
  message_type           text NOT NULL CHECK (message_type IN ('ari_delta','ari_full_sync','booking','booking_ack','content','ping','error')),
  status                 text NOT NULL DEFAULT 'queued' CHECK (status IN ('queued','sent','acked','failed','dead')),
  attempts               integer NOT NULL DEFAULT 0,
  next_attempt_at        timestamptz,
  date_from              date,
  date_to                date,
  correlation_id         text,
  request_payload        jsonb,
  response_payload       jsonb,
  error                  text,
  created_at             timestamptz NOT NULL DEFAULT now(),
  sent_at                timestamptz,
  UNIQUE (tenant_id, id),
  FOREIGN KEY (tenant_id, channel_connection_id) REFERENCES channelconnection (tenant_id, id) ON DELETE CASCADE
);
CREATE INDEX ix_channelmessage_queue ON channelmessage (next_attempt_at) WHERE status IN ('queued','failed');
CREATE INDEX ix_channelmessage_conn ON channelmessage (tenant_id, channel_connection_id, created_at);

CREATE TABLE icalfeed (
  id                     uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id              uuid NOT NULL,
  channel_connection_id  uuid,
  unit_id                uuid NOT NULL,
  direction              text NOT NULL CHECK (direction IN ('import','export')),
  url                    text,                         -- import source
  export_token_hash      text,                         -- export URL token (path segment)
  last_synced_at         timestamptz,
  last_error             text,
  is_active              boolean NOT NULL DEFAULT true,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  created_by text, updated_by text,
  UNIQUE (tenant_id, id),
  CHECK ((direction = 'import') = (url IS NOT NULL)),
  FOREIGN KEY (tenant_id, channel_connection_id) REFERENCES channelconnection (tenant_id, id) ON DELETE CASCADE,
  FOREIGN KEY (tenant_id, unit_id) REFERENCES unit (tenant_id, id) ON DELETE CASCADE
);

-- Daily channel performance (Google impressions/clicks/cost, OTA production).
CREATE TABLE channelperformancedaily (
  id                     uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id              uuid NOT NULL,
  channel_connection_id  uuid NOT NULL,
  metric_date            date NOT NULL,
  impressions            bigint,
  clicks                 bigint,
  bookings               integer,
  room_nights            integer,
  revenue                numeric(18,2),
  cost                   numeric(18,2),             -- ad spend or commission
  price_accuracy_score   numeric(5,2),              -- Google
  UNIQUE (tenant_id, id),
  UNIQUE (tenant_id, channel_connection_id, metric_date),
  FOREIGN KEY (tenant_id, channel_connection_id) REFERENCES channelconnection (tenant_id, id) ON DELETE CASCADE
);

-- =============================================================================
-- L. CRM, MESSAGING & REPUTATION
-- =============================================================================

CREATE TABLE messagingaccount (
  id                      uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id               uuid NOT NULL,
  property_id             uuid,
  channel_kind            text NOT NULL CHECK (channel_kind IN ('whatsapp','sms','email','instagram','google_business','ota','web_chat')),
  provider                text NOT NULL,              -- 'meta_cloud','twilio','smtp','ses','booking_com',…
  sender_identity         text NOT NULL,              -- phone number / email / page id
  credentials_secret_ref  text,
  status                  text NOT NULL DEFAULT 'active' CHECK (status IN ('setup','active','disabled','error')),
  settings                jsonb NOT NULL DEFAULT '{}',
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  created_by text, updated_by text,
  UNIQUE (tenant_id, id),
  UNIQUE (tenant_id, channel_kind, sender_identity),
  FOREIGN KEY (tenant_id, property_id) REFERENCES property (tenant_id, id) ON DELETE CASCADE
);

CREATE TABLE messagetemplate (
  id                      uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id               uuid NOT NULL,
  property_id             uuid,
  code                    text NOT NULL,              -- 'booking_confirmation','pre_arrival','payment_link'
  channel_kind            text NOT NULL CHECK (channel_kind IN ('whatsapp','sms','email','instagram','google_business','ota','web_chat')),
  locale                  text NOT NULL,
  category                text NOT NULL CHECK (category IN ('transactional','utility','marketing','authentication')),
  subject                 text,
  body                    text NOT NULL,
  variables               text[] NOT NULL DEFAULT '{}',
  provider_template_name  text,                       -- WhatsApp approved template name
  provider_status         text NOT NULL DEFAULT 'not_required' CHECK (provider_status IN ('not_required','pending','approved','rejected','paused')),
  is_active               boolean NOT NULL DEFAULT true,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  created_by text, updated_by text,
  UNIQUE (tenant_id, id),
  UNIQUE NULLS NOT DISTINCT (tenant_id, property_id, code, channel_kind, locale),
  FOREIGN KEY (tenant_id, property_id) REFERENCES property (tenant_id, id) ON DELETE CASCADE
);

CREATE TABLE conversation (
  id                         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id                  uuid NOT NULL,
  property_id                uuid NOT NULL,
  messaging_account_id       uuid NOT NULL,
  channel_kind               text NOT NULL,
  external_thread_id         text,                     -- wa_id / OTA thread id / email thread
  guest_id                   uuid,
  reservation_id             uuid,
  status                     text NOT NULL DEFAULT 'open' CHECK (status IN ('open','pending','snoozed','resolved','spam')),
  assigned_staff_id          uuid,
  priority                   text NOT NULL DEFAULT 'normal' CHECK (priority IN ('low','normal','high','urgent')),
  intent                     text,                     -- AI classification
  sentiment                  text CHECK (sentiment IN ('positive','neutral','negative')),
  language                   text,
  last_message_at            timestamptz,
  last_inbound_at            timestamptz,
  service_window_expires_at  timestamptz,              -- WhatsApp 24h customer-service window
  sla_due_at                 timestamptz,
  unread_count               integer NOT NULL DEFAULT 0,
  snoozed_until              timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  created_by text, updated_by text,
  UNIQUE (tenant_id, id),
  FOREIGN KEY (tenant_id, property_id) REFERENCES property (tenant_id, id),
  FOREIGN KEY (tenant_id, messaging_account_id) REFERENCES messagingaccount (tenant_id, id),
  FOREIGN KEY (tenant_id, guest_id) REFERENCES guest (tenant_id, id) ON DELETE SET NULL (guest_id),
  FOREIGN KEY (tenant_id, reservation_id) REFERENCES reservation (tenant_id, id) ON DELETE SET NULL (reservation_id),
  FOREIGN KEY (tenant_id, assigned_staff_id) REFERENCES staffmember (tenant_id, id) ON DELETE SET NULL (assigned_staff_id)
);
CREATE UNIQUE INDEX ux_conversation_thread ON conversation (tenant_id, messaging_account_id, external_thread_id)
  WHERE external_thread_id IS NOT NULL AND status <> 'resolved';
CREATE INDEX ix_conversation_inbox ON conversation (tenant_id, property_id, status, last_message_at DESC);

CREATE TABLE message (
  id                       uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id                uuid NOT NULL,
  conversation_id          uuid NOT NULL,
  direction                text NOT NULL CHECK (direction IN ('inbound','outbound','internal_note')),
  sender_kind              text NOT NULL CHECK (sender_kind IN ('guest','staff','system','ai_auto')),
  sender_staff_id          uuid,
  body                     text,
  body_translations        jsonb NOT NULL DEFAULT '{}',   -- {"en":"…","id":"…"}
  language                 text,
  attachment_document_ids  uuid[] NOT NULL DEFAULT '{}',
  template_id              uuid,
  provider_message_id      text,
  status                   text NOT NULL DEFAULT 'queued' CHECK (status IN ('received','queued','sent','delivered','read','failed')),
  error                    text,
  ai_suggestion_id         uuid,                          -- FK added after aisuggestion
  sent_at                  timestamptz,
  delivered_at             timestamptz,
  read_at                  timestamptz,
  created_at               timestamptz NOT NULL DEFAULT now(),
  UNIQUE (tenant_id, id),
  FOREIGN KEY (tenant_id, conversation_id) REFERENCES conversation (tenant_id, id) ON DELETE CASCADE,
  FOREIGN KEY (tenant_id, sender_staff_id) REFERENCES staffmember (tenant_id, id) ON DELETE SET NULL (sender_staff_id),
  FOREIGN KEY (tenant_id, template_id) REFERENCES messagetemplate (tenant_id, id) ON DELETE SET NULL (template_id)
);
CREATE INDEX ix_message_conversation ON message (tenant_id, conversation_id, created_at);
CREATE UNIQUE INDEX ux_message_provider_id ON message (tenant_id, provider_message_id) WHERE provider_message_id IS NOT NULL;

CREATE TABLE guestsegment (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id   uuid NOT NULL,
  name        text NOT NULL,
  kind        text NOT NULL DEFAULT 'dynamic' CHECK (kind IN ('dynamic','static')),
  rules       jsonb NOT NULL DEFAULT '{}',
  guest_ids   uuid[] NOT NULL DEFAULT '{}',          -- static lists only
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  created_by text, updated_by text,
  UNIQUE (tenant_id, id)
);

CREATE TABLE campaign (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id     uuid NOT NULL,
  property_id   uuid,
  name          text NOT NULL,
  segment_id    uuid NOT NULL,
  template_id   uuid NOT NULL,
  scheduled_at  timestamptz,
  status        text NOT NULL DEFAULT 'draft' CHECK (status IN ('draft','scheduled','sending','sent','cancelled')),
  stats         jsonb NOT NULL DEFAULT '{}',
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  created_by text, updated_by text,
  UNIQUE (tenant_id, id),
  FOREIGN KEY (tenant_id, property_id) REFERENCES property (tenant_id, id) ON DELETE CASCADE,
  FOREIGN KEY (tenant_id, segment_id) REFERENCES guestsegment (tenant_id, id),
  FOREIGN KEY (tenant_id, template_id) REFERENCES messagetemplate (tenant_id, id)
);

-- Lifecycle journeys ("2 days before arrival send pre-check-in link").
CREATE TABLE automation (
  id                   uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id            uuid NOT NULL,
  property_id          uuid,
  name                 text NOT NULL,
  trigger_event        text NOT NULL,              -- 'reservation.confirmed','reservation.arrival_offset',…
  offset_minutes       integer NOT NULL DEFAULT 0, -- negative = before the anchor time
  conditions           jsonb NOT NULL DEFAULT '{}',
  steps                jsonb NOT NULL DEFAULT '[]',
  review_before_send   boolean NOT NULL DEFAULT false,
  is_active            boolean NOT NULL DEFAULT true,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  created_by text, updated_by text,
  UNIQUE (tenant_id, id),
  FOREIGN KEY (tenant_id, property_id) REFERENCES property (tenant_id, id) ON DELETE CASCADE
);

CREATE TABLE scheduledmessage (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id       uuid NOT NULL,
  automation_id   uuid,
  campaign_id     uuid,
  reservation_id  uuid,
  guest_id        uuid NOT NULL,
  template_id     uuid NOT NULL,
  channel_kind    text NOT NULL,
  send_at         timestamptz NOT NULL,
  status          text NOT NULL DEFAULT 'scheduled' CHECK (status IN ('scheduled','awaiting_approval','sent','cancelled','failed','suppressed')),
  suppress_reason text,                              -- 'no_consent','quiet_hours','active_conversation'
  message_id      uuid,
  approved_by     text,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  created_by text, updated_by text,
  UNIQUE (tenant_id, id),
  CHECK (automation_id IS NOT NULL OR campaign_id IS NOT NULL),
  FOREIGN KEY (tenant_id, automation_id) REFERENCES automation (tenant_id, id) ON DELETE CASCADE,
  FOREIGN KEY (tenant_id, campaign_id) REFERENCES campaign (tenant_id, id) ON DELETE CASCADE,
  FOREIGN KEY (tenant_id, reservation_id) REFERENCES reservation (tenant_id, id) ON DELETE CASCADE,
  FOREIGN KEY (tenant_id, guest_id) REFERENCES guest (tenant_id, id) ON DELETE CASCADE,
  FOREIGN KEY (tenant_id, template_id) REFERENCES messagetemplate (tenant_id, id),
  FOREIGN KEY (tenant_id, message_id) REFERENCES message (tenant_id, id) ON DELETE SET NULL (message_id)
);
CREATE INDEX ix_scheduledmessage_due ON scheduledmessage (send_at) WHERE status = 'scheduled';

CREATE TABLE review (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id       uuid NOT NULL,
  property_id     uuid NOT NULL,
  source          text NOT NULL CHECK (source IN ('google','traveloka','tiket','agoda','booking_com','airbnb','expedia','trip_com','tripadvisor','internal')),
  external_id     text NOT NULL,
  reservation_id  uuid,
  guest_id        uuid,
  unit_id         uuid,
  author_name     text,
  rating          numeric(4,2),
  rating_scale    numeric(4,1) NOT NULL DEFAULT 5,
  title           text,
  body            text,
  language        text,
  published_at    timestamptz,
  themes          text[] NOT NULL DEFAULT '{}',      -- AI-tagged: cleanliness, staff, noise …
  sentiment       text CHECK (sentiment IN ('positive','neutral','negative','mixed')),
  response_body   text,
  response_status text NOT NULL DEFAULT 'none' CHECK (response_status IN ('none','draft','awaiting_approval','published','failed')),
  responded_at    timestamptz,
  responded_by    text,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  created_by text, updated_by text,
  UNIQUE (tenant_id, id),
  UNIQUE (tenant_id, source, external_id),
  FOREIGN KEY (tenant_id, property_id) REFERENCES property (tenant_id, id),
  FOREIGN KEY (tenant_id, reservation_id) REFERENCES reservation (tenant_id, id) ON DELETE SET NULL (reservation_id),
  FOREIGN KEY (tenant_id, guest_id) REFERENCES guest (tenant_id, id) ON DELETE SET NULL (guest_id),
  FOREIGN KEY (tenant_id, unit_id) REFERENCES unit (tenant_id, id) ON DELETE SET NULL (unit_id)
);

CREATE TABLE surveyresponse (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id       uuid NOT NULL,
  property_id     uuid NOT NULL,
  reservation_id  uuid,
  guest_id        uuid,
  survey_code     text NOT NULL,
  stage           text NOT NULL DEFAULT 'post_stay' CHECK (stage IN ('in_stay','post_stay')),
  nps             smallint CHECK (nps BETWEEN 0 AND 10),
  csat            smallint CHECK (csat BETWEEN 1 AND 5),
  answers         jsonb NOT NULL DEFAULT '{}',
  submitted_at    timestamptz NOT NULL DEFAULT now(),
  UNIQUE (tenant_id, id),
  FOREIGN KEY (tenant_id, property_id) REFERENCES property (tenant_id, id),
  FOREIGN KEY (tenant_id, reservation_id) REFERENCES reservation (tenant_id, id) ON DELETE SET NULL (reservation_id),
  FOREIGN KEY (tenant_id, guest_id) REFERENCES guest (tenant_id, id) ON DELETE SET NULL (guest_id)
);

-- Complaints and feedback cases.
CREATE TABLE guestfeedback (
  id                   uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id            uuid NOT NULL,
  property_id          uuid NOT NULL,
  reservation_id       uuid,
  guest_id             uuid,
  unit_id              uuid,
  source               text NOT NULL CHECK (source IN ('front_desk','message','survey','review','phone','other')),
  category             text NOT NULL,
  severity             text NOT NULL DEFAULT 'medium' CHECK (severity IN ('low','medium','high','critical')),
  description          text NOT NULL,
  status               text NOT NULL DEFAULT 'open' CHECK (status IN ('open','in_progress','resolved','closed')),
  owner_staff_id       uuid,
  resolution           text,
  compensation_amount  numeric(18,2),
  resolved_at          timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  created_by text, updated_by text,
  UNIQUE (tenant_id, id),
  FOREIGN KEY (tenant_id, property_id) REFERENCES property (tenant_id, id),
  FOREIGN KEY (tenant_id, reservation_id) REFERENCES reservation (tenant_id, id) ON DELETE SET NULL (reservation_id),
  FOREIGN KEY (tenant_id, guest_id) REFERENCES guest (tenant_id, id) ON DELETE SET NULL (guest_id),
  FOREIGN KEY (tenant_id, unit_id) REFERENCES unit (tenant_id, id) ON DELETE SET NULL (unit_id),
  FOREIGN KEY (tenant_id, owner_staff_id) REFERENCES staffmember (tenant_id, id) ON DELETE SET NULL (owner_staff_id)
);

-- =============================================================================
-- M. OPERATIONS (Housekeeping & Maintenance)
-- =============================================================================

CREATE TABLE tasktemplate (
  id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id         uuid NOT NULL,
  property_id       uuid NOT NULL,
  code              text NOT NULL,
  name              text NOT NULL,
  task_kind         text NOT NULL,
  unit_type_id      uuid,
  checklist         jsonb NOT NULL DEFAULT '[]',     -- [{"item":"Change sheets","mandatory":true,"photo":false}]
  standard_minutes  integer NOT NULL DEFAULT 30 CHECK (standard_minutes > 0),
  required_photos   smallint NOT NULL DEFAULT 0,
  is_active         boolean NOT NULL DEFAULT true,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  created_by text, updated_by text,
  UNIQUE (tenant_id, id),
  UNIQUE (tenant_id, property_id, code),
  FOREIGN KEY (tenant_id, property_id) REFERENCES property (tenant_id, id) ON DELETE CASCADE,
  FOREIGN KEY (tenant_id, unit_type_id) REFERENCES unittype (tenant_id, id) ON DELETE SET NULL (unit_type_id)
);

-- Housekeeping and service tasks (not maintenance work orders).
CREATE TABLE task (
  id                    uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id             uuid NOT NULL,
  property_id           uuid NOT NULL,
  task_kind             text NOT NULL CHECK (task_kind IN (
                          'departure_clean','stayover_clean','turndown','deep_clean','linen_change',
                          'inspection','pre_arrival_check','turnover','guest_request','public_area','other')),
  template_id           uuid,
  unit_id               uuid,
  area_id               uuid,
  reservation_unit_id   uuid,
  scheduled_for         date NOT NULL,
  due_at                timestamptz,
  priority              text NOT NULL DEFAULT 'normal' CHECK (priority IN ('low','normal','high','urgent')),
  status                text NOT NULL DEFAULT 'pending' CHECK (status IN (
                          'pending','assigned','in_progress','paused','done','inspected','failed_inspection',
                          'skipped_dnd','refused','cancelled')),
  assigned_staff_id     uuid,
  assigned_vendor_id    uuid,
  standard_minutes      integer,
  started_at            timestamptz,
  completed_at          timestamptz,
  inspected_by_staff_id uuid,
  inspection_result     text CHECK (inspection_result IN ('pass','fail')),
  checklist_result      jsonb NOT NULL DEFAULT '[]',
  photo_document_ids    uuid[] NOT NULL DEFAULT '{}',
  notes                 text,
  source                text NOT NULL DEFAULT 'auto' CHECK (source IN ('auto','manual','guest','message','inspection','ai')),
  vendor_fee            numeric(18,2),
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  created_by text, updated_by text,
  UNIQUE (tenant_id, id),
  CHECK (unit_id IS NOT NULL OR area_id IS NOT NULL OR task_kind = 'other'),
  FOREIGN KEY (tenant_id, property_id) REFERENCES property (tenant_id, id),
  FOREIGN KEY (tenant_id, template_id) REFERENCES tasktemplate (tenant_id, id) ON DELETE SET NULL (template_id),
  FOREIGN KEY (tenant_id, unit_id) REFERENCES unit (tenant_id, id) ON DELETE CASCADE,
  FOREIGN KEY (tenant_id, area_id) REFERENCES propertyarea (tenant_id, id) ON DELETE CASCADE,
  FOREIGN KEY (tenant_id, reservation_unit_id) REFERENCES reservationunit (tenant_id, id) ON DELETE SET NULL (reservation_unit_id),
  FOREIGN KEY (tenant_id, assigned_staff_id) REFERENCES staffmember (tenant_id, id) ON DELETE SET NULL (assigned_staff_id),
  FOREIGN KEY (tenant_id, assigned_vendor_id) REFERENCES vendor (tenant_id, id) ON DELETE SET NULL (assigned_vendor_id),
  FOREIGN KEY (tenant_id, inspected_by_staff_id) REFERENCES staffmember (tenant_id, id) ON DELETE SET NULL (inspected_by_staff_id)
);
CREATE INDEX ix_task_board ON task (tenant_id, property_id, scheduled_for, status);
CREATE INDEX ix_task_assignee ON task (tenant_id, assigned_staff_id, scheduled_for) WHERE assigned_staff_id IS NOT NULL;

-- Unit status history (append-only).
CREATE TABLE unitstatuslog (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id   uuid NOT NULL,
  unit_id     uuid NOT NULL,
  field       text NOT NULL CHECK (field IN ('hk_status','fo_status','service_status')),
  old_value   text,
  new_value   text NOT NULL,
  source      text NOT NULL CHECK (source IN ('staff','mobile','whatsapp','system','night_audit','lock','iot')),
  task_id     uuid,
  changed_by  text,
  changed_at  timestamptz NOT NULL DEFAULT now(),
  UNIQUE (tenant_id, id),
  FOREIGN KEY (tenant_id, unit_id) REFERENCES unit (tenant_id, id) ON DELETE CASCADE,
  FOREIGN KEY (tenant_id, task_id) REFERENCES task (tenant_id, id) ON DELETE SET NULL (task_id)
);
CREATE INDEX ix_unitstatuslog_unit ON unitstatuslog (tenant_id, unit_id, changed_at);

CREATE TABLE asset (
  id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id           uuid NOT NULL,
  property_id         uuid NOT NULL,
  unit_id             uuid,
  area_id             uuid,
  code                text NOT NULL,
  name                text NOT NULL,
  category            text NOT NULL,                 -- 'hvac','boiler','lift','pool','appliance','vehicle','generator'
  manufacturer        text,
  model               text,
  serial_no           text,
  installed_on        date,
  warranty_until      date,
  vendor_id           uuid,
  manual_document_id  uuid,
  status              text NOT NULL DEFAULT 'in_service' CHECK (status IN ('in_service','down','retired')),
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  created_by text, updated_by text,
  UNIQUE (tenant_id, id),
  UNIQUE (tenant_id, property_id, code),
  FOREIGN KEY (tenant_id, property_id) REFERENCES property (tenant_id, id) ON DELETE CASCADE,
  FOREIGN KEY (tenant_id, unit_id) REFERENCES unit (tenant_id, id) ON DELETE SET NULL (unit_id),
  FOREIGN KEY (tenant_id, area_id) REFERENCES propertyarea (tenant_id, id) ON DELETE SET NULL (area_id),
  FOREIGN KEY (tenant_id, vendor_id) REFERENCES vendor (tenant_id, id) ON DELETE SET NULL (vendor_id),
  FOREIGN KEY (tenant_id, manual_document_id) REFERENCES document (tenant_id, id) ON DELETE SET NULL (manual_document_id)
);

CREATE TABLE workorder (
  id                     uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id              uuid NOT NULL,
  property_id            uuid NOT NULL,
  number                 text NOT NULL,
  unit_id                uuid,
  area_id                uuid,
  asset_id               uuid,
  category               text NOT NULL,              -- 'plumbing','electrical','ac','furniture','it','pest',…
  priority               text NOT NULL DEFAULT 'normal' CHECK (priority IN ('low','normal','high','urgent')),
  status                 text NOT NULL DEFAULT 'open' CHECK (status IN (
                           'open','assigned','in_progress','waiting_parts','on_hold','completed','verified','cancelled')),
  title                  text NOT NULL,
  description            text,
  source                 text NOT NULL DEFAULT 'staff' CHECK (source IN ('staff','housekeeping','guest','inspection','preventive','iot','ai')),
  reported_by_staff_id   uuid,
  reported_by_guest_id   uuid,
  assigned_staff_id      uuid,
  vendor_id              uuid,
  is_guest_impacting     boolean NOT NULL DEFAULT false,
  sla_due_at             timestamptz,
  started_at             timestamptz,
  completed_at           timestamptz,
  verified_at            timestamptz,
  labour_minutes         integer,
  parts_cost             numeric(18,2),
  vendor_cost            numeric(18,2),
  recharge_to            text NOT NULL DEFAULT 'none' CHECK (recharge_to IN ('none','owner','guest')),
  photo_document_ids     uuid[] NOT NULL DEFAULT '{}',
  preventive_schedule_id uuid,                        -- FK added below
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  created_by text, updated_by text,
  UNIQUE (tenant_id, id),
  UNIQUE (tenant_id, property_id, number),
  FOREIGN KEY (tenant_id, property_id) REFERENCES property (tenant_id, id),
  FOREIGN KEY (tenant_id, unit_id) REFERENCES unit (tenant_id, id) ON DELETE SET NULL (unit_id),
  FOREIGN KEY (tenant_id, area_id) REFERENCES propertyarea (tenant_id, id) ON DELETE SET NULL (area_id),
  FOREIGN KEY (tenant_id, asset_id) REFERENCES asset (tenant_id, id) ON DELETE SET NULL (asset_id),
  FOREIGN KEY (tenant_id, reported_by_staff_id) REFERENCES staffmember (tenant_id, id) ON DELETE SET NULL (reported_by_staff_id),
  FOREIGN KEY (tenant_id, reported_by_guest_id) REFERENCES guest (tenant_id, id) ON DELETE SET NULL (reported_by_guest_id),
  FOREIGN KEY (tenant_id, assigned_staff_id) REFERENCES staffmember (tenant_id, id) ON DELETE SET NULL (assigned_staff_id),
  FOREIGN KEY (tenant_id, vendor_id) REFERENCES vendor (tenant_id, id) ON DELETE SET NULL (vendor_id)
);
CREATE INDEX ix_workorder_open ON workorder (tenant_id, property_id, status) WHERE status NOT IN ('verified','cancelled');

CREATE TABLE preventiveschedule (
  id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id           uuid NOT NULL,
  property_id         uuid NOT NULL,
  asset_id            uuid,
  unit_id             uuid,
  name                text NOT NULL,
  interval_days       integer NOT NULL CHECK (interval_days > 0),
  lead_days           integer NOT NULL DEFAULT 7,
  next_due_on         date NOT NULL,
  checklist           jsonb NOT NULL DEFAULT '[]',
  is_statutory        boolean NOT NULL DEFAULT false,   -- fire, lift, gas certifications
  is_active           boolean NOT NULL DEFAULT true,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  created_by text, updated_by text,
  UNIQUE (tenant_id, id),
  FOREIGN KEY (tenant_id, property_id) REFERENCES property (tenant_id, id) ON DELETE CASCADE,
  FOREIGN KEY (tenant_id, asset_id) REFERENCES asset (tenant_id, id) ON DELETE CASCADE,
  FOREIGN KEY (tenant_id, unit_id) REFERENCES unit (tenant_id, id) ON DELETE CASCADE
);
ALTER TABLE workorder
  ADD FOREIGN KEY (tenant_id, preventive_schedule_id) REFERENCES preventiveschedule (tenant_id, id) ON DELETE SET NULL (preventive_schedule_id);

-- =============================================================================
-- N. OWNERS (villa portfolios, condo-hotels, rental pools)
-- =============================================================================

CREATE TABLE owner (
  id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id           uuid NOT NULL,
  kind                text NOT NULL DEFAULT 'individual' CHECK (kind IN ('individual','company')),
  name                text NOT NULL,
  email               text,
  phone               text,
  nationality         char(2),
  tax_id              text,
  reporting_currency  char(3) NOT NULL DEFAULT 'IDR',
  payout_details      jsonb NOT NULL DEFAULT '{}',   -- masked; full numbers in secret store
  portal_user_id      integer,                       -- control-plane "user".id
  status              text NOT NULL DEFAULT 'active' CHECK (status IN ('active','inactive')),
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  created_by text, updated_by text,
  UNIQUE (tenant_id, id)
);

CREATE TABLE unitownership (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id       uuid NOT NULL,
  unit_id         uuid NOT NULL,
  owner_id        uuid NOT NULL,
  share_pct       numeric(5,2) NOT NULL CHECK (share_pct > 0 AND share_pct <= 100),
  effective_from  date NOT NULL,
  effective_to    date,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  created_by text, updated_by text,
  UNIQUE (tenant_id, id),
  CHECK (effective_to IS NULL OR effective_to >= effective_from),
  FOREIGN KEY (tenant_id, unit_id) REFERENCES unit (tenant_id, id) ON DELETE CASCADE,
  FOREIGN KEY (tenant_id, owner_id) REFERENCES owner (tenant_id, id) ON DELETE CASCADE
);

CREATE TABLE managementagreement (
  id                       uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id                uuid NOT NULL,
  owner_id                 uuid NOT NULL,
  property_id              uuid NOT NULL,
  model                    text NOT NULL CHECK (model IN ('commission','fixed_fee','revenue_share','rental_pool','guaranteed_rent')),
  terms                    jsonb NOT NULL DEFAULT '{}',   -- {"commission_pct":20,"deduct":["ota_commission","cleaning"]}
  owner_stay_nights_per_year integer,
  valid_from               date NOT NULL,
  valid_to                 date,
  contract_document_id     uuid,
  status                   text NOT NULL DEFAULT 'active' CHECK (status IN ('draft','active','ended')),
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  created_by text, updated_by text,
  UNIQUE (tenant_id, id),
  FOREIGN KEY (tenant_id, owner_id) REFERENCES owner (tenant_id, id) ON DELETE CASCADE,
  FOREIGN KEY (tenant_id, property_id) REFERENCES property (tenant_id, id),
  FOREIGN KEY (tenant_id, contract_document_id) REFERENCES document (tenant_id, id) ON DELETE SET NULL (contract_document_id)
);

-- Out of order / out of service / owner block / house use on a unit.
CREATE TABLE unitblock (
  id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id      uuid NOT NULL,
  unit_id        uuid NOT NULL,
  kind           text NOT NULL CHECK (kind IN ('out_of_order','out_of_service','owner_block','house_use','maintenance_hold')),
  start_at       timestamptz NOT NULL,
  end_at         timestamptz NOT NULL,
  period         tstzrange GENERATED ALWAYS AS (tstzrange(start_at, end_at, '[)')) STORED,
  reason_code_id uuid,
  reason_text    text,
  work_order_id  uuid,
  owner_id       uuid,
  status         text NOT NULL DEFAULT 'active' CHECK (status IN ('active','released','cancelled')),
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  created_by text, updated_by text,
  UNIQUE (tenant_id, id),
  CHECK (end_at > start_at),
  FOREIGN KEY (tenant_id, unit_id) REFERENCES unit (tenant_id, id) ON DELETE CASCADE,
  FOREIGN KEY (tenant_id, reason_code_id) REFERENCES reasoncode (tenant_id, id) ON DELETE SET NULL (reason_code_id),
  FOREIGN KEY (tenant_id, work_order_id) REFERENCES workorder (tenant_id, id) ON DELETE SET NULL (work_order_id),
  FOREIGN KEY (tenant_id, owner_id) REFERENCES owner (tenant_id, id) ON DELETE SET NULL (owner_id),
  CONSTRAINT ex_unitblock_no_overlap EXCLUDE USING gist (unit_id WITH =, period WITH &&) WHERE (status = 'active')
);

CREATE TABLE ownerstatement (
  id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id         uuid NOT NULL,
  owner_id          uuid NOT NULL,
  property_id       uuid NOT NULL,
  number            text,
  period_start      date NOT NULL,
  period_end        date NOT NULL,
  currency          char(3) NOT NULL DEFAULT 'IDR',
  gross_revenue     numeric(18,2) NOT NULL DEFAULT 0,
  commission_total  numeric(18,2) NOT NULL DEFAULT 0,
  expense_total     numeric(18,2) NOT NULL DEFAULT 0,
  withholding_tax   numeric(18,2) NOT NULL DEFAULT 0,
  net_payable       numeric(18,2) NOT NULL DEFAULT 0,
  fx_rate_reporting numeric(20,8),                    -- to owner's reporting currency
  status            text NOT NULL DEFAULT 'draft' CHECK (status IN ('draft','approved','sent','paid','void')),
  approved_by       text,
  approved_at       timestamptz,
  pdf_document_id   uuid,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  created_by text, updated_by text,
  UNIQUE (tenant_id, id),
  UNIQUE (tenant_id, owner_id, property_id, period_start),
  CHECK (period_end >= period_start),
  FOREIGN KEY (tenant_id, owner_id) REFERENCES owner (tenant_id, id),
  FOREIGN KEY (tenant_id, property_id) REFERENCES property (tenant_id, id),
  FOREIGN KEY (tenant_id, pdf_document_id) REFERENCES document (tenant_id, id) ON DELETE SET NULL (pdf_document_id)
);

CREATE TABLE ownerstatementline (
  id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id           uuid NOT NULL,
  statement_id        uuid NOT NULL,
  line_kind           text NOT NULL CHECK (line_kind IN ('revenue','commission','ota_commission','cleaning','maintenance','utility','expense','adjustment','owner_stay','withholding_tax')),
  unit_id             uuid,
  reservation_id      uuid,
  work_order_id       uuid,
  description         text NOT NULL,
  amount              numeric(18,2) NOT NULL,          -- signed: revenue +, deductions −
  receipt_document_id uuid,
  UNIQUE (tenant_id, id),
  FOREIGN KEY (tenant_id, statement_id) REFERENCES ownerstatement (tenant_id, id) ON DELETE CASCADE,
  FOREIGN KEY (tenant_id, unit_id) REFERENCES unit (tenant_id, id),
  FOREIGN KEY (tenant_id, reservation_id) REFERENCES reservation (tenant_id, id),
  FOREIGN KEY (tenant_id, work_order_id) REFERENCES workorder (tenant_id, id),
  FOREIGN KEY (tenant_id, receipt_document_id) REFERENCES document (tenant_id, id) ON DELETE SET NULL (receipt_document_id)
);

CREATE TABLE ownerpayout (
  id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id          uuid NOT NULL,
  owner_id           uuid NOT NULL,
  statement_id       uuid,
  amount             numeric(18,2) NOT NULL CHECK (amount > 0),
  currency           char(3) NOT NULL DEFAULT 'IDR',
  paid_on            date NOT NULL,
  method             text NOT NULL CHECK (method IN ('bank_transfer','cash','wise','other')),
  reference          text,
  withholding_tax    numeric(18,2) NOT NULL DEFAULT 0,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  created_by text, updated_by text,
  UNIQUE (tenant_id, id),
  FOREIGN KEY (tenant_id, owner_id) REFERENCES owner (tenant_id, id),
  FOREIGN KEY (tenant_id, statement_id) REFERENCES ownerstatement (tenant_id, id) ON DELETE SET NULL (statement_id)
);

-- =============================================================================
-- O. LONG STAY, KOS & LEASES
-- =============================================================================

CREATE TABLE lease (
  id                    uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id             uuid NOT NULL,
  property_id           uuid NOT NULL,
  reservation_id        uuid NOT NULL,              -- the long-stay reservation that holds the unit
  resident_guest_id     uuid NOT NULL,
  payer_guest_id        uuid,                       -- e.g. parent paying for a student
  payer_account_id      uuid,
  status                text NOT NULL DEFAULT 'draft' CHECK (status IN ('draft','signed','active','notice_given','ended','settled','cancelled')),
  start_date            date NOT NULL,
  end_date              date,                       -- NULL = open-ended
  notice_days           integer NOT NULL DEFAULT 30,
  billing_cycle         text NOT NULL DEFAULT 'monthly' CHECK (billing_cycle IN ('weekly','monthly','quarterly','yearly','custom')),
  billing_day           smallint CHECK (billing_day BETWEEN 1 AND 28),
  rent_amount           numeric(18,2) NOT NULL CHECK (rent_amount >= 0),
  currency              char(3) NOT NULL DEFAULT 'IDR',
  deposit_amount        numeric(18,2) NOT NULL DEFAULT 0,
  deposit_held          numeric(18,2) NOT NULL DEFAULT 0,
  included_utilities    text[] NOT NULL DEFAULT '{}',   -- 'water','wifi','electricity'
  house_rules_version   text,
  contract_document_id  uuid,
  signed_at             timestamptz,
  notice_given_on       date,
  move_out_on           date,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  created_by text, updated_by text,
  UNIQUE (tenant_id, id),
  UNIQUE (tenant_id, reservation_id),
  CHECK (end_date IS NULL OR end_date > start_date),
  FOREIGN KEY (tenant_id, property_id) REFERENCES property (tenant_id, id),
  FOREIGN KEY (tenant_id, reservation_id) REFERENCES reservation (tenant_id, id),
  FOREIGN KEY (tenant_id, resident_guest_id) REFERENCES guest (tenant_id, id),
  FOREIGN KEY (tenant_id, payer_guest_id) REFERENCES guest (tenant_id, id) ON DELETE SET NULL (payer_guest_id),
  FOREIGN KEY (tenant_id, payer_account_id) REFERENCES account (tenant_id, id) ON DELETE SET NULL (payer_account_id),
  FOREIGN KEY (tenant_id, contract_document_id) REFERENCES document (tenant_id, id) ON DELETE SET NULL (contract_document_id)
);

-- Recurring charges for any reservation (daily parking, monthly laundry, kos rent lines).
CREATE TABLE recurringcharge (
  id                   uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id            uuid NOT NULL,
  reservation_id       uuid NOT NULL,
  lease_id             uuid,
  product_id           uuid,
  transaction_code_id  uuid NOT NULL,
  description          text NOT NULL,
  amount               numeric(18,2) NOT NULL,
  frequency            text NOT NULL CHECK (frequency IN ('daily','weekly','monthly','billing_cycle')),
  start_date           date NOT NULL,
  end_date             date,
  next_run_on          date NOT NULL,
  is_active            boolean NOT NULL DEFAULT true,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  created_by text, updated_by text,
  UNIQUE (tenant_id, id),
  FOREIGN KEY (tenant_id, reservation_id) REFERENCES reservation (tenant_id, id) ON DELETE CASCADE,
  FOREIGN KEY (tenant_id, lease_id) REFERENCES lease (tenant_id, id) ON DELETE CASCADE,
  FOREIGN KEY (tenant_id, product_id) REFERENCES product (tenant_id, id),
  FOREIGN KEY (tenant_id, transaction_code_id) REFERENCES transactioncode (tenant_id, id)
);
CREATE INDEX ix_recurringcharge_due ON recurringcharge (tenant_id, next_run_on) WHERE is_active;

-- One billing period of a lease (monthly kos invoice + pay link + reminders).
CREATE TABLE billingperiod (
  id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id        uuid NOT NULL,
  lease_id         uuid NOT NULL,
  period_start     date NOT NULL,
  period_end       date NOT NULL,
  due_on           date NOT NULL,
  amount           numeric(18,2) NOT NULL,
  invoice_id       uuid,
  payment_link_id  uuid,
  status           text NOT NULL DEFAULT 'scheduled' CHECK (status IN ('scheduled','invoiced','paid','overdue','waived','cancelled')),
  reminder_count   integer NOT NULL DEFAULT 0,
  last_reminded_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  created_by text, updated_by text,
  UNIQUE (tenant_id, id),
  UNIQUE (tenant_id, lease_id, period_start),
  CHECK (period_end >= period_start),
  FOREIGN KEY (tenant_id, lease_id) REFERENCES lease (tenant_id, id) ON DELETE CASCADE,
  FOREIGN KEY (tenant_id, invoice_id) REFERENCES invoice (tenant_id, id),
  FOREIGN KEY (tenant_id, payment_link_id) REFERENCES paymentlink (tenant_id, id) ON DELETE SET NULL (payment_link_id)
);

CREATE TABLE meter (
  id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id    uuid NOT NULL,
  property_id  uuid NOT NULL,
  unit_id      uuid,
  kind         text NOT NULL CHECK (kind IN ('electricity','electricity_prepaid_token','water','gas')),
  meter_no     text NOT NULL,                       -- PLN customer/meter id
  unit_price   numeric(18,4),                       -- per kWh / m3 for postpaid sub-metering
  is_active    boolean NOT NULL DEFAULT true,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  created_by text, updated_by text,
  UNIQUE (tenant_id, id),
  UNIQUE (tenant_id, property_id, meter_no),
  FOREIGN KEY (tenant_id, property_id) REFERENCES property (tenant_id, id) ON DELETE CASCADE,
  FOREIGN KEY (tenant_id, unit_id) REFERENCES unit (tenant_id, id) ON DELETE SET NULL (unit_id)
);

CREATE TABLE meterreading (
  id                     uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id              uuid NOT NULL,
  meter_id               uuid NOT NULL,
  read_at                timestamptz NOT NULL,
  reading_value          numeric(14,3) NOT NULL,
  consumption            numeric(14,3),
  token_purchase_amount  numeric(18,2),             -- prepaid token top-ups
  photo_document_id      uuid,
  read_by                text,
  folio_transaction_id   uuid,                      -- set when billed
  created_at             timestamptz NOT NULL DEFAULT now(),
  UNIQUE (tenant_id, id),
  FOREIGN KEY (tenant_id, meter_id) REFERENCES meter (tenant_id, id) ON DELETE CASCADE,
  FOREIGN KEY (tenant_id, photo_document_id) REFERENCES document (tenant_id, id) ON DELETE SET NULL (photo_document_id),
  FOREIGN KEY (tenant_id, folio_transaction_id) REFERENCES foliotransaction (tenant_id, id)
);

-- =============================================================================
-- P. COMPLIANCE (Indonesia first: APOA, PBJT; generic data-subject requests)
-- =============================================================================

-- Foreign-guest report to immigration (APOA) per occupant.
CREATE TABLE foreignguestreport (
  id                   uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id            uuid NOT NULL,
  property_id          uuid NOT NULL,
  reservation_guest_id uuid NOT NULL,
  guest_id             uuid NOT NULL,
  guest_document_id    uuid,
  report_system        text NOT NULL DEFAULT 'apoa',
  report_kind          text NOT NULL DEFAULT 'arrival' CHECK (report_kind IN ('arrival','departure','amendment')),
  method               text NOT NULL DEFAULT 'assisted_export' CHECK (method IN ('api','assisted_export','manual')),
  status               text NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','ready','submitted','failed','not_required','cancelled')),
  due_at               timestamptz NOT NULL,          -- e.g. check-in + 24h
  submitted_at         timestamptz,
  submitted_by         text,
  external_reference   text,
  payload              jsonb NOT NULL DEFAULT '{}',   -- exact fields sent/exported
  error                text,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  created_by text, updated_by text,
  UNIQUE (tenant_id, id),
  UNIQUE (tenant_id, reservation_guest_id, report_system, report_kind),
  FOREIGN KEY (tenant_id, property_id) REFERENCES property (tenant_id, id),
  FOREIGN KEY (tenant_id, reservation_guest_id) REFERENCES reservationguest (tenant_id, id),
  FOREIGN KEY (tenant_id, guest_id) REFERENCES guest (tenant_id, id),
  FOREIGN KEY (tenant_id, guest_document_id) REFERENCES guestdocument (tenant_id, id) ON DELETE SET NULL (guest_document_id)
);
CREATE INDEX ix_foreignguestreport_due ON foreignguestreport (tenant_id, property_id, due_at) WHERE status IN ('pending','ready','failed');

-- Periodic tax return (PBJT hotel/restaurant per kab/kota, tourist tax, VAT).
CREATE TABLE taxreturn (
  id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id        uuid NOT NULL,
  legal_entity_id  uuid NOT NULL,
  property_id      uuid,
  region_code      text,
  tax_category     text NOT NULL CHECK (tax_category IN ('pbjt_hotel','pbjt_restaurant','tourist_tax','vat','other')),
  period_start     date NOT NULL,
  period_end       date NOT NULL,
  taxable_base     numeric(18,2) NOT NULL DEFAULT 0,
  tax_amount       numeric(18,2) NOT NULL DEFAULT 0,
  details          jsonb NOT NULL DEFAULT '{}',
  status           text NOT NULL DEFAULT 'draft' CHECK (status IN ('draft','final','filed','paid')),
  filed_at         timestamptz,
  filing_reference text,
  export_document_id uuid,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  created_by text, updated_by text,
  UNIQUE (tenant_id, id),
  UNIQUE NULLS NOT DISTINCT (tenant_id, legal_entity_id, property_id, tax_category, period_start),
  FOREIGN KEY (tenant_id, legal_entity_id) REFERENCES legalentity (tenant_id, id),
  FOREIGN KEY (tenant_id, property_id) REFERENCES property (tenant_id, id),
  FOREIGN KEY (tenant_id, export_document_id) REFERENCES document (tenant_id, id) ON DELETE SET NULL (export_document_id)
);

CREATE TABLE datasubjectrequest (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id     uuid NOT NULL,
  guest_id      uuid,
  requester_email text,
  kind          text NOT NULL CHECK (kind IN ('access','export','rectify','erase','restrict','object')),
  status        text NOT NULL DEFAULT 'received' CHECK (status IN ('received','verifying','in_progress','completed','rejected')),
  received_at   timestamptz NOT NULL DEFAULT now(),
  due_at        timestamptz,
  completed_at  timestamptz,
  outcome       text,                               -- incl. what was retained for legal reasons
  export_document_id uuid,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  created_by text, updated_by text,
  UNIQUE (tenant_id, id),
  FOREIGN KEY (tenant_id, guest_id) REFERENCES guest (tenant_id, id) ON DELETE SET NULL (guest_id),
  FOREIGN KEY (tenant_id, export_document_id) REFERENCES document (tenant_id, id) ON DELETE SET NULL (export_document_id)
);

-- =============================================================================
-- Q. ANCILLARY / POS LITE (later phase)
-- =============================================================================

CREATE TABLE outlet (
  id                   uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id            uuid NOT NULL,
  property_id          uuid NOT NULL,
  code                 text NOT NULL,
  name                 text NOT NULL,
  kind                 text NOT NULL CHECK (kind IN ('breakfast','restaurant','bar','shop','reception','spa','activities','pool_bar')),
  opening_hours        jsonb NOT NULL DEFAULT '{}',
  is_active            boolean NOT NULL DEFAULT true,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  created_by text, updated_by text,
  UNIQUE (tenant_id, id),
  UNIQUE (tenant_id, property_id, code),
  FOREIGN KEY (tenant_id, property_id) REFERENCES property (tenant_id, id) ON DELETE CASCADE
);

CREATE TABLE posorder (
  id                   uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id            uuid NOT NULL,
  outlet_id            uuid NOT NULL,
  business_date        date NOT NULL,
  status               text NOT NULL DEFAULT 'open' CHECK (status IN ('open','settled','voided')),
  settlement_kind      text CHECK (settlement_kind IN ('room_charge','payment','complimentary','package_entitlement')),
  folio_id             uuid,
  reservation_unit_id  uuid,
  payment_id           uuid,
  total_amount         numeric(18,2) NOT NULL DEFAULT 0,
  opened_by            text,
  closed_at            timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  created_by text, updated_by text,
  UNIQUE (tenant_id, id),
  FOREIGN KEY (tenant_id, outlet_id) REFERENCES outlet (tenant_id, id),
  FOREIGN KEY (tenant_id, folio_id) REFERENCES folio (tenant_id, id),
  FOREIGN KEY (tenant_id, reservation_unit_id) REFERENCES reservationunit (tenant_id, id),
  FOREIGN KEY (tenant_id, payment_id) REFERENCES payment (tenant_id, id)
);

CREATE TABLE posorderline (
  id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id    uuid NOT NULL,
  pos_order_id uuid NOT NULL,
  product_id   uuid NOT NULL,
  quantity     numeric(10,2) NOT NULL CHECK (quantity > 0),
  unit_price   numeric(18,2) NOT NULL,
  amount       numeric(18,2) NOT NULL,
  modifiers    jsonb NOT NULL DEFAULT '[]',
  UNIQUE (tenant_id, id),
  FOREIGN KEY (tenant_id, pos_order_id) REFERENCES posorder (tenant_id, id) ON DELETE CASCADE,
  FOREIGN KEY (tenant_id, product_id) REFERENCES product (tenant_id, id)
);

-- Bookable services (spa, tours, transfers, equipment) in time slots.
CREATE TABLE servicebooking (
  id                    uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id             uuid NOT NULL,
  property_id           uuid NOT NULL,
  product_id            uuid NOT NULL,
  resource_label        text,                       -- therapist / guide / vehicle
  start_at              timestamptz NOT NULL,
  end_at                timestamptz NOT NULL,
  guest_id              uuid,
  reservation_id        uuid,
  participants          integer NOT NULL DEFAULT 1,
  status                text NOT NULL DEFAULT 'booked' CHECK (status IN ('booked','completed','cancelled','no_show')),
  folio_transaction_id  uuid,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  created_by text, updated_by text,
  UNIQUE (tenant_id, id),
  CHECK (end_at > start_at),
  FOREIGN KEY (tenant_id, property_id) REFERENCES property (tenant_id, id),
  FOREIGN KEY (tenant_id, product_id) REFERENCES product (tenant_id, id),
  FOREIGN KEY (tenant_id, guest_id) REFERENCES guest (tenant_id, id) ON DELETE SET NULL (guest_id),
  FOREIGN KEY (tenant_id, reservation_id) REFERENCES reservation (tenant_id, id) ON DELETE SET NULL (reservation_id),
  FOREIGN KEY (tenant_id, folio_transaction_id) REFERENCES foliotransaction (tenant_id, id)
);

CREATE TABLE voucher (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id       uuid NOT NULL,
  property_id     uuid,
  code            text NOT NULL,
  kind            text NOT NULL CHECK (kind IN ('monetary','experience')),
  initial_value   numeric(18,2) NOT NULL CHECK (initial_value >= 0),
  balance         numeric(18,2) NOT NULL CHECK (balance >= 0),
  currency        char(3) NOT NULL DEFAULT 'IDR',
  expires_on      date,
  buyer_guest_id  uuid,
  payment_id      uuid,
  status          text NOT NULL DEFAULT 'active' CHECK (status IN ('active','redeemed','expired','cancelled')),
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  created_by text, updated_by text,
  UNIQUE (tenant_id, id),
  UNIQUE (tenant_id, code),
  CHECK (balance <= initial_value),
  FOREIGN KEY (tenant_id, property_id) REFERENCES property (tenant_id, id),
  FOREIGN KEY (tenant_id, buyer_guest_id) REFERENCES guest (tenant_id, id) ON DELETE SET NULL (buyer_guest_id),
  FOREIGN KEY (tenant_id, payment_id) REFERENCES payment (tenant_id, id)
);

-- =============================================================================
-- R. REVENUE MANAGEMENT (later phase)
-- =============================================================================

CREATE TABLE demandevent (
  id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id    uuid NOT NULL,
  property_id  uuid,                                 -- NULL = applies to all properties in region
  name         text NOT NULL,
  kind         text NOT NULL CHECK (kind IN ('public_holiday','cuti_bersama','school_holiday','religious','local_event','convention','weather','other')),
  region_code  text,
  starts_on    date NOT NULL,
  ends_on      date NOT NULL,
  impact       text NOT NULL DEFAULT 'medium' CHECK (impact IN ('negative','low','medium','high','very_high')),
  source       text NOT NULL DEFAULT 'manual',       -- 'calendar_pack','manual','ai_suggested'
  is_confirmed boolean NOT NULL DEFAULT true,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  created_by text, updated_by text,
  UNIQUE (tenant_id, id),
  CHECK (ends_on >= starts_on),
  FOREIGN KEY (tenant_id, property_id) REFERENCES property (tenant_id, id) ON DELETE CASCADE
);

CREATE TABLE competitor (
  id                     uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id              uuid NOT NULL,
  property_id            uuid NOT NULL,
  name                   text NOT NULL,
  external_ref           text,
  unit_type_equivalence  jsonb NOT NULL DEFAULT '{}', -- {"<our unit_type_id>":"Deluxe Room"}
  is_active              boolean NOT NULL DEFAULT true,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  created_by text, updated_by text,
  UNIQUE (tenant_id, id),
  FOREIGN KEY (tenant_id, property_id) REFERENCES property (tenant_id, id) ON DELETE CASCADE
);

CREATE TABLE competitorrate (
  id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id      uuid NOT NULL,
  competitor_id  uuid NOT NULL,
  stay_date      date NOT NULL,
  captured_at    timestamptz NOT NULL,
  room_label     text,
  los            smallint NOT NULL DEFAULT 1,
  amount         numeric(18,2),
  currency       char(3) NOT NULL DEFAULT 'IDR',
  is_sold_out    boolean NOT NULL DEFAULT false,
  source         text NOT NULL,
  UNIQUE (tenant_id, id),
  FOREIGN KEY (tenant_id, competitor_id) REFERENCES competitor (tenant_id, id) ON DELETE CASCADE
);
CREATE INDEX ix_competitorrate_lookup ON competitorrate (tenant_id, competitor_id, stay_date, captured_at DESC);

-- Daily forecast snapshot per unit type.
CREATE TABLE forecastday (
  id                   uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id            uuid NOT NULL,
  property_id          uuid NOT NULL,
  unit_type_id         uuid NOT NULL,
  stay_date            date NOT NULL,
  snapshot_date        date NOT NULL,
  on_books             integer NOT NULL,
  forecast_occupancy   numeric(6,4),
  forecast_low         numeric(6,4),
  forecast_high        numeric(6,4),
  forecast_adr         numeric(18,2),
  components           jsonb NOT NULL DEFAULT '{}', -- explainable parts: baseline, dow, pace, events
  UNIQUE (tenant_id, id),
  UNIQUE (tenant_id, unit_type_id, stay_date, snapshot_date),
  FOREIGN KEY (tenant_id, property_id) REFERENCES property (tenant_id, id) ON DELETE CASCADE,
  FOREIGN KEY (tenant_id, unit_type_id) REFERENCES unittype (tenant_id, id) ON DELETE CASCADE
);

CREATE TABLE pricerecommendation (
  id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id           uuid NOT NULL,
  property_id         uuid NOT NULL,
  unit_type_id        uuid NOT NULL,
  rate_plan_id        uuid NOT NULL,
  stay_date           date NOT NULL,
  current_amount      numeric(18,2) NOT NULL,
  recommended_amount  numeric(18,2) NOT NULL,
  reasons             jsonb NOT NULL DEFAULT '[]',
  explanation         text,                          -- AI plain-language summary
  status              text NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','accepted','rejected','auto_applied','superseded','expired')),
  decided_by          text,
  decided_at          timestamptz,
  applied_at          timestamptz,
  created_at          timestamptz NOT NULL DEFAULT now(),
  UNIQUE (tenant_id, id),
  FOREIGN KEY (tenant_id, property_id) REFERENCES property (tenant_id, id) ON DELETE CASCADE,
  FOREIGN KEY (tenant_id, unit_type_id) REFERENCES unittype (tenant_id, id) ON DELETE CASCADE,
  FOREIGN KEY (tenant_id, rate_plan_id) REFERENCES rateplan (tenant_id, id) ON DELETE CASCADE
);
CREATE INDEX ix_pricerecommendation_pending ON pricerecommendation (tenant_id, property_id, stay_date) WHERE status = 'pending';

CREATE TABLE budget (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id     uuid NOT NULL,
  property_id   uuid NOT NULL,
  month         date NOT NULL CHECK (date_trunc('month', month)::date = month),
  metric        text NOT NULL CHECK (metric IN ('occupancy','adr','revpar','room_revenue','total_revenue','room_nights')),
  segment_code  text NOT NULL DEFAULT '',
  amount        numeric(18,4) NOT NULL,
  kind          text NOT NULL DEFAULT 'budget' CHECK (kind IN ('budget','forecast','target')),
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  created_by text, updated_by text,
  UNIQUE (tenant_id, id),
  UNIQUE (tenant_id, property_id, month, metric, segment_code, kind),
  FOREIGN KEY (tenant_id, property_id) REFERENCES property (tenant_id, id) ON DELETE CASCADE
);

-- =============================================================================
-- S. AI ASSISTANT LAYER (hosted models; no training)
-- =============================================================================

CREATE TABLE aifeaturesetting (
  id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id    uuid NOT NULL,
  property_id  uuid,                                 -- NULL = tenant default
  feature      text NOT NULL,                        -- 'message_reply','faq_autoreply','review_reply','transfer_proof',…
  enabled      boolean NOT NULL DEFAULT false,
  autonomy     text NOT NULL DEFAULT 'suggest' CHECK (autonomy IN ('off','suggest','auto_allowlist')),
  model_tier   text NOT NULL DEFAULT 'small' CHECK (model_tier IN ('small','medium','large')),
  config       jsonb NOT NULL DEFAULT '{}',          -- tone, allow-listed intents, language prefs
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  created_by text, updated_by text,
  UNIQUE (tenant_id, id),
  UNIQUE NULLS NOT DISTINCT (tenant_id, property_id, feature),
  FOREIGN KEY (tenant_id, property_id) REFERENCES property (tenant_id, id) ON DELETE CASCADE
);

CREATE TABLE aibudget (
  id                   uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id            uuid NOT NULL,
  property_id          uuid,
  month                date NOT NULL CHECK (date_trunc('month', month)::date = month),
  limit_amount         numeric(18,2) NOT NULL CHECK (limit_amount >= 0),
  spent_amount         numeric(18,6) NOT NULL DEFAULT 0,
  currency             char(3) NOT NULL DEFAULT 'IDR',
  alert_threshold_pct  smallint NOT NULL DEFAULT 80,
  alerted_at           timestamptz,
  exhausted_at         timestamptz,
  updated_at           timestamptz NOT NULL DEFAULT now(),
  UNIQUE (tenant_id, id),
  UNIQUE NULLS NOT DISTINCT (tenant_id, property_id, month),
  FOREIGN KEY (tenant_id, property_id) REFERENCES property (tenant_id, id) ON DELETE CASCADE
);

-- Property knowledge base used to ground every guest-facing answer.
CREATE TABLE aiknowledgeitem (
  id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id           uuid NOT NULL,
  property_id         uuid NOT NULL,
  kind                text NOT NULL CHECK (kind IN ('faq','policy','guide','local_info','manual','menu','other')),
  title               text NOT NULL,
  body                text NOT NULL,
  locale              text NOT NULL DEFAULT 'id-ID',
  allow_autoreply     boolean NOT NULL DEFAULT false,
  source_document_id  uuid,
  version             integer NOT NULL DEFAULT 1,
  is_active           boolean NOT NULL DEFAULT true,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  created_by text, updated_by text,
  UNIQUE (tenant_id, id),
  FOREIGN KEY (tenant_id, property_id) REFERENCES property (tenant_id, id) ON DELETE CASCADE,
  FOREIGN KEY (tenant_id, source_document_id) REFERENCES document (tenant_id, id) ON DELETE SET NULL (source_document_id)
);

CREATE TABLE aichunk (
  id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id          uuid NOT NULL,
  knowledge_item_id  uuid NOT NULL,
  chunk_index        integer NOT NULL,
  content            text NOT NULL,
  content_tsv        tsvector GENERATED ALWAYS AS (to_tsvector('simple', content)) STORED,
  embedding          real[],                         -- switch to vector(N) when pgvector is installed
  embedding_model    text,
  UNIQUE (tenant_id, id),
  UNIQUE (tenant_id, knowledge_item_id, chunk_index),
  FOREIGN KEY (tenant_id, knowledge_item_id) REFERENCES aiknowledgeitem (tenant_id, id) ON DELETE CASCADE
);
CREATE INDEX ix_aichunk_tsv ON aichunk USING gin (content_tsv);

-- Every AI output shown to a human or acted on.
CREATE TABLE aisuggestion (
  id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id      uuid NOT NULL,
  property_id    uuid,
  feature        text NOT NULL,
  subject_table  text NOT NULL,                      -- 'message','review','transferproof','guestdocument',…
  subject_id     uuid NOT NULL,
  input_ref      jsonb NOT NULL DEFAULT '{}',        -- ids of grounding data, not raw PII
  output         jsonb NOT NULL,
  confidence     numeric(4,3),
  status         text NOT NULL DEFAULT 'proposed' CHECK (status IN ('proposed','accepted','edited','rejected','auto_applied','expired')),
  decided_by     text,
  decided_at     timestamptz,
  edit_distance  integer,
  feedback       text,
  created_at     timestamptz NOT NULL DEFAULT now(),
  UNIQUE (tenant_id, id),
  FOREIGN KEY (tenant_id, property_id) REFERENCES property (tenant_id, id) ON DELETE CASCADE
);
CREATE INDEX ix_aisuggestion_subject ON aisuggestion (tenant_id, subject_table, subject_id);

ALTER TABLE message
  ADD FOREIGN KEY (tenant_id, ai_suggestion_id) REFERENCES aisuggestion (tenant_id, id) ON DELETE SET NULL (ai_suggestion_id);

-- Per-call metering (high volume -> partition by month later).
CREATE TABLE aiusage (
  id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id        uuid NOT NULL,
  property_id      uuid,
  feature          text NOT NULL,
  provider         text NOT NULL,
  model            text NOT NULL,
  input_tokens     integer NOT NULL DEFAULT 0,
  output_tokens    integer NOT NULL DEFAULT 0,
  cached_tokens    integer NOT NULL DEFAULT 0,
  cost_amount      numeric(18,6) NOT NULL DEFAULT 0,
  currency         char(3) NOT NULL DEFAULT 'IDR',
  latency_ms       integer,
  was_cache_hit    boolean NOT NULL DEFAULT false,
  suggestion_id    uuid,
  staff_member_id  uuid,
  request_id       text,
  occurred_at      timestamptz NOT NULL DEFAULT now(),
  UNIQUE (tenant_id, id),
  FOREIGN KEY (tenant_id, property_id) REFERENCES property (tenant_id, id) ON DELETE SET NULL (property_id),
  FOREIGN KEY (tenant_id, suggestion_id) REFERENCES aisuggestion (tenant_id, id) ON DELETE SET NULL (suggestion_id),
  FOREIGN KEY (tenant_id, staff_member_id) REFERENCES staffmember (tenant_id, id) ON DELETE SET NULL (staff_member_id)
);
CREATE INDEX ix_aiusage_month ON aiusage (tenant_id, property_id, occurred_at);

-- =============================================================================
-- T. PLATFORM PLUMBING (events, webhooks, API keys, idempotency, audit)
-- =============================================================================

-- Transactional outbox: written in the same transaction as the business change,
-- relayed to the event bus (CRM, channel manager, RMS, control-plane directory).
CREATE TABLE outboxevent (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id       uuid NOT NULL,
  aggregate_type  text NOT NULL,                     -- 'reservation','folio','unit','task'
  aggregate_id    uuid NOT NULL,
  event_type      text NOT NULL,                     -- 'reservation.created','unit.status_changed'
  payload         jsonb NOT NULL,
  occurred_at     timestamptz NOT NULL DEFAULT now(),
  published_at    timestamptz,
  attempts        integer NOT NULL DEFAULT 0,
  last_error      text,
  UNIQUE (tenant_id, id)
);
CREATE INDEX ix_outboxevent_unpublished ON outboxevent (occurred_at) WHERE published_at IS NULL;

CREATE TABLE webhookendpoint (
  id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id    uuid NOT NULL,
  url          text NOT NULL,
  secret_ref   text NOT NULL,
  event_types  text[] NOT NULL DEFAULT '{}',
  is_active    boolean NOT NULL DEFAULT true,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  created_by text, updated_by text,
  UNIQUE (tenant_id, id)
);

CREATE TABLE webhookdelivery (
  id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id        uuid NOT NULL,
  endpoint_id      uuid NOT NULL,
  outbox_event_id  uuid NOT NULL,
  status           text NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','delivered','failed','dead')),
  attempts         integer NOT NULL DEFAULT 0,
  next_attempt_at  timestamptz,
  response_code    integer,
  response_body    text,
  created_at       timestamptz NOT NULL DEFAULT now(),
  UNIQUE (tenant_id, id),
  FOREIGN KEY (tenant_id, endpoint_id) REFERENCES webhookendpoint (tenant_id, id) ON DELETE CASCADE,
  FOREIGN KEY (tenant_id, outbox_event_id) REFERENCES outboxevent (tenant_id, id) ON DELETE CASCADE
);

CREATE TABLE apiclient (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id     uuid NOT NULL,
  name          text NOT NULL,
  key_prefix    text NOT NULL,                      -- shown in UI to identify the key
  key_hash      text NOT NULL,
  scopes        text[] NOT NULL DEFAULT '{}',
  property_ids  uuid[] NOT NULL DEFAULT '{}',       -- empty = all
  expires_at    timestamptz,
  last_used_at  timestamptz,
  status        text NOT NULL DEFAULT 'active' CHECK (status IN ('active','revoked')),
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  created_by text, updated_by text,
  UNIQUE (tenant_id, id),
  UNIQUE (key_hash)
);

CREATE TABLE idempotencyrecord (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id     uuid NOT NULL,
  scope         text NOT NULL,                      -- 'booking_engine.checkout','payment.capture'
  key           text NOT NULL,
  request_hash  text NOT NULL,
  response      jsonb,
  status_code   integer,
  expires_at    timestamptz NOT NULL,
  created_at    timestamptz NOT NULL DEFAULT now(),
  UNIQUE (tenant_id, id),
  UNIQUE (tenant_id, scope, key)
);

-- Tenant-scoped audit trail. Same shape as the audit prefab's audit_entries
-- (hash-chained) plus tenant_id; the chain is per tenant.
CREATE TABLE tenantauditentry (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id     uuid NOT NULL,
  property_id   uuid,
  event_id      text NOT NULL,                      -- AUDIT_EVENTS registry key
  actor_id      text,
  occurred_at   timestamptz NOT NULL DEFAULT now(),
  entity_table  text,
  entity_id     uuid,
  payload       jsonb NOT NULL DEFAULT '{}',
  request_id    text,
  session_id    text,
  ip_address    inet,
  subject_key   text,                               -- shredded on erasure
  anonymised    boolean NOT NULL DEFAULT false,
  prev_hash     text,
  entry_hash    text NOT NULL,
  UNIQUE (tenant_id, id)
);
CREATE INDEX ix_tenantauditentry_entity ON tenantauditentry (tenant_id, entity_table, entity_id, occurred_at);
CREATE INDEX ix_tenantauditentry_time ON tenantauditentry (tenant_id, occurred_at);

-- =============================================================================
-- U. INTEGRITY TRIGGERS
-- =============================================================================

-- Ledger and evidence tables are append-only.
CREATE OR REPLACE FUNCTION forbid_delete() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION '% rows are append-only; post a reversing entry instead', TG_TABLE_NAME
    USING ERRCODE = 'restrict_violation';
END $$;

CREATE OR REPLACE FUNCTION forbid_update() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION '% rows are immutable', TG_TABLE_NAME
    USING ERRCODE = 'restrict_violation';
END $$;

CREATE TRIGGER trg_foliotransaction_no_delete BEFORE DELETE ON foliotransaction FOR EACH ROW EXECUTE FUNCTION forbid_delete();
CREATE TRIGGER trg_foliotransaction_no_update BEFORE UPDATE ON foliotransaction FOR EACH ROW EXECUTE FUNCTION forbid_update();
CREATE TRIGGER trg_invoiceline_no_delete      BEFORE DELETE ON invoiceline      FOR EACH ROW EXECUTE FUNCTION forbid_delete();
CREATE TRIGGER trg_paymentevent_no_delete     BEFORE DELETE ON paymentevent     FOR EACH ROW EXECUTE FUNCTION forbid_delete();
CREATE TRIGGER trg_reservationchange_no_delete BEFORE DELETE ON reservationchange FOR EACH ROW EXECUTE FUNCTION forbid_delete();
CREATE TRIGGER trg_tenantauditentry_no_delete BEFORE DELETE ON tenantauditentry FOR EACH ROW EXECUTE FUNCTION forbid_delete();
CREATE TRIGGER trg_payment_no_delete          BEFORE DELETE ON payment          FOR EACH ROW EXECUTE FUNCTION forbid_delete();

-- Issued invoices are immutable except attaching the PDF / fiscal reference / paid amount.
CREATE OR REPLACE FUNCTION protect_issued_invoice() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
  IF TG_OP = 'DELETE' THEN
    IF OLD.status = 'issued' THEN
      RAISE EXCEPTION 'issued invoice % cannot be deleted; issue a credit note', OLD.number
        USING ERRCODE = 'restrict_violation';
    END IF;
    RETURN OLD;
  END IF;
  IF OLD.status = 'issued' AND (
       NEW.status, NEW.number, NEW.series, NEW.kind, NEW.issued_at, NEW.bill_to,
       NEW.subtotal, NEW.tax_total, NEW.total, NEW.currency, NEW.folio_id, NEW.legal_entity_id
     ) IS DISTINCT FROM (
       OLD.status, OLD.number, OLD.series, OLD.kind, OLD.issued_at, OLD.bill_to,
       OLD.subtotal, OLD.tax_total, OLD.total, OLD.currency, OLD.folio_id, OLD.legal_entity_id
     ) THEN
    RAISE EXCEPTION 'issued invoice % is immutable; issue a credit note', OLD.number
      USING ERRCODE = 'restrict_violation';
  END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER trg_invoice_protect BEFORE UPDATE OR DELETE ON invoice FOR EACH ROW EXECUTE FUNCTION protect_issued_invoice();

-- Closed business days cannot be reopened silently.
CREATE OR REPLACE FUNCTION protect_closed_businessday() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
  IF OLD.status = 'closed' AND NEW.status <> 'closed' THEN
    RAISE EXCEPTION 'business date % is closed', OLD.business_date USING ERRCODE = 'restrict_violation';
  END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER trg_businessday_protect BEFORE UPDATE ON businessday FOR EACH ROW EXECUTE FUNCTION protect_closed_businessday();

-- updated_at maintenance for every table that has the column.
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
      AND EXISTS (SELECT 1 FROM information_schema.columns c2
                  WHERE c2.table_schema = c.table_schema AND c2.table_name = c.table_name
                    AND c2.column_name = 'tenant_id')
  LOOP
    EXECUTE format('DROP TRIGGER IF EXISTS trg_set_updated_at ON %I', r.table_name);
    EXECUTE format('CREATE TRIGGER trg_set_updated_at BEFORE UPDATE ON %I
                    FOR EACH ROW EXECUTE FUNCTION set_updated_at()', r.table_name);
  END LOOP;
END $$;

-- =============================================================================
-- V. ROW-LEVEL SECURITY (tenant isolation)
-- =============================================================================
-- The API sets the tenant per transaction:
--     SET LOCAL app.tenant_id = '<uuid>';
-- If it is not set, current_setting(..., true) returns NULL and NO rows are
-- visible or writable (fail closed). FORCE makes it apply to the table owner
-- too; migrations and cross-tenant jobs use a role with BYPASSRLS.
-- In dedicated_db / dedicated_schema mode RLS stays on as defence in depth.
-- Control-plane tables are excluded: in single-database dev mode they share this
-- schema, and tenant resolution must read them before any tenant is set.
DO $$
DECLARE r record;
BEGIN
  FOR r IN
    SELECT c.table_name
    FROM information_schema.columns c
    JOIN information_schema.tables t
      ON t.table_schema = c.table_schema AND t.table_name = c.table_name
    WHERE c.table_schema = current_schema()
      AND c.column_name = 'tenant_id'
      AND t.table_type = 'BASE TABLE'
      AND c.table_name NOT IN ('tenantdatabase','tenantmigration','tenantdomain','propertydirectory',
                               'tenantsubscription','tenantentitlement','tenantmembership',
                               'tenantinvitation','tenantusagemonthly')
  LOOP
    EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY', r.table_name);
    EXECUTE format('ALTER TABLE %I FORCE ROW LEVEL SECURITY', r.table_name);
    EXECUTE format('DROP POLICY IF EXISTS tenant_isolation ON %I', r.table_name);
    EXECUTE format($p$
      CREATE POLICY tenant_isolation ON %I
        USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
        WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
    $p$, r.table_name);
  END LOOP;
END $$;
