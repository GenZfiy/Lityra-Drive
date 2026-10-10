-- Optional rollback only: run after both products stop receiving traffic.
-- Collapses product copies into one role catalog for the combined fallback.
-- Refuses role-permission/scope conflicts rather than widening privileges.
BEGIN;
SELECT pg_advisory_xact_lock(781204262);

DO $$ BEGIN
  IF EXISTS (
    SELECT 1 FROM lare_auth.roles h
    JOIN lare_auth.roles l ON l.name = h.name AND l.product = 'learn'
    WHERE h.product = 'hire'
      AND (h.description IS DISTINCT FROM l.description
        OR h.scope_level IS DISTINCT FROM l.scope_level
        OR h.is_system IS DISTINCT FROM l.is_system
        OR h.is_active IS DISTINCT FROM l.is_active)
  ) THEN
    RAISE EXCEPTION 'Cannot merge product roles: matching roles have different attributes';
  END IF;
  IF EXISTS (
    SELECT name FROM lare_auth.roles WHERE product = 'hire'
    INTERSECT
    SELECT name FROM lare_auth.roles WHERE product = 'learn'
  ) AND EXISTS (
    SELECT l.name
    FROM lare_auth.roles l
    JOIN lare_auth.roles h ON h.name = l.name AND h.product = 'hire'
    WHERE l.product = 'learn'
      AND (
        EXISTS (
          SELECT p.code FROM lare_auth.role_permissions rp
          JOIN lare_auth.permissions p ON p.id = rp.permission_id
          WHERE rp.role_id = l.id
          EXCEPT
          SELECT p.code FROM lare_auth.role_permissions rp
          JOIN lare_auth.permissions p ON p.id = rp.permission_id
          WHERE rp.role_id = h.id
        ) OR EXISTS (
          SELECT p.code FROM lare_auth.role_permissions rp
          JOIN lare_auth.permissions p ON p.id = rp.permission_id
          WHERE rp.role_id = h.id
          EXCEPT
          SELECT p.code FROM lare_auth.role_permissions rp
          JOIN lare_auth.permissions p ON p.id = rp.permission_id
          WHERE rp.role_id = l.id
        )
      )
  ) THEN
    RAISE EXCEPTION 'Cannot merge product roles: matching roles have different permission sets';
  END IF;
END $$;

-- Keep a recoverable record of product-specific IDs and bindings before the
-- active legacy catalog is collapsed. Existing audit events retain their IDs.
CREATE TABLE IF NOT EXISTS lare_auth.product_role_rollback_archive (
  role_id text PRIMARY KEY,
  role_data jsonb NOT NULL,
  archived_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS lare_auth.product_assignment_rollback_archive (
  assignment_id text PRIMARY KEY,
  assignment_data jsonb NOT NULL,
  archived_at timestamptz NOT NULL DEFAULT now()
);
INSERT INTO lare_auth.product_role_rollback_archive (role_id, role_data)
SELECT r.id, jsonb_build_object(
  'id', r.id, 'name', r.name, 'product', r.product,
  'description', r.description, 'scope_level', r.scope_level,
  'is_system', r.is_system, 'is_active', r.is_active,
  'created_at', r.created_at,
  'permissions', COALESCE((
    SELECT jsonb_agg(p.code ORDER BY p.code)
    FROM lare_auth.role_permissions rp
    JOIN lare_auth.permissions p ON p.id = rp.permission_id
    WHERE rp.role_id = r.id
  ), '[]'::jsonb)
)
FROM lare_auth.roles r WHERE r.product = 'hire'
ON CONFLICT (role_id) DO NOTHING;
INSERT INTO lare_auth.product_assignment_rollback_archive (assignment_id, assignment_data)
SELECT ur.id, jsonb_build_object(
  'id', ur.id, 'user_id', ur.user_id, 'role_id', ur.role_id,
  'college_id', ur.college_id, 'branch_id', ur.branch_id,
  'cohort_id', ur.cohort_id, 'role_product', r.product
)
FROM lare_auth.user_roles ur
JOIN lare_auth.users u ON u.id = ur.user_id AND u.product = 'hire'
JOIN lare_auth.roles r ON r.id = ur.role_id AND r.product = 'hire'
ON CONFLICT (assignment_id) DO NOTHING;

-- Keep the Learn role IDs for built-ins and matching roles. Preserve unique
-- Hire-only custom roles by moving them to the combined catalog unchanged.
UPDATE lare_auth.user_roles ur
SET role_id = learn_role.id
FROM lare_auth.users u,
     lare_auth.roles hire_role,
     lare_auth.roles learn_role
WHERE ur.user_id = u.id
  AND hire_role.id = ur.role_id
  AND hire_role.product = 'hire'
  AND learn_role.name = hire_role.name
  AND learn_role.product = 'learn'
  AND u.product = 'hire';

DELETE FROM lare_auth.roles h
USING lare_auth.roles l
WHERE h.product = 'hire'
  AND l.product = 'learn'
  AND l.name = h.name;

UPDATE lare_auth.roles SET product = 'learn' WHERE product = 'hire';

-- Restore global role-name uniqueness expected by the former combined app.
ALTER TABLE lare_auth.roles DROP CONSTRAINT IF EXISTS uq_roles_name_product;
DROP INDEX IF EXISTS lare_auth.uq_roles_name_product;
DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conrelid = 'lare_auth.roles'::regclass AND conname = 'roles_name_key'
  ) THEN
    ALTER TABLE lare_auth.roles ADD CONSTRAINT roles_name_key UNIQUE (name);
  END IF;
END $$;

-- The explicitly assigned fallback login can see a merged combined catalog;
-- product logins remain bound to matching user and role products.
DROP POLICY IF EXISTS product_user_roles_isolation ON lare_auth.user_roles;
CREATE POLICY product_user_roles_isolation ON lare_auth.user_roles
  USING (EXISTS (
    SELECT 1 FROM lare_auth.users u JOIN lare_auth.roles r ON r.id = role_id
    WHERE u.id = user_id AND (
      (pg_has_role(current_user, 'lityra_learn_runtime', 'member') AND u.product = 'learn' AND r.product = 'learn') OR
      (pg_has_role(current_user, 'lityra_hire_runtime', 'member') AND u.product = 'hire' AND r.product = 'hire') OR
      (pg_has_role(current_user, 'lityra_combined_fallback', 'member') AND u.product IN ('learn', 'hire'))
    )
  ))
  WITH CHECK (EXISTS (
    SELECT 1 FROM lare_auth.users u JOIN lare_auth.roles r ON r.id = role_id
    WHERE u.id = user_id AND (
      (pg_has_role(current_user, 'lityra_learn_runtime', 'member') AND u.product = 'learn' AND r.product = 'learn') OR
      (pg_has_role(current_user, 'lityra_hire_runtime', 'member') AND u.product = 'hire' AND r.product = 'hire') OR
      (pg_has_role(current_user, 'lityra_combined_fallback', 'member') AND u.product IN ('learn', 'hire'))
    )
  ));

COMMIT;
