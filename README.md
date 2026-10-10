# Lityra Hire

Standalone Lityra Hire application. This directory contains its own frontend and only the backend services in `backend/services.txt`; it does not require Lityra Learn's source.

## Frontend

```powershell
cd frontend
npm ci
npm run dev
npm run build
```

Set `VITE_API_BASE_URL` in the frontend environment for the deployed API.

## Backend

Copy `.env.example` to a private `.env`, configure the product-specific database URL, JWT secrets, CORS origins, and integration credentials. Never commit real credentials. The Render service uses `deployment/render.yaml`; release initialization is intentionally skipped during web startup.

Run the entire product locally without Docker from this project directory:

```powershell
python scripts/run_local.py --init-db
```

Use `--init-db` on the first run against a new Hire database to create its service tables. For later runs, use `python scripts/run_local.py`. The launcher reads this project's `.env`, installs missing Python and frontend dependencies, starts the Hire backend services and Vite, and reports the app at `http://127.0.0.1:5175`. Keep the terminal open; press Ctrl+C to stop the services. Learn and Hire use overlapping backend ports, so run one product at a time on this machine.

Use only the Hire database URL and credentials in this project's `.env`. Database initialization creates/updates tables and seeds built-in roles; inspect the target database before using `--init-db`. Production schema initialization should use a reviewed staging release and migration-owner credentials, never the web runtime credential.

## Database and security

Migration source files are in `migrations/`. Review `migrations/separate_accounts.sql` and `migrations/products/` in order against a backup and disposable PostgreSQL before any staging/production use. Existing shared tables may contain user data; no automatic data copy or production migration is performed. Follow `docs/OPERATIONS.md`.

## Validation limitations

This extraction does not imply staging, hosted database isolation, external integrations, or end-to-end workflows were verified. Run the validation matrix in `docs/OPERATIONS.md` before cutover.
