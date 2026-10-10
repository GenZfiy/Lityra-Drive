-- LARE — RBAC engine (Phase 1: granular permissions, custom roles, scope)
-- ============================================================================
-- Adds the columns the RBAC engine needs on the existing `roles` table. The
-- application seed (backend/services/auth/manage.py seed) then, idempotently:
--   * inserts the full granular permission catalog,
--   * inserts the new built-in roles (principal, dean, tpo, faculty),
--   * grants each built-in role its default permission set,
--   * marks built-in roles is_system=true and sets their scope_level.
--
-- This migration only performs the DDL that create_all() cannot (adding columns
-- to a table that already exists). Data population is left to the seed so the
-- two never drift. Idempotent. Schema: lare_auth.
--   psql "$DATABASE_URL" -f backend/migrations/rbac_engine.sql
-- ============================================================================

SET search_path TO lare_auth, public;

-- Data-visibility ceiling for a role's holders: platform|college|branch|section|self.
ALTER TABLE roles ADD COLUMN IF NOT EXISTS scope_level varchar(16) NOT NULL DEFAULT 'self';

-- Built-in roles cannot be deleted (only re-permissioned); custom roles can.
ALTER TABLE roles ADD COLUMN IF NOT EXISTS is_system boolean NOT NULL DEFAULT false;

-- Deactivated roles keep their assignments but grant no permissions at login.
ALTER TABLE roles ADD COLUMN IF NOT EXISTS is_active boolean NOT NULL DEFAULT true;

ALTER TABLE roles ADD COLUMN IF NOT EXISTS created_at timestamptz NOT NULL DEFAULT now();

-- Flag the pre-existing built-in ladder as system roles up front, so that even
-- before the app seed runs they are protected from deletion.
UPDATE roles SET is_system = true
 WHERE name IN ('super_admin','company_admin','principal','dean','tpo',
                'college_admin','trainer','faculty','recruiter','student');
