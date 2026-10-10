r"""Add columns init-db can't add to existing coding tables (idempotent,
dialect-aware). Run with the same env run-all uses (schema 'coding' locally):

    cd backend/services/coding
    $env:DB_SCHEMA = "coding"; $env:PYTHONPATH = "."
    ..\..\.venv\Scripts\python.exe migrate_cols.py
"""
from __future__ import annotations

from dotenv import load_dotenv

load_dotenv()

import app.models  # noqa: E402,F401
from app.config import CodingConfig  # noqa: E402
from lare_common.db import Database  # noqa: E402
from sqlalchemy import inspect, text  # noqa: E402

COLUMNS = [
    ("problems", "skill", "VARCHAR(64) DEFAULT 'General'"),
    ("problems", "difficulty", "VARCHAR(16) DEFAULT 'easy'"),
    ("problems", "practice", "BOOLEAN DEFAULT FALSE"),
    ("coding_sessions", "kind", "VARCHAR(16) DEFAULT 'exam'"),
]


def main():
    cfg = CodingConfig()
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
    print("Coding column migration done ({} added).".format(added))


if __name__ == "__main__":
    main()
