-- =============================================================================
-- Skills-to-Opportunity — Career Readiness (Learn) + Matched Opportunities (Hire)
-- Idempotent. Run once per environment after deploying the code.
-- NOTE: schema names below assume the defaults (drive_core / lms_assessment). If
-- your service runs with a different DB_SCHEMA, change the search_path lines.
-- The NEW tables (career_roles) are created automatically by `manage.py init-db`;
-- only the new COLUMN below needs this migration.
-- =============================================================================

-- ---- LARE Hire (drive-core): required skills on a drive role ----------------
SET search_path TO drive_core;
ALTER TABLE drive_roles
    ADD COLUMN IF NOT EXISTS skills JSON NOT NULL DEFAULT '[]';

-- ---- LARE Learn (lms-assessment): career-role catalog ----------------------
-- Created by `cd backend/services/assessment && python manage.py init-db`.
-- Provided here as a fallback (safe to run):
SET search_path TO lms_assessment;
CREATE TABLE IF NOT EXISTS career_roles (
    id              VARCHAR      PRIMARY KEY,
    title           VARCHAR(128) NOT NULL,
    description     VARCHAR(512),
    required_skills JSON         NOT NULL DEFAULT '[]',
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT now()
);
