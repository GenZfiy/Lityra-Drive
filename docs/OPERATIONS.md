# Lityra Hire operations

## Service ownership

The authoritative runtime list is `backend/services.txt`; it contains 23 processes: auth, candidate, drive, questionbank, exam, submission, anticheat, coding, evaluation, interview, result, notification, files, analytics, audit, ai_orchestration, organization, evidence, competency, decision, action, recruit_ai, and gateway. Shared libraries are copied into this project under `backend/libs`. Auth, coding, notification, files, analytics, audit, AI orchestration, organization, and gateway are also used by Learn and therefore have independent copies here; Hire-only services are not in Learn's registry.

## Database release and recovery

1. Take a verified database backup and test restore.
2. Use a disposable PostgreSQL database with a migration-owner credential and a restricted runtime credential.
3. Review account and role SQL in `migrations/`; run only the product's role/migration statements, then verify the denied cross-product access.
4. Keep a migration log and tested recovery plan. Never point local scripts at production accidentally.

The two products still may use the same Supabase project/cluster if configured that way. Separate schemas and roles do not remove that shared availability/billing failure domain. Historical unprefixed schemas require a reviewed data transition; this project does not migrate them. `migrations/` retains shared/auth, Hire-relevant and ambiguous release SQL history; Learn-only lesson, adaptive-drill, and practice-world migrations are excluded. The retained set is not a linear auto-run migration chain. Review each file against this product's service/schema inventory before applying.

The release helper initializes registered service metadata in sequence and records an idempotent release ID; it does not apply every SQL file in `migrations/`. For a disposable or approved staging DB only: set `MIGRATION_DATABASE_URL` to the migration-owner credential, then run `python backend/tools/release.py --product hire --release 20261010_01` (choose a new unique ID for each release). Apply reviewed SQL separately in a transaction where supported. Recovery uses a verified pre-release backup and a reviewed forward repair; never assume arbitrary feature SQL has a safe down migration.

Access and refresh tokens remain in product-namespaced browser localStorage. This keeps product keys separate but remains exposed to same-origin script compromise; HttpOnly-cookie/CSRF migration is not included. Code execution remains disabled until a production sandbox is verified.

## Deploy

Configure independent Render and Netlify services from `deployment/render.yaml` and `deployment/netlify.toml`. Add secrets in the hosting dashboard. Set product-specific CORS origins, database URL, JWT issuer/audience and signing secrets. Keep `SKIP_INIT=1`; run reviewed release operations separately. Configure health checks at `/health`, verify `/ready` if enabled, then deploy staging before production. Retain the previous deployment for rollback.

## Validation matrix

- Frontend npm install/build and local boundary check: run from this folder.
- Backend syntax: `python -m compileall -q backend/services backend/libs`.
- Unit/integration, product JWT checks, DB role-denial checks and migrations: require service dependencies and disposable PostgreSQL; status is NOT RUN until actually executed.
- Hosted health, CORS, external integrations and LMS/Hire workflows: NOT RUN in this local extraction.
