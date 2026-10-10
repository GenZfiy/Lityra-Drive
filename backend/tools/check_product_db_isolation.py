"""Verify product DB grants against a non-production database.

Set LEARN_TEST_DATABASE_URL and HIRE_TEST_DATABASE_URL to distinct, restricted
non-production logins after applying both product migrations. The negative
role-assignment probe is inside a rolled-back savepoint. Main requires an
explicit non-production confirmation and refuses unmarked production-like DBs.
"""
from __future__ import annotations

import os
import sys
from uuid import uuid4

from sqlalchemy.exc import DBAPIError
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

OWNED = {
    "learn": {"institution", "learner", "curriculum", "content", "progress",
              "assessment", "gamification", "certification", "ai_tutor"},
    "hire": {"candidate", "drive", "questionbank", "exam", "submission",
             "anticheat", "evaluation", "interview", "result", "evidence",
             "competency", "decision", "action", "recruit_ai"},
}

# Shared capabilities are deployed as a separate process in each product but
# must not share writable database tables. Their physical schema is product
# prefixed so grants provide a second isolation boundary without relying on
# application-provided row filters.
for _product in ("learn", "hire"):
    OWNED[_product].update({f"{_product}_{name}" for name in (
        "coding", "notification", "files", "analytics", "audit",
        "ai_orchestration", "organization",
    )})


def check(product: str, url: str, *, foreign_user_id: str | None = None,
          foreign_role_id: str | None = None) -> list[str]:
    errors: list[str] = []
    engine = create_engine(url, pool_size=1, max_overflow=0, connect_args={"connect_timeout": 8})
    try:
        with engine.connect() as conn:
            role = conn.execute(text("""
                SELECT current_user, r.rolsuper, r.rolbypassrls,
                  EXISTS (
                    SELECT 1 FROM pg_class c
                    JOIN pg_namespace n ON n.oid = c.relnamespace
                    WHERE n.nspname = 'lare_auth' AND c.relkind IN ('r', 'p')
                      AND pg_has_role(current_user, c.relowner, 'member')
                  ) AS owns_auth_tables,
                  pg_has_role(current_user, 'lityra_learn_runtime', 'member') AS is_learn,
                  pg_has_role(current_user, 'lityra_hire_runtime', 'member') AS is_hire,
                  pg_has_role(current_user, 'lityra_combined_fallback', 'member') AS is_fallback
                FROM pg_roles r WHERE r.rolname = current_user
            """)).mappings().one()
            if role["rolsuper"] or role["rolbypassrls"]:
                errors.append(f"{product}: runtime login is superuser or BYPASSRLS")
            if role["owns_auth_tables"]:
                errors.append(f"{product}: runtime login inherits ownership of auth tables and can bypass RLS")
            if role["is_learn"] != (product == "learn") or role["is_hire"] != (product == "hire"):
                errors.append(f"{product}: runtime login must inherit exactly its own group role")
            if role["is_fallback"]:
                errors.append(f"{product}: product runtime login must not inherit the combined fallback role")

            opposite = "hire" if product == "learn" else "learn"
            for schema in OWNED[product]:
                allowed = conn.execute(text("SELECT has_schema_privilege(current_user,:s,'USAGE')"), {"s": schema}).scalar()
                if not allowed:
                    errors.append(f"{product}: missing USAGE for owned schema {schema}")
                can_create = conn.execute(text("SELECT has_schema_privilege(current_user,:s,'CREATE')"), {"s": schema}).scalar()
                if can_create:
                    errors.append(f"{product}: runtime login can CREATE in {schema}")
                can_read_probe = conn.execute(text(
                    "SELECT has_table_privilege(current_user,:t,'SELECT')"),
                    {"t": f"{schema}.product_isolation_probe"}).scalar()
                if not can_read_probe:
                    errors.append(f"{product}: cannot read own-schema permission probe {schema}")
            for schema in OWNED[opposite]:
                allowed = conn.execute(text("SELECT has_schema_privilege(current_user,:s,'USAGE')"), {"s": schema}).scalar()
                if allowed:
                    errors.append(f"{product}: unauthorized USAGE on {opposite} schema {schema}")
                cross_table = conn.execute(text(
                    "SELECT has_table_privilege(current_user,:t,'SELECT')"),
                    {"t": f"{schema}.product_isolation_probe"}).scalar()
                if cross_table:
                    errors.append(f"{product}: unauthorized SELECT on {opposite} table {schema}.product_isolation_probe")

            visible_cross_accounts = conn.execute(text(
                "SELECT count(*) FROM lare_auth.users WHERE product <> :p"), {"p": product}
            ).scalar_one()
            if visible_cross_accounts:
                errors.append(f"{product}: RLS exposes {visible_cross_accounts} other-product auth rows")
            visible_own_accounts = conn.execute(text(
                "SELECT count(*) FROM lare_auth.users WHERE product = :p"), {"p": product}
            ).scalar_one()
            if visible_own_accounts < 1:
                errors.append(f"{product}: RLS hides all own-product auth rows")
            print(f"{product}: own auth rows visible={visible_own_accounts}; cross-product rows visible={visible_cross_accounts}")
            visible_cross_roles = conn.execute(text(
                "SELECT count(*) FROM lare_auth.roles WHERE product <> :p"), {"p": product}
            ).scalar_one()
            if visible_cross_roles:
                errors.append(f"{product}: RLS exposes {visible_cross_roles} other-product roles")
            visible_own_roles = conn.execute(text(
                "SELECT count(*) FROM lare_auth.roles WHERE product = :p"), {"p": product}
            ).scalar_one()
            if visible_own_roles < 1:
                errors.append(f"{product}: RLS hides all own-product roles")
            if foreign_user_id:
                visible_foreign_assignments = conn.execute(text(
                    "SELECT count(*) FROM lare_auth.user_roles WHERE user_id=:u"),
                    {"u": foreign_user_id}).scalar_one()
                if visible_foreign_assignments:
                    errors.append(f"{product}: RLS exposes role assignments belonging to the other product")
            if foreign_role_id and visible_own_accounts:
                tx = conn.begin_nested()
                denied = False
                try:
                    conn.execute(text("""
                        INSERT INTO lare_auth.user_roles (id, user_id, role_id, college_id)
                        SELECT :id, id, :role, NULL FROM lare_auth.users
                        WHERE product=:p LIMIT 1
                    """), {"id": str(uuid4()), "role": foreign_role_id, "p": product})
                except DBAPIError:
                    denied = True
                finally:
                    tx.rollback()
                if not denied:
                    errors.append(f"{product}: database allowed an assignment to the other product's role")
    finally:
        engine.dispose()
    return errors


def main() -> int:
    if os.getenv("PRODUCT_DB_ISOLATION_CONFIRM_NON_PRODUCTION") != "I_HAVE_VERIFIED_NON_PRODUCTION":
        print("Set PRODUCT_DB_ISOLATION_CONFIRM_NON_PRODUCTION=I_HAVE_VERIFIED_NON_PRODUCTION only after verifying the targets are non-production.", file=sys.stderr)
        return 2
    urls = {p: os.getenv(f"{p.upper()}_TEST_DATABASE_URL", "") for p in OWNED}
    if not all(urls.values()):
        print("Set LEARN_TEST_DATABASE_URL and HIRE_TEST_DATABASE_URL to non-production restricted logins.", file=sys.stderr)
        return 2
    errors = []
    for product, url in urls.items():
        if not url.startswith(("postgresql://", "postgresql+psycopg://", "postgres://")):
            print(f"{product}: expected PostgreSQL URL", file=sys.stderr)
            return 2
        parsed = make_url(url)
        is_local = parsed.host in ("localhost", "127.0.0.1")
        looks_nonprod = any(marker in (parsed.database or "").lower()
                            for marker in ("test", "stage", "staging"))
        if not is_local and not looks_nonprod:
            print(f"{product}: database name does not identify a test/staging target; refusing to connect.", file=sys.stderr)
            return 2
        errors.extend(check(product, url))
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1
    print("Product database permission checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
