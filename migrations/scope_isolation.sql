-- LARE — data-scope isolation (Phase 2)
-- ============================================================================
-- A role grant can now be pinned to a branch or a section, not just a college,
-- so a Dean sees only their branch and Faculty only their sections. These
-- bindings ride in the access token and every read path filters on them.
--
-- Additive only; safe to run against the shared RDS while old code runs.
-- Idempotent. Schema: lare_auth. Run AFTER rbac_engine.sql.
--   psql "$DATABASE_URL" -f backend/migrations/scope_isolation.sql
-- ============================================================================

SET search_path TO lare_auth, public;

ALTER TABLE user_roles ADD COLUMN IF NOT EXISTS branch_id varchar(64);
ALTER TABLE user_roles ADD COLUMN IF NOT EXISTS cohort_id varchar(64);

CREATE INDEX IF NOT EXISTS ix_user_roles_branch ON user_roles (branch_id);
CREATE INDEX IF NOT EXISTS ix_user_roles_cohort ON user_roles (cohort_id);
