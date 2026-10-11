# Lityra Hire RBAC

## Implemented authorization flow

1. Auth resolves active roles and their permissions for the selected product when it issues a short-lived access token.
2. The Hire gateway validates the token product, signature, issuer, and audience, then signs an internal identity context for downstream services.
3. Services trust only the signed internal context or a valid access token. Unsigned `X-User-Id`, `X-Roles`, and `X-Permissions` headers do not establish identity.
4. Backend routes use centralized permission checks for access, user and role administration, drive operations, candidate access, results, interviews, question banks, and evaluation.
5. Record checks constrain drive records to platform operators, drive creators, or college bindings. Recruiter candidate access is resolved from registrations in drives visible to that recruiter. Interviewers can review only interviews assigned to their user ID.

Frontend route and navigation checks use the same permission codes. They improve presentation only; backend checks remain authoritative.

## Hire role summary

| Role | Intended scope | Core Hire capabilities |
| --- | --- | --- |
| `super_admin` | Platform | Full catalog, role/user administration, operations, and auditing |
| `company_admin` | Hire product operator | User administration, organization-wide Hire operations, publishing, exports, analytics; cannot edit role definitions by default |
| `tpo` | Bound college | Manage placement drives, candidates, interviews, questions, access codes, results, and college analytics |
| `recruiter` | Self / drives created by the recruiter | Manage own drives, registered candidates, interviews, assessments, exports, and publishing |
| `interviewer` | Assigned interviews | View assigned interviews and submit interview feedback/decisions |
| `college_admin` | Bound college | View drives and college operations granted in its permission set |
| `student` | Self | Own profile and application flows; enter drives only with a valid drive access grant |

The Auth catalog also contains LMS roles because the auth implementation shares catalog structures. LMS-only permissions are filtered from Hire role grants and Hire tokens. Only roles with Hire workflows should be assigned in Hire.

## Administrative safeguards

- Role grants are product- and tenant-checked, reject self-changes and unauthorized privilege expansion, enforce role scope bindings, and require delegated permissions to be held by the actor.
- Company-admin user listings and user detail/status operations are tenant bounded. Super admins retain platform access within the configured product service.
- Inactive roles are excluded from role claims, effective permissions, and scope bindings when new tokens are issued.
- Login access tokens default to 15 minutes. `ACCESS_TOKEN_TTL_MIN` can override this; increasing it extends the maximum stale-permission window. Refresh tokens rotate and reuse revokes the token family.
- Role and permission seed updates are additive and idempotent. No database was contacted by this implementation.

## Deployment and verification

Back up the Hire auth database before applying the updated catalog. Against the Hire database only, run the existing auth initializer after confirming its `DATABASE_URL` and `AUTH_ALLOWED_PRODUCT=hire`:

```powershell
cd Lityra-hire\backend\services\auth
..\..\.venv\Scripts\python.exe manage.py init-db
```

The initializer creates missing auth tables and seeds missing Hire permissions/roles; it does not drop user, role, candidate, or drive data. Test the resulting role catalog and authentication in staging before production.

Local checks executed for this implementation:

- Auth product/security tests: 13 passed using in-memory SQLite.
- Gateway product-claim/readiness tests: 4 passed.
- Analytics scope tests: 3 passed using in-memory SQLite.
- Python `compileall` for Hire common libraries and backend services: passed.
- Hire frontend production build: passed. Vite reported a chunk-size advisory for the Three.js vendor chunk.
- Frontend product-boundary check: passed (23 services).

## Remaining schema-level work

Hire `drives` and `analytics` fact records do not currently persist a tenant identifier. Existing route guards constrain recruiters and college-scoped staff by creator/college, but a product-wide company operator currently has platform scope. Full tenant isolation for these rows requires a versioned migration to add and backfill tenant ownership, then query filters and negative cross-tenant tests. Do not treat this build as a substitute for that production migration.

Some secondary service endpoints still use centralized role-name guards rather than the granular permission catalog. They remain server-side protected; custom roles cannot use those endpoints solely by receiving a permission unless the route is migrated. Audit and migrate those endpoints before advertising a fully customizable permission model.

The PostgreSQL migration/isolation integration suite requires a disposable local PostgreSQL database and was not run. No production database, external credentials, or hosted service was accessed.
