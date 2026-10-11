"""Run an explicit, serialized product schema release.

Use MIGRATION_DATABASE_URL with a migration owner account. Web services must
use DATABASE_URL with a restricted runtime role and SKIP_INIT=1.
"""
from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path

from sqlalchemy import create_engine, text
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT.parent / ".env")
REGISTRIES = {"hire": ROOT / "services.txt"}
RELEASE_SCHEMA = "lityra_release"


def parse_registry(product: str) -> list[tuple[str, str, str]]:
    entries = []
    for line in REGISTRIES[product].read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        if len(parts) != 3:
            raise ValueError(f"Invalid registry row in {REGISTRIES[product].name}")
        name, directory, port = parts
        if name != "gateway":
            entries.append((name, directory, port))
    return entries


def schema_for(service: str, product: str) -> str:
    name = service.replace("-", "_")
    if name in {"coding", "notification", "files", "analytics", "audit",
                "ai_orchestration", "organization"}:
        return f"{product}_{name}"
    return f"lare_{name}" if name in {"auth", "storage", "realtime", "graphql", "vault", "cron", "net", "extensions"} else name


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--product", choices=REGISTRIES, required=True)
    parser.add_argument("--release", required=True, help="Immutable release id, e.g. 20261010_01")
    args = parser.parse_args()
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}", args.release):
        parser.error("--release must be 1-64 safe identifier characters")

    url = os.environ.get("MIGRATION_DATABASE_URL")
    if not url:
        print("MIGRATION_DATABASE_URL is required; refusing to use a web runtime credential.", file=sys.stderr)
        return 2
    if not url.startswith(("postgresql://", "postgresql+psycopg://", "postgres://")):
        print("MIGRATION_DATABASE_URL must use PostgreSQL.", file=sys.stderr)
        return 2

    engine = create_engine(url, pool_size=1, max_overflow=0, pool_timeout=10, connect_args={"connect_timeout": 8})
    try:
        with engine.connect() as lock_conn:
            locked = lock_conn.execute(text("SELECT pg_try_advisory_lock(781204261)")).scalar()
            if not locked:
                print("Another Lityra release command holds the migration lock.", file=sys.stderr)
                return 3
            lock_conn.commit()
            try:
                lock_conn.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{RELEASE_SCHEMA}"'))
                lock_conn.execute(text(
                    f'''CREATE TABLE IF NOT EXISTS "{RELEASE_SCHEMA}".history (
                        product text NOT NULL CHECK (product IN ('learn', 'hire')),
                        release_id text NOT NULL,
                        completed_at timestamptz NOT NULL DEFAULT now(),
                        PRIMARY KEY (product, release_id)
                    )'''
                ))
                lock_conn.commit()
                exists = lock_conn.execute(text(
                    f'SELECT 1 FROM "{RELEASE_SCHEMA}".history WHERE product=:p AND release_id=:r'
                ), {"p": args.product, "r": args.release}).scalar()
                lock_conn.commit()
                if exists:
                    print(f"Release {args.release} is already recorded for {args.product}; no work performed.")
                    return 0

                env = os.environ.copy()
                env["DATABASE_URL"] = url
                env["APP_PRODUCT"] = args.product
                # Service entry points import the shared package from backend/libs.
                # They run with each service directory as cwd, so this path is not
                # otherwise discoverable when release.py is launched from the repo.
                shared_libs = str(ROOT / "libs")
                inherited_pythonpath = env.get("PYTHONPATH")
                env["PYTHONPATH"] = os.pathsep.join(
                    part for part in (shared_libs, inherited_pythonpath) if part
                )
                for name, directory, port in parse_registry(args.product):
                    service_dir = ROOT / "services" / directory
                    if not (service_dir / "manage.py").is_file():
                        raise RuntimeError(f"Missing manage.py for registered service {name}")
                    service_schema = schema_for(name, args.product)
                    env.update(DB_SCHEMA=service_schema, SERVICE_NAME=name, PORT=port)
                    if name == "auth":
                        env["AUTH_ALLOWED_PRODUCT"] = args.product
                    print(f"[release] initializing {name} (schema={service_schema})", flush=True)
                    result = subprocess.run(
                        [sys.executable, "manage.py", "init-db"], cwd=service_dir,
                        env=env, check=False, timeout=180,
                    )
                    if result.returncode:
                        print(f"Release stopped at {name}; it is safe to rerun after resolving the failure.", file=sys.stderr)
                        return result.returncode

                lock_conn.execute(text(
                    f'INSERT INTO "{RELEASE_SCHEMA}".history(product, release_id) VALUES (:p, :r)'
                ), {"p": args.product, "r": args.release})
                lock_conn.commit()
                print(f"[release] completed {args.product} release {args.release}")
                return 0
            finally:
                lock_conn.execute(text("SELECT pg_advisory_unlock(781204261)"))
                lock_conn.commit()
    except subprocess.TimeoutExpired as exc:
        print(f"Release timed out while initializing {exc.cmd[-1]}; no completion record was written.", file=sys.stderr)
        return 124
    except Exception as exc:  # do not print connection URLs or driver reprs
        print(f"Release failed ({type(exc).__name__}). Check database connectivity and migration permissions.", file=sys.stderr)
        return 1
    finally:
        engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
