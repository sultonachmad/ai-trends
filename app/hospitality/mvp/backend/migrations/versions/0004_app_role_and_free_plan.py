"""app_rw role, local pooled cluster, Free plan

Revision ID: 0004
Revises: 0003
Create Date: 2026-11-20 00:00:00.000000

Hand-written (no model changes):

* ``app_rw`` — the least-privilege, no-login role tenant-scoped transactions switch to
  (``SET LOCAL ROLE app_rw``, see app/tenancy/session.py). It is not a table owner
  and has no BYPASSRLS, so the ``tenant_isolation`` policies from 0003 apply to it
  even while the API connects as a superuser.
* one ``dbcluster`` row for the database the app runs in (single-DB dev mode).
* the ``free`` plan. Its limits are plain data in ``planmodule.limits`` — change
  them with an UPDATE, no code change needed.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0004"
down_revision: str | Sequence[str] | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

APP_ROLE = "app_rw"
LOCAL_CLUSTER_CODE = "local-pooled-01"
FREE_PLAN_CODE = "free"

# Roles are cluster-wide: another database on the same server may have made it already.
CREATE_ROLE = f"""
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{APP_ROLE}') THEN
    CREATE ROLE {APP_ROLE} NOLOGIN;
  END IF;
END $$;
"""

# Least privilege. app_rw may:
#   * read and write tenant tables ("tenant table" = carries the tenant_isolation policy
#     from 0003), always filtered by that policy;
#   * read the platform catalogs, which hold no tenant data;
#   * read ITS OWN tenant's row in the three control-plane tables below, enforced by the
#     policies in OWN_TENANT_POLICIES.
# It gets nothing on "user" (password hashes), memberships, invitations or other tenants.
GRANT_TENANT_DML = f"""
DO $$
DECLARE r record;
BEGIN
  FOR r IN SELECT tablename FROM pg_policies
           WHERE schemaname = current_schema() AND policyname = 'tenant_isolation'
  LOOP
    EXECUTE format('GRANT SELECT, INSERT, UPDATE, DELETE ON %I TO {APP_ROLE}', r.tablename);
  END LOOP;
END $$;
"""

CATALOG_TABLES = ("module", "channelcatalog", "plan", "planmodule")

# table -> column holding the tenant id. RLS is ENABLED but not FORCED here: the table
# owner (migrations, provisioning) is unaffected; app_rw sees only the current tenant.
OWN_TENANT_TABLES = {
    "tenant": "id",
    "tenantsubscription": "tenant_id",
    "tenantentitlement": "tenant_id",
}
OWN_TENANT_POLICY = "own_tenant_read"
CURRENT_TENANT = "NULLIF(current_setting('app.tenant_id', true), '')::uuid"

SEED_CLUSTER = f"""
INSERT INTO dbcluster (code, region, kind, connection_secret_ref, status)
VALUES ('{LOCAL_CLUSTER_CODE}', 'ap-southeast-3', 'pooled', 'env:PREFAB_DATABASE_URL', 'active')
ON CONFLICT (code) DO NOTHING
"""

SEED_FREE_PLAN = f"""
INSERT INTO plan (code, name, billing_basis, price_amount, currency, billing_period)
VALUES ('{FREE_PLAN_CODE}', 'Free', 'free', 0, 'IDR', 'monthly')
ON CONFLICT (code) DO NOTHING
"""

# Phase 0 wedge: inbox (crm) + payment links (payments) on top of pms_core.
SEED_FREE_PLAN_MODULES = f"""
INSERT INTO planmodule (plan_id, module_code, limits)
SELECT p.id, m.module_code, m.limits::jsonb
FROM plan p
CROSS JOIN (VALUES
  ('pms_core', '{{}}'),
  ('crm',      '{{}}'),
  ('payments', '{{"payment_links_per_month": 30}}')
) AS m(module_code, limits)
WHERE p.code = '{FREE_PLAN_CODE}'
ON CONFLICT (plan_id, module_code) DO NOTHING
"""


def upgrade() -> None:
    """Upgrade schema."""
    op.execute(CREATE_ROLE)
    op.execute(f"GRANT USAGE ON SCHEMA public TO {APP_ROLE}")
    # SET LOCAL ROLE needs membership when the API logs in as a non-superuser.
    op.execute(f"GRANT {APP_ROLE} TO CURRENT_USER")
    op.execute(GRANT_TENANT_DML)
    for table in CATALOG_TABLES:
        op.execute(f"GRANT SELECT ON {table} TO {APP_ROLE}")
    for table, column in OWN_TENANT_TABLES.items():
        op.execute(f"GRANT SELECT ON {table} TO {APP_ROLE}")
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(
            f"CREATE POLICY {OWN_TENANT_POLICY} ON {table} FOR SELECT TO {APP_ROLE} "
            f"USING ({column} = {CURRENT_TENANT})"
        )
    op.execute(SEED_CLUSTER)
    op.execute(SEED_FREE_PLAN)
    op.execute(SEED_FREE_PLAN_MODULES)


def downgrade() -> None:
    """Downgrade schema.

    Fails on purpose (and rolls back) while any tenant still subscribes to the Free
    plan or lives on the local cluster: remove or move those tenants first.
    """
    op.execute(
        "DELETE FROM planmodule WHERE plan_id IN "
        f"(SELECT id FROM plan WHERE code = '{FREE_PLAN_CODE}')"
    )
    op.execute(f"DELETE FROM plan WHERE code = '{FREE_PLAN_CODE}'")
    op.execute(f"DELETE FROM dbcluster WHERE code = '{LOCAL_CLUSTER_CODE}'")
    for table in OWN_TENANT_TABLES:
        op.execute(f"DROP POLICY IF EXISTS {OWN_TENANT_POLICY} ON {table}")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")
    op.execute(f"REVOKE ALL ON ALL TABLES IN SCHEMA public FROM {APP_ROLE}")
    op.execute(f"REVOKE USAGE ON SCHEMA public FROM {APP_ROLE}")
    # The role itself stays: it is cluster-wide and other databases may use it.
