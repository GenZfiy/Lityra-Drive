# RBAC / Super Admin / Analytics program — deployment runbook

Five phases shipped together: RBAC engine, data-scope isolation, Super Admin
portal, hierarchical analytics + role dashboards, and audit logging. Everything
below is **additive** — safe to run against the shared RDS while the old code is
still serving, then roll the code out with no downtime window.

Run the steps **in order**. Do not skip the migrations: login and `/me` now read
the new `roles`/`user_roles` columns.

## 1. Migrations (shared RDS — run once)

```bash
# From repo root, with DATABASE_URL pointing at the target DB.
psql "$DATABASE_URL" -f backend/migrations/rbac_engine.sql       # roles: scope_level, is_system, is_active, created_at
psql "$DATABASE_URL" -f backend/migrations/scope_isolation.sql   # user_roles: branch_id, cohort_id (+ indexes)
```

## 2. Seed (idempotent — inserts the RBAC catalog)

```bash
cd backend/services/auth
python manage.py seed     # permission catalog, new roles (principal/dean/tpo/faculty),
                          # default grants, flags built-in roles is_system + scope
```

Expected tail: `[seed] RBAC ready — 26 permissions, 10 roles`.

## 3. Deploy code

```bash
git pull
./redeploy.sh             # rebuilds/reloads all services + frontend
```

The auth service now also publishes admin events → `lare-audit` (already a
wildcard sink) records them. No new infra needed.

## 4. Verify end-to-end

- **Login still works** and `GET /auth/v1/me` returns `permissions` + `scope_level`.
- **Super Admin** sees the new nav items: User Management, Roles & Permissions,
  Audit Trail, Institution Analytics.
- **Roles & Permissions** (`/lms/roles`) lists 10 roles + 26 permissions; editing
  a role's permissions saves.
- **User Management** (`/lms/users`) lists users; assign a scoped role (e.g. make
  someone `dean` of a branch) → after they re-login, they see only that branch in
  **Institution Analytics**, and are blocked from other branches.
- **Audit Trail** (`/lms/audit`) shows the role/status changes you just made;
  "Verify integrity" reports the chain intact.

## Rollback

The migrations only ADD columns, so old code keeps working against the new
schema. To roll back, redeploy the previous code — no schema down-migration
required. (Dropping the columns is optional and only if you truly abandon RBAC.)

## Still requires a human (not automatable here)

- Rotate the previously-exposed secrets: Gemini API key, Zoho SMTP password,
  admin password `Lare@2025`.
