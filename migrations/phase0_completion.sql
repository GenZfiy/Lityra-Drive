-- =============================================================================
-- Phase 0 completion — Coding→Twin fusion, persistent coach, adversarial viva
-- Run ONCE per environment, after deploying the new code. Idempotent (safe to
-- re-run). Postgres syntax. Schema-per-service: run each block against the
-- correct schema (search_path or fully-qualified names).
-- =============================================================================

-- ---- Coding service (schema: drive_coding) ---------------------------------
-- New columns on existing tables (create_all / init-db does NOT add these).
ALTER TABLE drive_coding.problems
    ADD COLUMN IF NOT EXISTS skill      VARCHAR(64)  NOT NULL DEFAULT 'General';
ALTER TABLE drive_coding.problems
    ADD COLUMN IF NOT EXISTS difficulty VARCHAR(16)  NOT NULL DEFAULT 'easy';
ALTER TABLE drive_coding.problems
    ADD COLUMN IF NOT EXISTS practice   BOOLEAN      NOT NULL DEFAULT FALSE;

ALTER TABLE drive_coding.coding_sessions
    ADD COLUMN IF NOT EXISTS kind       VARCHAR(16)  NOT NULL DEFAULT 'exam';
CREATE INDEX IF NOT EXISTS ix_coding_sessions_kind
    ON drive_coding.coding_sessions (kind);

-- New table: adversarial viva (also created by `python manage.py init-db`).
CREATE TABLE IF NOT EXISTS drive_coding.coding_vivas (
    id                 VARCHAR      PRIMARY KEY,
    coding_session_id  VARCHAR(64)  NOT NULL,
    problem_id         VARCHAR(64)  NOT NULL,
    candidate_id       VARCHAR(64)  NOT NULL,
    question           VARCHAR(1024) NOT NULL DEFAULT '',
    answer             VARCHAR(4096) NOT NULL DEFAULT '',
    score              DOUBLE PRECISION NOT NULL DEFAULT 0,
    passed             BOOLEAN      NOT NULL DEFAULT FALSE,
    verdict            VARCHAR(1024) NOT NULL DEFAULT '',
    ai_generated       BOOLEAN      NOT NULL DEFAULT FALSE,
    status             VARCHAR(16)  NOT NULL DEFAULT 'asked',
    created_at         TIMESTAMPTZ  NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_coding_vivas_session   ON drive_coding.coding_vivas (coding_session_id);
CREATE INDEX IF NOT EXISTS ix_coding_vivas_candidate ON drive_coding.coding_vivas (candidate_id);
CREATE INDEX IF NOT EXISTS ix_coding_vivas_problem   ON drive_coding.coding_vivas (problem_id);

-- ---- Assessment service (schema: lms_assessment) ---------------------------
-- New table: persistent AI study plan (also created by `manage.py init-db`).
CREATE TABLE IF NOT EXISTS lms_assessment.study_plans (
    learner_id      VARCHAR(64)  PRIMARY KEY,
    plan            JSON         NOT NULL DEFAULT '{}',
    weakest         VARCHAR(128) NOT NULL DEFAULT '',
    profile_sig     VARCHAR(512) NOT NULL DEFAULT '',
    completed_days  JSON         NOT NULL DEFAULT '[]',
    generated_at    TIMESTAMPTZ  NOT NULL DEFAULT now(),
    last_nudged_at  TIMESTAMPTZ,
    nudge_count     INTEGER      NOT NULL DEFAULT 0
);
