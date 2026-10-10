"""Database engine / session helpers built on SQLAlchemy 2.x.

Each service constructs one Database instance from its config and shares the
declarative Base for its models.
"""
from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


class Base(DeclarativeBase):
    """Root declarative base. Services define models against this."""


class Database:
    """Per-service database handle.

    On PostgreSQL, each service isolates its tables in its own schema
    (``schema``) via ``search_path``, giving the schema-per-domain layout the
    SRS mandates without hard-coding the schema into every table definition.
    On SQLite (local dev) the schema is ignored.
    """

    def __init__(self, url: str, *, echo: bool = False, schema: str | None = None):
        import os

        self.is_sqlite = url.startswith("sqlite")
        self.schema = None if self.is_sqlite else schema

        connect_args = {}
        engine_kw: dict = {"echo": echo, "future": True, "pool_pre_ping": True}
        if self.is_sqlite:
            connect_args["check_same_thread"] = False
        else:
            # Pool sizing depends on the DB endpoint:
            #  * Session pooler (Supabase port 5432) / direct: holds one server
            #    connection per client, so with ~31 services the pool MUST be
            #    small or Postgres runs out of slots. Default is tuned for this.
            #  * Transaction pooler (Supabase port 6543): multiplexes — you can
            #    safely raise DB_POOL_SIZE to match the web thread count.
            engine_kw["pool_size"] = int(os.getenv("DB_POOL_SIZE", "2"))
            # With many independently-running services, overflow multiplies
            # the possible Postgres sessions across the whole deployment.
            # Keep each service at its configured base pool unless explicitly
            # raised for a larger database plan.
            engine_kw["max_overflow"] = int(os.getenv("DB_MAX_OVERFLOW", "0"))
            engine_kw["pool_recycle"] = int(os.getenv("DB_POOL_RECYCLE", "1800"))
            engine_kw["pool_timeout"] = int(os.getenv("DB_POOL_TIMEOUT", "30"))
            # Test a pooled connection before use and transparently reconnect if
            # it's dead — so a dropped SSH tunnel / pooler reset reconnects on the
            # next request instead of surfacing as a 500.
            engine_kw["pool_pre_ping"] = True
            if self.schema:
                # Pin search_path as a libpq STARTUP option. This is preserved
                # per-connection by the Supabase/pgbouncer session pooler, unlike
                # a mid-session `SET` which a pooler reset would wipe.
                connect_args["options"] = f"-c search_path={self.schema},public"

        self.engine = create_engine(url, connect_args=connect_args, **engine_kw)

        if self.schema:
            # Belt-and-suspenders: also set it on every pool checkout so a reset
            # connection is always re-scoped before use.
            @event.listens_for(self.engine, "checkout")
            def _set_search_path(dbapi_conn, _record, _proxy):  # noqa: ANN001
                cur = dbapi_conn.cursor()
                cur.execute(f'SET search_path TO "{self.schema}", public')
                cur.close()

        self.SessionLocal = sessionmaker(
            bind=self.engine, autoflush=False, autocommit=False, future=True
        )

    def ensure_schema(self) -> None:
        if self.schema:
            with self.engine.connect() as conn:
                conn.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{self.schema}"'))
                conn.commit()

    def create_all(self) -> None:
        self.ensure_schema()
        Base.metadata.create_all(self.engine)

    def drop_all(self) -> None:
        Base.metadata.drop_all(self.engine)

    @contextmanager
    def session(self) -> Iterator[Session]:
        s = self.SessionLocal()
        try:
            yield s
            s.commit()
        except Exception:
            s.rollback()
            raise
        finally:
            s.close()
