"""Disposable PostgreSQL integration test for the product-role SQL migrations."""
from __future__ import annotations

import os
import sys
from pathlib import Path
from sqlalchemy import select, text

import psycopg
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "libs"))
sys.path.insert(0, str(ROOT / "services" / "auth"))
sys.path.insert(0, str(ROOT / "tools"))
from lare_common.db import Database  # noqa: E402
from app.models import Role, User, UserRole  # noqa: E402
from check_product_db_isolation import OWNED, check  # noqa: E402
from release import schema_for  # noqa: E402


def main() -> int:
    for product in ("learn", "hire"):
        for service in ("coding", "notification", "files", "analytics", "audit",
                        "ai_orchestration", "organization"):
            if schema_for(service, product) != f"{product}_{service}":
                raise AssertionError(f"{product} {service} is not product-schema isolated")
    if schema_for("institution", "learn") != "institution" or schema_for("drive", "hire") != "drive":
        raise AssertionError("Product-private service schema mapping changed unexpectedly")

    admin_url = os.getenv("PRODUCT_ISOLATION_TEST_ADMIN_URL", "")
    parsed = make_url(admin_url) if admin_url else None
    if (not parsed or parsed.get_backend_name() != "postgresql"
            or parsed.host not in ("127.0.0.1", "localhost")
            or "test" not in (parsed.database or "").lower()):
        print("Set PRODUCT_ISOLATION_TEST_ADMIN_URL to a disposable localhost database with 'test' in its name.", file=sys.stderr)
        return 2

    shared_schemas = {"coding", "notification", "files", "analytics", "audit",
                      "ai_orchestration", "organization"}
    product_shared_schemas = {f"{product}_{schema}" for product in ("learn", "hire")
                              for schema in shared_schemas}
    schemas = (set(OWNED["learn"]) | set(OWNED["hire"]) | shared_schemas
               | product_shared_schemas | {"lare_auth"})
    psycopg_url = admin_url.replace("postgresql+psycopg://", "postgresql://", 1)
    with psycopg.connect(psycopg_url) as conn:
        for schema in schemas:
            if not schema.replace("_", "").isalnum():
                raise ValueError("Unexpected schema name in ownership map")
            conn.execute(f'CREATE SCHEMA IF NOT EXISTS "{schema}"')
            if schema != "lare_auth":
                conn.execute(f'CREATE TABLE IF NOT EXISTS "{schema}".product_isolation_probe (id integer PRIMARY KEY)')
                conn.execute(f'INSERT INTO "{schema}".product_isolation_probe (id) VALUES (1) ON CONFLICT DO NOTHING')

    # Build the real auth schema through SQLAlchemy metadata, then simulate the
    # current shared-role catalog and a Hire assignment that needs rebinding.
    db = Database(admin_url, schema="lare_auth")
    db.create_all()
    with Session(db.engine) as s, s.begin():
        role = s.execute(select(Role).where(Role.name == "migration_probe",
                                            Role.product == "learn")).scalar_one_or_none()
        if not role:
            role = Role(id="learn-probe-role", name="migration_probe", product="learn",
                        description="migration test", scope_level="self",
                        is_system=False, is_active=True)
            s.add(role)
        users = {}
        for product in ("learn", "hire"):
            user = s.execute(select(User).where(User.email == f"{product}@migration.test",
                                                User.product == product)).scalar_one_or_none()
            if not user:
                user = User(id=f"{product}-migration-user", email=f"{product}@migration.test",
                            product=product, password_hash="not-a-login-hash",
                            tenant_id="migration-test", status="active")
                s.add(user)
            users[product] = user
        s.flush()
        for product in ("learn", "hire"):
            link = s.execute(select(UserRole).where(
                UserRole.user_id == users[product].id,
                UserRole.role_id == role.id,
            )).scalar_one_or_none()
            if not link:
                s.add(UserRole(id=f"{product}-migration-role", user_id=users[product].id,
                               role_id=role.id, college_id=None))

    migration_root = ROOT.parent / "migrations" if (ROOT.parent / "migrations").exists() else ROOT / "migrations"
    migration_dir = migration_root / "products"
    with psycopg.connect(psycopg_url) as conn:
        # Exercise the account/product transition before RLS and catalog roles.
        conn.execute((migration_root / "separate_accounts.sql").read_text(encoding="utf-8"), prepare=False)
        for filename in ("001_product_database_roles.sql", "002_product_role_catalog.sql"):
            conn.execute((migration_dir / filename).read_text(encoding="utf-8"), prepare=False)

    with Session(db.engine) as s:
        hire_assignment = s.execute(
            select(UserRole, Role).join(Role, Role.id == UserRole.role_id)
            .where(UserRole.user_id == "hire-migration-user")
        ).one()
        if hire_assignment[1].product != "hire":
            raise AssertionError("Hire assignment was not rebound to a Hire role")
        cross_role_ids = {
            product: s.execute(select(Role.id).where(Role.name == "migration_probe",
                                                      Role.product == product)).scalar_one()
            for product in ("learn", "hire")
        }

    # These fixed credentials exist only in the disposable CI service database.
    with psycopg.connect(psycopg_url) as conn:
        conn.execute("CREATE ROLE lityra_learn_test LOGIN PASSWORD 'ci-only-test-password'")
        conn.execute("CREATE ROLE lityra_hire_test LOGIN PASSWORD 'ci-only-test-password'")
        conn.execute("GRANT lityra_learn_runtime TO lityra_learn_test")
        conn.execute("GRANT lityra_hire_runtime TO lityra_hire_test")

    errors = []
    for product, login in (("learn", "lityra_learn_test"), ("hire", "lityra_hire_test")):
        url = parsed.set(username=login, password="ci-only-test-password")
        other = "hire" if product == "learn" else "learn"
        errors.extend(check(product, url.render_as_string(hide_password=False),
                            foreign_user_id=f"{other}-migration-user",
                            foreign_role_id=cross_role_ids[other]))

    # The fallback group is dormant until explicitly granted to an old combined
    # login. Verify it sees both products before and after the role merge.
    with psycopg.connect(psycopg_url) as conn:
        conn.execute("CREATE ROLE lityra_legacy_test LOGIN PASSWORD 'ci-only-test-password'")
        conn.execute("GRANT lityra_combined_fallback TO lityra_legacy_test")
    fallback_url = parsed.set(username="lityra_legacy_test", password="ci-only-test-password")
    fallback_engine = create_engine(fallback_url.render_as_string(hide_password=False))
    with fallback_engine.connect() as conn:
        if conn.execute(text("SELECT count(*) FROM lare_auth.users")).scalar_one() != 2:
            raise AssertionError("Combined fallback cannot see both account products")

    with psycopg.connect(psycopg_url) as conn:
        conn.execute((migration_dir / "003_combined_fallback_rollback.sql").read_text(encoding="utf-8"), prepare=False)
    with fallback_engine.connect() as conn:
        duplicate_names = conn.execute(text("""
            SELECT count(*) FROM (
              SELECT name FROM lare_auth.roles GROUP BY name HAVING count(*) > 1
            ) duplicates
        """)).scalar_one()
        hire_assignment_product = conn.execute(text("""
            SELECT r.product FROM lare_auth.user_roles ur
            JOIN lare_auth.roles r ON r.id = ur.role_id
            WHERE ur.user_id = 'hire-migration-user'
        """)).scalar_one()
        if duplicate_names or hire_assignment_product != "learn":
            raise AssertionError("Combined role catalog rollback did not restore a unique legacy role catalog")
        if conn.execute(text("SELECT count(*) FROM lare_auth.users")).scalar_one() != 2:
            raise AssertionError("Combined fallback lost visibility to account data during rollback")
    fallback_engine.dispose()
    db.engine.dispose()
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1
    print("Product-role SQL migrations, isolation checks, and combined-catalog rollback passed on disposable PostgreSQL.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
