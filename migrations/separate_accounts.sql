-- LARE — separate accounts per product (LARE Learn vs LARE Hire)
-- ============================================================================
-- Splits the single global-email account model into per-product accounts:
-- the same email may exist once for Learn and once for Hire, each with its own
-- password. Identity becomes UNIQUE (email, product) instead of UNIQUE (email).
--
-- Backfill of EXISTING accounts is BY ROLE (confirmed):
--     recruiter / company_admin  -> 'hire'
--     everyone else              -> 'learn'   (students, trainers, admins)
--
-- Idempotent. Schema: lare_auth. Review, BACK UP the users table, then run
-- against the target DB deliberately (do NOT run this casually against prod).
--   psql "$DATABASE_URL" -f backend/migrations/separate_accounts.sql
-- ============================================================================

SET search_path TO lare_auth, public;

-- 1) Add the product column (defaults existing rows to 'learn').
ALTER TABLE users ADD COLUMN IF NOT EXISTS product varchar(16) NOT NULL DEFAULT 'learn';

-- 2) Backfill BY ROLE: mark accounts that hold a recruiter/company_admin role
--    as Hire; everything else stays Learn (the column default).
UPDATE users u
   SET product = 'hire'
  FROM user_roles ur
  JOIN roles r ON r.id = ur.role_id
 WHERE ur.user_id = u.id
   AND r.name IN ('recruiter', 'company_admin');

-- 3) Drop the old single-column UNIQUE on email (constraint or unique index),
--    whatever its generated name is, so (email, product) can become the key.
DO $$
DECLARE c record;
BEGIN
  -- unique/pk CONSTRAINTS on users that cover exactly (email)
  FOR c IN
    SELECT con.conname
      FROM pg_constraint con
      JOIN pg_class rel  ON rel.oid = con.conrelid
      JOIN pg_namespace ns ON ns.oid = rel.relnamespace
     WHERE rel.relname = 'users' AND ns.nspname = 'lare_auth'
       AND con.contype = 'u'
       AND (SELECT array_agg(att.attname::text ORDER BY att.attname)
              FROM unnest(con.conkey) k
              JOIN pg_attribute att ON att.attrelid = con.conrelid AND att.attnum = k
           ) = ARRAY['email']::text[]
  LOOP
    EXECUTE format('ALTER TABLE lare_auth.users DROP CONSTRAINT %I', c.conname);
  END LOOP;

  -- standalone UNIQUE INDEXES on users over exactly (email) that are not constraints
  FOR c IN
    SELECT i.indexname
      FROM pg_indexes i
     WHERE i.schemaname = 'lare_auth' AND i.tablename = 'users'
       AND i.indexdef ILIKE '%UNIQUE%(email)%'
       AND i.indexname NOT IN (
         SELECT conname FROM pg_constraint WHERE conrelid = 'lare_auth.users'::regclass)
  LOOP
    EXECUTE format('DROP INDEX IF EXISTS lare_auth.%I', c.indexname);
  END LOOP;
END $$;

-- 4) New composite key: one account per (email, product).
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint
     WHERE conname = 'uq_users_email_product'
       AND conrelid = 'lare_auth.users'::regclass
  ) THEN
    ALTER TABLE lare_auth.users
      ADD CONSTRAINT uq_users_email_product UNIQUE (email, product);
  END IF;
END $$;

-- 4b) ADMINS get access to BOTH products. For every admin account (super_admin /
--     company_admin / college_admin) that exists in only one product, create a
--     twin account in the other product (same password to start) and copy its
--     roles. They can then log into both Learn and Hire with the same email.
DO $$
DECLARE a record; nid text; other text;
BEGIN
  FOR a IN
    SELECT DISTINCT u.id AS uid, u.email, u.product, u.password_hash, u.full_name,
                    u.tenant_id, u.status, u.email_verified, u.mfa_enabled
      FROM users u
      JOIN user_roles ur ON ur.user_id = u.id
      JOIN roles r       ON r.id = ur.role_id
     WHERE r.name IN ('super_admin', 'company_admin', 'college_admin')
  LOOP
    other := CASE WHEN a.product = 'learn' THEN 'hire' ELSE 'learn' END;
    IF EXISTS (SELECT 1 FROM users WHERE email = a.email AND product = other) THEN
      CONTINUE;  -- twin already present
    END IF;
    nid := md5(random()::text || clock_timestamp()::text || a.email || other);
    INSERT INTO users (id, email, product, password_hash, full_name, tenant_id,
                       status, email_verified, mfa_enabled, failed_attempts, created_at)
    VALUES (nid, a.email, other, a.password_hash, a.full_name, a.tenant_id,
            a.status, a.email_verified, a.mfa_enabled, 0, now());
    INSERT INTO user_roles (id, user_id, role_id, college_id)
    SELECT md5(random()::text || clock_timestamp()::text || ur.role_id),
           nid, ur.role_id, ur.college_id
      FROM user_roles ur
     WHERE ur.user_id = a.uid;
  END LOOP;
END $$;

-- 5) Keep a plain index on email for lookups (non-unique now).
CREATE INDEX IF NOT EXISTS ix_users_email ON users (email);

-- Rollback (manual): drop uq_users_email_product, re-add UNIQUE(email) after
-- de-duplicating, then DROP COLUMN product.
