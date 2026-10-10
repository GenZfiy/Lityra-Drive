-- =============================================================================
-- CLOUD DELTA — exactly the tables + columns added between the deployed commit
-- (7181293) and this release (6dee2a8). Nothing else. Idempotent.
--
-- Run once against the production Postgres:
--     psql "$DATABASE_URL" -f cloud_delta.sql
--
-- Schema names assume the cloud convention (schema = service name; auth = lare_auth).
-- If your DB_SCHEMA values differ, change the SET search_path lines.
-- =============================================================================


-- ========================= schema: assessment ===============================
SET search_path TO assessment;

-- new columns on existing tables
ALTER TABLE assessment_items
    ADD COLUMN IF NOT EXISTS difficulty VARCHAR(8) NOT NULL DEFAULT 'medium';
-- proctoring/shuffle (added in 7181293; include for DBs deployed before it)
ALTER TABLE assessments
    ADD COLUMN IF NOT EXISTS proctored BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE assessments
    ADD COLUMN IF NOT EXISTS shuffle   BOOLEAN NOT NULL DEFAULT FALSE;

-- new tables
CREATE TABLE IF NOT EXISTS study_plans (
    learner_id      VARCHAR(64)  PRIMARY KEY,
    plan            JSON         NOT NULL DEFAULT '{}',
    weakest         VARCHAR(128) NOT NULL DEFAULT '',
    profile_sig     VARCHAR(512) NOT NULL DEFAULT '',
    completed_days  JSON         NOT NULL DEFAULT '[]',
    generated_at    TIMESTAMPTZ  NOT NULL DEFAULT now(),
    last_nudged_at  TIMESTAMPTZ,
    nudge_count     INTEGER      NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS career_roles (
    id              VARCHAR      PRIMARY KEY,
    title           VARCHAR(128) NOT NULL,
    description     VARCHAR(512),
    required_skills JSON         NOT NULL DEFAULT '[]',
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS review_items (
    id                VARCHAR      PRIMARY KEY,
    learner_id        VARCHAR(64)  NOT NULL,
    skill             VARCHAR(128) NOT NULL,
    source            VARCHAR(16)  NOT NULL DEFAULT 'written',
    interval_days     DOUBLE PRECISION NOT NULL DEFAULT 1.0,
    ease              DOUBLE PRECISION NOT NULL DEFAULT 2.0,
    review_count      INTEGER      NOT NULL DEFAULT 0,
    last_mastery      DOUBLE PRECISION NOT NULL DEFAULT 0,
    last_reviewed_at  TIMESTAMPTZ  NOT NULL DEFAULT now(),
    due_at            TIMESTAMPTZ  NOT NULL DEFAULT now(),
    created_at        TIMESTAMPTZ  NOT NULL DEFAULT now(),
    CONSTRAINT uq_review_learner_skill UNIQUE (learner_id, skill)
);
CREATE INDEX IF NOT EXISTS ix_review_items_learner ON review_items (learner_id);
CREATE INDEX IF NOT EXISTS ix_review_items_due     ON review_items (due_at);

CREATE TABLE IF NOT EXISTS wallet_credentials (
    id            VARCHAR      PRIMARY KEY,
    learner_id    VARCHAR(64)  NOT NULL UNIQUE,
    verify_id     VARCHAR(64)  NOT NULL UNIQUE,
    subject_name  VARCHAR(255) NOT NULL DEFAULT '',
    payload       JSON         NOT NULL DEFAULT '{}',
    signature     TEXT         NOT NULL DEFAULT '',
    revoked       BOOLEAN      NOT NULL DEFAULT FALSE,
    issued_at     TIMESTAMPTZ  NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS drill_sessions (
    id              VARCHAR     PRIMARY KEY,
    learner_id      VARCHAR(64) NOT NULL,
    topic           VARCHAR(128),
    level           INTEGER     NOT NULL DEFAULT 1,
    served          JSON        NOT NULL DEFAULT '[]',
    pending_item_id VARCHAR(64),
    pending_q       JSON        NOT NULL DEFAULT '{}',
    pending_since   TIMESTAMPTZ,
    correct_count   INTEGER     NOT NULL DEFAULT 0,
    total_count     INTEGER     NOT NULL DEFAULT 0,
    fast_count      INTEGER     NOT NULL DEFAULT 0,
    target          INTEGER     NOT NULL DEFAULT 8,
    status          VARCHAR(12) NOT NULL DEFAULT 'active',
    started_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_drill_sessions_learner ON drill_sessions (learner_id);

CREATE TABLE IF NOT EXISTS teach_sessions (
    id           VARCHAR      PRIMARY KEY,
    topic        VARCHAR(128) NOT NULL,
    teacher_id   VARCHAR(64)  NOT NULL,
    learner_id   VARCHAR(64)  NOT NULL,
    requested_by VARCHAR(64)  NOT NULL,
    status       VARCHAR(12)  NOT NULL DEFAULT 'requested',
    note         VARCHAR(512),
    created_at   TIMESTAMPTZ  NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_teach_sessions_teacher ON teach_sessions (teacher_id);
CREATE INDEX IF NOT EXISTS ix_teach_sessions_learner ON teach_sessions (learner_id);

CREATE TABLE IF NOT EXISTS generated_lessons (
    id          VARCHAR      PRIMARY KEY,
    learner_id  VARCHAR(64)  NOT NULL,
    topic       VARCHAR(128) NOT NULL,
    lesson      JSON         NOT NULL DEFAULT '{}',
    generated   BOOLEAN      NOT NULL DEFAULT FALSE,
    created_at  TIMESTAMPTZ  NOT NULL DEFAULT now(),
    CONSTRAINT uq_lesson_learner_topic UNIQUE (learner_id, topic)
);
CREATE INDEX IF NOT EXISTS ix_generated_lessons_learner ON generated_lessons (learner_id);

CREATE TABLE IF NOT EXISTS practice_worlds (
    id          VARCHAR      PRIMARY KEY,
    title       VARCHAR(160) NOT NULL,
    role        VARCHAR(80)  NOT NULL DEFAULT '',
    skill       VARCHAR(80)  NOT NULL DEFAULT '',
    difficulty  VARCHAR(8)   NOT NULL DEFAULT 'medium',
    summary     VARCHAR(512),
    steps       JSON         NOT NULL DEFAULT '[]',
    pass_pct    INTEGER      NOT NULL DEFAULT 60,
    created_at  TIMESTAMPTZ  NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS world_runs (
    id            VARCHAR     PRIMARY KEY,
    world_id      VARCHAR(64) NOT NULL,
    learner_id    VARCHAR(64) NOT NULL,
    step_index    INTEGER     NOT NULL DEFAULT 0,
    answers       JSON        NOT NULL DEFAULT '{}',
    correct_count INTEGER     NOT NULL DEFAULT 0,
    score         DOUBLE PRECISION NOT NULL DEFAULT 0,
    status        VARCHAR(12) NOT NULL DEFAULT 'in_progress',
    started_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_world_runs_world   ON world_runs (world_id);
CREATE INDEX IF NOT EXISTS ix_world_runs_learner ON world_runs (learner_id);


-- ========================= schema: coding ===================================
SET search_path TO coding;

-- new columns on existing tables
ALTER TABLE problems         ADD COLUMN IF NOT EXISTS skill      VARCHAR(64)  NOT NULL DEFAULT 'General';
ALTER TABLE problems         ADD COLUMN IF NOT EXISTS difficulty VARCHAR(16)  NOT NULL DEFAULT 'easy';
ALTER TABLE problems         ADD COLUMN IF NOT EXISTS practice   BOOLEAN      NOT NULL DEFAULT FALSE;
ALTER TABLE coding_sessions  ADD COLUMN IF NOT EXISTS kind       VARCHAR(16)  NOT NULL DEFAULT 'exam';
CREATE INDEX IF NOT EXISTS ix_coding_sessions_kind ON coding_sessions (kind);

-- new table
CREATE TABLE IF NOT EXISTS coding_vivas (
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
CREATE INDEX IF NOT EXISTS ix_coding_vivas_session   ON coding_vivas (coding_session_id);
CREATE INDEX IF NOT EXISTS ix_coding_vivas_candidate ON coding_vivas (candidate_id);
CREATE INDEX IF NOT EXISTS ix_coding_vivas_problem   ON coding_vivas (problem_id);


-- ========================= schema: curriculum ===============================
SET search_path TO curriculum;

ALTER TABLE lessons ADD COLUMN IF NOT EXISTS content JSON NOT NULL DEFAULT '[]';


-- ========================= schema: drive ====================================
SET search_path TO drive;

ALTER TABLE drive_roles ADD COLUMN IF NOT EXISTS skills JSON NOT NULL DEFAULT '[]';
