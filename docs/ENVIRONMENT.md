# Hire environment reference

Set secrets in the local untracked root `.env` or the hosting provider's secret store. `.env.example` contains placeholders only.

| Variable | Purpose |
| --- | --- |
| `DATABASE_URL` | Hire-only restricted PostgreSQL runtime credential; TLS enabled. |
| `JWT_SECRET`, `INTERNAL_JWT_SECRET` | Independent signing secrets; rotate any value previously shared publicly. |
| `JWT_ISSUER`, `JWT_AUDIENCE`, `AUTH_ALLOWED_PRODUCT` | Set to `lityra-hire-auth`, `lityra-hire-api`, and `hire`. |
| `APP_PRODUCT` | Must be `hire` for the backend container. |
| `CORS_ORIGINS` | Comma-separated exact Netlify/custom-domain origins; no wildcard in production. |
| `PORT`, `HOST` | Hosting port and public gateway bind; Render sets `PORT`, gateway binds `0.0.0.0`. |
| `SERVICE_REGISTRY_PATH` | Container registry path `/app/backend/services.txt`; local entrypoint default is used otherwise. |
| `SKIP_INIT` | Keep `1` for web processes; perform reviewed release work separately. |
| `DB_POOL_SIZE`, `DB_MAX_OVERFLOW`, `DB_POOL_TIMEOUT` | Bound each service's DB connections; copied defaults are small. |
| `VITE_API_TARGET` | Optional local Vite proxy target, normally `http://127.0.0.1:8000`. |
| `VITE_API_BASE_URL` | Frontend production API base; set in Netlify build environment. |
| `GEMINI_API_KEY`, `MISTRAL_API_KEY`, SMTP variables, `REDIS_URL` | Optional integrations; omit or disable providers not configured. |

Never put backend credentials in Netlify variables with a `VITE_` prefix because Vite embeds those into browser assets.
