-- REVIEW REQUIRED; apply only after 001_product_database_roles.sql on staging.
-- Preserves current Learn assignments and creates matching Hire role records.
BEGIN;
SELECT pg_advisory_xact_lock(781204262);

ALTER TABLE lare_auth.roles
  ADD COLUMN IF NOT EXISTS product varchar(16) NOT NULL DEFAULT 'learn';

-- Existing role names were global. Replace that uniqueness rule with a product
-- scoped one so each product can independently manage roles with the same name.
ALTER TABLE lare_auth.roles DROP CONSTRAINT IF EXISTS roles_name_key;
CREATE UNIQUE INDEX IF NOT EXISTS uq_roles_name_product
  ON lare_auth.roles (name, product);

INSERT INTO lare_auth.roles
  (id, name, product, description, scope_level, is_system, is_active, created_at)
SELECT gen_random_uuid()::text, name, 'hire', description, scope_level,
       is_system, is_active, created_at
FROM lare_auth.roles AS learn_role
WHERE learn_role.product = 'learn'
ON CONFLICT (name, product) DO NOTHING;

INSERT INTO lare_auth.role_permissions (role_id, permission_id)
SELECT hire_role.id, rp.permission_id
FROM lare_auth.roles AS learn_role
JOIN lare_auth.roles AS hire_role
  ON hire_role.name = learn_role.name AND hire_role.product = 'hire'
JOIN lare_auth.role_permissions AS rp ON rp.role_id = learn_role.id
WHERE learn_role.product = 'learn'
ON CONFLICT (role_id, permission_id) DO NOTHING;

-- Rebind Hire users to their product-specific role copy. Learn rows keep their
-- original IDs and relationships. No user/account records are merged/deleted.
UPDATE lare_auth.user_roles AS ur
SET role_id = hire_role.id
FROM lare_auth.users AS u,
     lare_auth.roles AS learn_role,
     lare_auth.roles AS hire_role
WHERE ur.user_id = u.id
  AND learn_role.id = ur.role_id
  AND learn_role.product = 'learn'
  AND hire_role.name = learn_role.name
  AND hire_role.product = 'hire'
  AND u.product = 'hire';

-- Bind every role assignment to the same product as its user. The first
-- migration cannot express this until the catalog has a product column.
DROP POLICY IF EXISTS product_user_roles_isolation ON lare_auth.user_roles;
CREATE POLICY product_user_roles_isolation ON lare_auth.user_roles
  USING (EXISTS (
    SELECT 1 FROM lare_auth.users u
    JOIN lare_auth.roles r ON r.id = role_id
    WHERE u.id = user_id AND u.product = r.product
      AND ((pg_has_role(current_user, 'lityra_learn_runtime', 'member') AND u.product = 'learn')
        OR (pg_has_role(current_user, 'lityra_hire_runtime', 'member') AND u.product = 'hire')
        OR (pg_has_role(current_user, 'lityra_combined_fallback', 'member') AND u.product IN ('learn', 'hire')))
  ))
  WITH CHECK (EXISTS (
    SELECT 1 FROM lare_auth.users u
    JOIN lare_auth.roles r ON r.id = role_id
    WHERE u.id = user_id AND u.product = r.product
      AND ((pg_has_role(current_user, 'lityra_learn_runtime', 'member') AND u.product = 'learn')
        OR (pg_has_role(current_user, 'lityra_hire_runtime', 'member') AND u.product = 'hire')
        OR (pg_has_role(current_user, 'lityra_combined_fallback', 'member') AND u.product IN ('learn', 'hire')))
  ));

GRANT SELECT, INSERT, UPDATE, DELETE ON lare_auth.roles,
  lare_auth.role_permissions TO lityra_learn_runtime, lityra_hire_runtime,
  lityra_combined_fallback;
REVOKE ALL ON lare_auth.roles, lare_auth.role_permissions FROM PUBLIC;

ALTER TABLE lare_auth.roles ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS product_roles_isolation ON lare_auth.roles;
CREATE POLICY product_roles_isolation ON lare_auth.roles
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

ALTER TABLE lare_auth.role_permissions ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS product_role_permissions_isolation ON lare_auth.role_permissions;
CREATE POLICY product_role_permissions_isolation ON lare_auth.role_permissions
  USING (EXISTS (
    SELECT 1 FROM lare_auth.roles r WHERE r.id = role_id
      AND ((pg_has_role(current_user, 'lityra_learn_runtime', 'member') AND r.product = 'learn')
        OR (pg_has_role(current_user, 'lityra_hire_runtime', 'member') AND r.product = 'hire')
        OR pg_has_role(current_user, 'lityra_combined_fallback', 'member'))
  ))
  WITH CHECK (EXISTS (
    SELECT 1 FROM lare_auth.roles r WHERE r.id = role_id
      AND ((pg_has_role(current_user, 'lityra_learn_runtime', 'member') AND r.product = 'learn')
        OR (pg_has_role(current_user, 'lityra_hire_runtime', 'member') AND r.product = 'hire')
        OR pg_has_role(current_user, 'lityra_combined_fallback', 'member'))
  ));

-- Permissions are shared immutable catalog entries. Runtime products may read
-- these rows but cannot add/change permission codes; migrations own the catalog.
COMMIT;
