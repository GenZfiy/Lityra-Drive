-- REVIEW REQUIRED; do not apply to production without backup and approval.
-- Run as a database administrator after both products' schemas are present.
-- This creates NOLOGIN group roles. Create separate LOGIN credentials in the
-- database provider and grant each login membership in exactly one group.
BEGIN;
SELECT pg_advisory_xact_lock(781204262);

DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'lityra_learn_runtime') THEN
    CREATE ROLE lityra_learn_runtime NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'lityra_hire_runtime') THEN
    CREATE ROLE lityra_hire_runtime NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'lityra_combined_fallback') THEN
    CREATE ROLE lityra_combined_fallback NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION;
  END IF;
END $$;

REVOKE CREATE ON SCHEMA public FROM PUBLIC;

-- Private service schemas. Only the listed product group gets table access.
REVOKE ALL ON SCHEMA institution, learner, curriculum, content, progress,
  assessment, gamification, certification, ai_tutor FROM PUBLIC, lityra_hire_runtime;
REVOKE ALL ON ALL TABLES IN SCHEMA institution, learner, curriculum, content,
  progress, assessment, gamification, certification, ai_tutor
  FROM PUBLIC, lityra_hire_runtime;
REVOKE ALL ON ALL SEQUENCES IN SCHEMA institution, learner, curriculum,
  content, progress, assessment, gamification, certification, ai_tutor
  FROM PUBLIC, lityra_hire_runtime;
GRANT USAGE ON SCHEMA institution, learner, curriculum, content, progress,
  assessment, gamification, certification, ai_tutor TO lityra_learn_runtime;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA institution, learner,
  curriculum, content, progress, assessment, gamification, certification,
  ai_tutor TO lityra_learn_runtime;
GRANT USAGE, SELECT, UPDATE ON ALL SEQUENCES IN SCHEMA institution, learner,
  curriculum, content, progress, assessment, gamification, certification,
  ai_tutor TO lityra_learn_runtime;
GRANT USAGE ON SCHEMA institution, learner, curriculum, content, progress,
  assessment, gamification, certification, ai_tutor TO lityra_combined_fallback;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA institution, learner,
  curriculum, content, progress, assessment, gamification, certification,
  ai_tutor TO lityra_combined_fallback;
GRANT USAGE, SELECT, UPDATE ON ALL SEQUENCES IN SCHEMA institution, learner,
  curriculum, content, progress, assessment, gamification, certification,
  ai_tutor TO lityra_combined_fallback;

REVOKE ALL ON SCHEMA candidate, drive, questionbank, exam, submission,
  anticheat, evaluation, interview, result, evidence, competency, decision,
  action, recruit_ai FROM PUBLIC, lityra_learn_runtime;
REVOKE ALL ON ALL TABLES IN SCHEMA candidate, drive, questionbank, exam,
  submission, anticheat, evaluation, interview, result, evidence, competency,
  decision, action, recruit_ai FROM PUBLIC, lityra_learn_runtime;
REVOKE ALL ON ALL SEQUENCES IN SCHEMA candidate, drive, questionbank, exam,
  submission, anticheat, evaluation, interview, result, evidence, competency,
  decision, action, recruit_ai FROM PUBLIC, lityra_learn_runtime;
GRANT USAGE ON SCHEMA candidate, drive, questionbank, exam, submission,
  anticheat, evaluation, interview, result, evidence, competency, decision,
  action, recruit_ai TO lityra_hire_runtime;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA candidate, drive,
  questionbank, exam, submission, anticheat, evaluation, interview, result,
  evidence, competency, decision, action, recruit_ai TO lityra_hire_runtime;
GRANT USAGE, SELECT, UPDATE ON ALL SEQUENCES IN SCHEMA candidate, drive,
  questionbank, exam, submission, anticheat, evaluation, interview, result,
  evidence, competency, decision, action, recruit_ai TO lityra_hire_runtime;
GRANT USAGE ON SCHEMA candidate, drive, questionbank, exam, submission,
  anticheat, evaluation, interview, result, evidence, competency, decision,
  action, recruit_ai TO lityra_combined_fallback;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA candidate, drive,
  questionbank, exam, submission, anticheat, evaluation, interview, result,
  evidence, competency, decision, action, recruit_ai TO lityra_combined_fallback;
GRANT USAGE, SELECT, UPDATE ON ALL SEQUENCES IN SCHEMA candidate, drive,
  questionbank, exam, submission, anticheat, evaluation, interview, result,
  evidence, competency, decision, action, recruit_ai TO lityra_combined_fallback;

-- The auth schema stores accounts for both products. Row-level security binds
-- each product role to its product rows; table owners/superusers can bypass RLS,
-- so product web services must never connect as the migration/schema owner.
REVOKE ALL ON SCHEMA lare_auth FROM PUBLIC;
REVOKE ALL ON ALL TABLES IN SCHEMA lare_auth FROM PUBLIC;
REVOKE ALL ON ALL SEQUENCES IN SCHEMA lare_auth FROM PUBLIC;
GRANT USAGE ON SCHEMA lare_auth TO lityra_learn_runtime, lityra_hire_runtime;
GRANT USAGE ON SCHEMA lare_auth TO lityra_combined_fallback;
GRANT SELECT, INSERT ON lare_auth.users TO lityra_learn_runtime, lityra_hire_runtime,
  lityra_combined_fallback;
GRANT UPDATE (email, password_hash, full_name, status, email_verified,
  mfa_enabled, tenant_id, failed_attempts, locked_until)
  ON lare_auth.users TO lityra_learn_runtime, lityra_hire_runtime,
  lityra_combined_fallback;
GRANT SELECT ON lare_auth.roles, lare_auth.permissions,
  lare_auth.role_permissions TO lityra_learn_runtime, lityra_hire_runtime,
  lityra_combined_fallback;
GRANT SELECT, INSERT, UPDATE, DELETE ON lare_auth.user_roles,
  lare_auth.refresh_tokens, lare_auth.verification_tokens
  TO lityra_learn_runtime, lityra_hire_runtime, lityra_combined_fallback;
GRANT USAGE, SELECT, UPDATE ON ALL SEQUENCES IN SCHEMA lare_auth
  TO lityra_learn_runtime, lityra_hire_runtime, lityra_combined_fallback;

-- Shared capability processes are also duplicated per product. Their schemas
-- are product-prefixed, so an application bug cannot expose cross-product rows
-- even where the service data model has no product discriminator.
REVOKE ALL ON SCHEMA learn_coding, learn_notification, learn_files,
  learn_analytics, learn_audit, learn_ai_orchestration, learn_organization
  FROM PUBLIC, lityra_hire_runtime;
REVOKE ALL ON ALL TABLES IN SCHEMA learn_coding, learn_notification, learn_files,
  learn_analytics, learn_audit, learn_ai_orchestration, learn_organization
  FROM PUBLIC, lityra_hire_runtime;
REVOKE ALL ON ALL SEQUENCES IN SCHEMA learn_coding, learn_notification,
  learn_files, learn_analytics, learn_audit, learn_ai_orchestration,
  learn_organization FROM PUBLIC, lityra_hire_runtime;
GRANT USAGE ON SCHEMA learn_coding, learn_notification, learn_files,
  learn_analytics, learn_audit, learn_ai_orchestration, learn_organization
  TO lityra_learn_runtime;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA learn_coding,
  learn_notification, learn_files, learn_analytics, learn_audit,
  learn_ai_orchestration, learn_organization TO lityra_learn_runtime;
GRANT USAGE, SELECT, UPDATE ON ALL SEQUENCES IN SCHEMA learn_coding,
  learn_notification, learn_files, learn_analytics, learn_audit,
  learn_ai_orchestration, learn_organization TO lityra_learn_runtime;

REVOKE ALL ON SCHEMA hire_coding, hire_notification, hire_files,
  hire_analytics, hire_audit, hire_ai_orchestration, hire_organization
  FROM PUBLIC, lityra_learn_runtime;
REVOKE ALL ON ALL TABLES IN SCHEMA hire_coding, hire_notification, hire_files,
  hire_analytics, hire_audit, hire_ai_orchestration, hire_organization
  FROM PUBLIC, lityra_learn_runtime;
REVOKE ALL ON ALL SEQUENCES IN SCHEMA hire_coding, hire_notification,
  hire_files, hire_analytics, hire_audit, hire_ai_orchestration,
  hire_organization FROM PUBLIC, lityra_learn_runtime;
GRANT USAGE ON SCHEMA hire_coding, hire_notification, hire_files,
  hire_analytics, hire_audit, hire_ai_orchestration, hire_organization
  TO lityra_hire_runtime;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA hire_coding,
  hire_notification, hire_files, hire_analytics, hire_audit,
  hire_ai_orchestration, hire_organization TO lityra_hire_runtime;
GRANT USAGE, SELECT, UPDATE ON ALL SEQUENCES IN SCHEMA hire_coding,
  hire_notification, hire_files, hire_analytics, hire_audit,
  hire_ai_orchestration, hire_organization TO lityra_hire_runtime;

-- The fallback group is intentionally broad and NOLOGIN. It is not inherited
-- by Learn or Hire logins; it exists only for an explicitly approved combined
-- rollback and keeps that fallback's shared capabilities online.
GRANT USAGE ON SCHEMA coding, notification, files, analytics, audit,
  ai_orchestration, organization TO lityra_combined_fallback;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA coding,
  notification, files, analytics, audit, ai_orchestration, organization
  TO lityra_combined_fallback;
GRANT USAGE, SELECT, UPDATE ON ALL SEQUENCES IN SCHEMA coding, notification,
  files, analytics, audit, ai_orchestration, organization
  TO lityra_combined_fallback;
GRANT USAGE ON SCHEMA learn_coding, learn_notification, learn_files,
  learn_analytics, learn_audit, learn_ai_orchestration, learn_organization,
  hire_coding, hire_notification, hire_files, hire_analytics, hire_audit,
  hire_ai_orchestration, hire_organization TO lityra_combined_fallback;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA learn_coding,
  learn_notification, learn_files, learn_analytics, learn_audit,
  learn_ai_orchestration, learn_organization, hire_coding, hire_notification,
  hire_files, hire_analytics, hire_audit, hire_ai_orchestration,
  hire_organization TO lityra_combined_fallback;
GRANT USAGE, SELECT, UPDATE ON ALL SEQUENCES IN SCHEMA learn_coding,
  learn_notification, learn_files, learn_analytics, learn_audit,
  learn_ai_orchestration, learn_organization, hire_coding, hire_notification,
  hire_files, hire_analytics, hire_audit, hire_ai_orchestration,
  hire_organization TO lityra_combined_fallback;

ALTER TABLE lare_auth.users ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS product_users_isolation ON lare_auth.users;
CREATE POLICY product_users_isolation ON lare_auth.users
  USING (
    (pg_has_role(current_user, 'lityra_learn_runtime', 'member') AND product = 'learn') OR
    (pg_has_role(current_user, 'lityra_hire_runtime', 'member') AND product = 'hire') OR
    (pg_has_role(current_user, 'lityra_combined_fallback', 'member') AND product IN ('learn', 'hire'))
  )
  WITH CHECK (
    (pg_has_role(current_user, 'lityra_learn_runtime', 'member') AND product = 'learn') OR
    (pg_has_role(current_user, 'lityra_hire_runtime', 'member') AND product = 'hire') OR
    (pg_has_role(current_user, 'lityra_combined_fallback', 'member') AND product IN ('learn', 'hire'))
  );

ALTER TABLE lare_auth.user_roles ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS product_user_roles_isolation ON lare_auth.user_roles;
CREATE POLICY product_user_roles_isolation ON lare_auth.user_roles
  USING (EXISTS (
    SELECT 1 FROM lare_auth.users u WHERE u.id = user_id
      AND ((pg_has_role(current_user, 'lityra_learn_runtime', 'member') AND u.product = 'learn')
        OR (pg_has_role(current_user, 'lityra_hire_runtime', 'member') AND u.product = 'hire')
        OR (pg_has_role(current_user, 'lityra_combined_fallback', 'member') AND u.product IN ('learn', 'hire')))
  ))
  WITH CHECK (EXISTS (
    SELECT 1 FROM lare_auth.users u WHERE u.id = user_id
      AND ((pg_has_role(current_user, 'lityra_learn_runtime', 'member') AND u.product = 'learn')
        OR (pg_has_role(current_user, 'lityra_hire_runtime', 'member') AND u.product = 'hire')
        OR (pg_has_role(current_user, 'lityra_combined_fallback', 'member') AND u.product IN ('learn', 'hire')))
  ));

ALTER TABLE lare_auth.refresh_tokens ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS product_refresh_tokens_isolation ON lare_auth.refresh_tokens;
CREATE POLICY product_refresh_tokens_isolation ON lare_auth.refresh_tokens
  USING (EXISTS (
    SELECT 1 FROM lare_auth.users u WHERE u.id = user_id
      AND ((pg_has_role(current_user, 'lityra_learn_runtime', 'member') AND u.product = 'learn')
        OR (pg_has_role(current_user, 'lityra_hire_runtime', 'member') AND u.product = 'hire')
        OR (pg_has_role(current_user, 'lityra_combined_fallback', 'member') AND u.product IN ('learn', 'hire')))
  ))
  WITH CHECK (EXISTS (
    SELECT 1 FROM lare_auth.users u WHERE u.id = user_id
      AND ((pg_has_role(current_user, 'lityra_learn_runtime', 'member') AND u.product = 'learn')
        OR (pg_has_role(current_user, 'lityra_hire_runtime', 'member') AND u.product = 'hire')
        OR (pg_has_role(current_user, 'lityra_combined_fallback', 'member') AND u.product IN ('learn', 'hire')))
  ));

ALTER TABLE lare_auth.verification_tokens ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS product_verification_tokens_isolation ON lare_auth.verification_tokens;
CREATE POLICY product_verification_tokens_isolation ON lare_auth.verification_tokens
  USING (EXISTS (
    SELECT 1 FROM lare_auth.users u WHERE u.id = user_id
      AND ((pg_has_role(current_user, 'lityra_learn_runtime', 'member') AND u.product = 'learn')
        OR (pg_has_role(current_user, 'lityra_hire_runtime', 'member') AND u.product = 'hire')
        OR (pg_has_role(current_user, 'lityra_combined_fallback', 'member') AND u.product IN ('learn', 'hire')))
  ))
  WITH CHECK (EXISTS (
    SELECT 1 FROM lare_auth.users u WHERE u.id = user_id
      AND ((pg_has_role(current_user, 'lityra_learn_runtime', 'member') AND u.product = 'learn')
        OR (pg_has_role(current_user, 'lityra_hire_runtime', 'member') AND u.product = 'hire')
        OR (pg_has_role(current_user, 'lityra_combined_fallback', 'member') AND u.product IN ('learn', 'hire')))
  ));

-- Re-run this file after migrations so newly created tables receive grants.
COMMIT;
