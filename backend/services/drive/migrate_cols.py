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
]


def main():
    cfg = DriveConfig()
    db = Database(cfg.DATABASE_URL, echo=False, schema=cfg.DB_SCHEMA)
    db.create_all()
    schema = cfg.DB_SCHEMA or None
    insp = inspect(db.engine)
    added = 0
    with db.engine.begin() as conn:
        for table, col, ddl in COLUMNS:
            try:
                cols = {c["name"] for c in insp.get_columns(table, schema=schema)}
            except Exception:
                print("  skip {} (table missing)".format(table))
                continue
            if col in cols:
                continue
            qualified = "{}.{}".format(schema, table) if schema else table
            conn.execute(text("ALTER TABLE {} ADD COLUMN {} {}".format(qualified, col, ddl)))
            print("  + {}.{}".format(table, col))
            added += 1
    print("Drive column migration done ({} added).".format(added))


if __name__ == "__main__":
    main()
