# Lityra Hire architecture and ownership

The independent API container starts only `backend/services.txt`. The registry is the contract used by the product-local entrypoint, release script, and boundary check. The frontend entry is `frontend/apps/hire/index.html`; Vite's alias points only to `frontend/src` inside this project.

| Ownership | Services |
| --- | --- |
| Hire only | candidate, drive, questionbank, exam, submission, anticheat, evaluation, interview, result, evidence, competency, decision, action, recruit_ai |
| Independent Hire copy of shared capabilities | auth, coding, notification, files, analytics, audit, ai_orchestration, organization, gateway |

Shared code is copied locally into each product to avoid sibling-directory or shared-package-at-runtime dependencies. The deployments may still share a Supabase cluster, email provider, AI vendors, and Netlify/Render accounts if configured that way.

## Configuration

Backend secrets are environment variables from the root `.env.example`: `DATABASE_URL`, `JWT_SECRET`, `INTERNAL_JWT_SECRET`, `CORS_ORIGINS`, AI/email credentials as enabled, and bounded DB pool settings. Runtime identity must be a product-scoped least-privilege role. Set `APP_PRODUCT=hire`, `AUTH_ALLOWED_PRODUCT=hire`, and distinct Hire issuer/audience values. The frontend uses `VITE_API_TARGET` for local dev proxy and `VITE_API_BASE_URL` for the production API origin.

## Database ownership

Hire-only service schemas are owned by Hire. Shared-service schemas use the `hire_` prefix in independent deployment. The `lare_auth` schema currently contains product-aware identity and role data and requires its row-level policy plus product-role migration to be applied and tested. This source split does not itself create database roles or prove isolation. Use `backend/tools/check_product_db_isolation.py` and the disposable database harness in `backend/tools/test_product_role_migrations.py` only with reviewed, non-production database URLs.
