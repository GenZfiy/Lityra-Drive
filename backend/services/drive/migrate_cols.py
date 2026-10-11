r"""Add columns init-db can't add to existing drive tables (idempotent,
dialect-aware). Run with the same env run-all uses (schema 'drive' locally):

    cd backend/services/drive
    $env:DB_SCHEMA = "drive"; $env:PYTHONPATH = "."
    ..\..\.venv\Scripts\python.exe migrate_cols.py
"""
from __future__ import annotations

from dotenv import load_dotenv

load_dotenv()

import app.models  # noqa: E402,F401
from app.config import DriveConfig  # noqa: E402
from lare_common.db import Database  # noqa: E402
from sqlalchemy import inspect, text  # noqa: E402

COLUMNS = [
    ("drive_roles", "skills", "JSON DEFAULT '[]'"),
    ("drives", "tenant_id", "VARCHAR(64) NOT NULL DEFAULT 'lare'"),
    ("drives", "drive_type", "VARCHAR(32) NOT NULL DEFAULT 'company_off_campus'"),
    ("drives", "organizer_type", "VARCHAR(16) NOT NULL DEFAULT 'company'"),
    ("drives", "organizer_id", "VARCHAR(64) NOT NULL DEFAULT 'lare'"),
    ("drives", "host_college_id", "VARCHAR(64)"),
    ("drives", "adoption_status", "VARCHAR(16)"),
    ("drives", "workflow_config", "JSON DEFAULT '{}'"),
    ("drives", "event_group_id", "VARCHAR(64)"),
    ("drives", "parent_drive_id", "VARCHAR(64)"),
    ("drives", "pipeline_company_id", "VARCHAR(64)"),
    ("drive_company_participation", "pipeline_drive_id", "VARCHAR(64)"),
]


def migrate_existing_columns(db: Database) -> int:
    schema = db.schema or None
    added = 0
    existing_tables: set[str] = set()
    checked_tables: set[str] = set()
    # Check table presence before opening the migration transaction. This avoids
    # reserving the only configured pooled connection while reflection runs.
    insp = inspect(db.engine)
    for table, _col, _ddl in COLUMNS:
        if table in checked_tables:
            continue
        checked_tables.add(table)
        print("  checking {}.{}".format(schema or "public", table), flush=True)
        # Do not turn connection, permission, or schema errors into a misleading
        # "table missing" message. `has_table` returns False only when absent.
        if not insp.has_table(table, schema=schema):
            raise RuntimeError(
                "Expected Drive table {}.{} is missing after create_all; "
                "check DB_SCHEMA and database permissions.".format(schema or "public", table)
            )
        existing_tables.add(table)

    with db.engine.begin() as conn:
        # Avoid spending the release command's entire timeout waiting on a live
        # request or another DDL operation holding a table lock.
        conn.execute(text("SET LOCAL lock_timeout = '10s'"))
        conn.execute(text("SET LOCAL statement_timeout = '120s'"))
        # Bind reflection to this transaction's connection. Inspecting the Engine
        # here would check out a second connection and deadlock when DB_POOL_SIZE=1.
        conn_insp = inspect(conn)
        for table, col, ddl in COLUMNS:
            if table not in existing_tables:
                continue
            cols = {c["name"] for c in conn_insp.get_columns(table, schema=schema)}
            if col in cols:
                continue
            qualified = "{}.{}".format(schema, table) if schema else table
            print("  adding {}.{}".format(table, col), flush=True)
            conn.execute(text("ALTER TABLE {} ADD COLUMN {} {}".format(qualified, col, ddl)))
            print("  added {}.{}".format(table, col), flush=True)
            added += 1
        # Older Hire drives used company_id as the owning company key. New
        # ownership columns receive compatibility defaults when added; backfill
        # those defaults so existing recruiters keep access after the migration.
        drives = "{}.drives".format(schema) if schema else "drives"
        if "drives" in existing_tables:
            for label, statement in (
                ("drive ownership", "UPDATE {} SET tenant_id = company_id WHERE tenant_id = 'lare' AND company_id IS NOT NULL AND company_id <> 'pending'".format(drives)),
                ("drive organizer", "UPDATE {} SET organizer_id = tenant_id WHERE organizer_type = 'company' AND organizer_id = 'lare'".format(drives)),
                ("event group", "UPDATE {} SET event_group_id = id WHERE event_group_id IS NULL".format(drives)),
            ):
                print("  backfilling {}".format(label), flush=True)
                conn.execute(text(statement))
        for table, column, index_name in (
            ("drives", "event_group_id", "ix_drives_event_group_id"),
            ("drives", "parent_drive_id", "ix_drives_parent_drive_id"),
            ("drives", "pipeline_company_id", "ix_drives_pipeline_company_id"),
            ("drive_company_participation", "pipeline_drive_id", "ix_drive_company_pipeline_drive_id"),
        ):
            if table not in existing_tables:
                continue
            qualified = '"{}"."{}"'.format(schema, table) if schema else '"{}"'.format(table)
            print("  ensuring index {}".format(index_name), flush=True)
            conn.execute(text('CREATE INDEX IF NOT EXISTS "{}" ON {} ("{}")'.format(
                index_name, qualified, column)))
    return added


def main():
    cfg = DriveConfig()
    db = Database(cfg.DATABASE_URL, echo=False, schema=cfg.DB_SCHEMA)
    added = migrate_existing_columns(db)
    print("Drive column migration done ({} added).".format(added))


if __name__ == "__main__":
    main()
