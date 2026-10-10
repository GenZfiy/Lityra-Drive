"""Production-capable WSGI serving for `manage.py serve`.

Prefers a real WSGI server so a service can handle real concurrency:
  * Linux production → Gunicorn (via ``deploy/gunicorn.conf.py``), started by
    systemd/Procfile, not this helper.
  * Everywhere else (Windows dev, single-process prod) → **waitress**, a pure-
    Python multithreaded WSGI server. Falls back to Flask's threaded dev server
    only if waitress is missing.

Concurrency is thread-based (``WEB_THREADS``); keep the DB pool (``DB_POOL_SIZE``
+ ``DB_MAX_OVERFLOW``) at least as large as the thread count so requests don't
queue on connections.
"""
from __future__ import annotations

import logging
import os

log = logging.getLogger("lare-serve")


def serve(app, *, host: str = "127.0.0.1", port: int = 8000) -> None:
    threads = int(os.getenv("WEB_THREADS", "16"))
    try:
        from waitress import serve as waitress_serve
    except ImportError:
        log.warning("waitress not installed; using Flask dev server (dev only)")
        app.run(host=host, port=port, use_reloader=False, threaded=True)
        return
    log.info("serving on %s:%s via waitress (threads=%d)", host, port, threads)
    waitress_serve(app, host=host, port=port, threads=threads,
                   connection_limit=int(os.getenv("WEB_CONNECTION_LIMIT", "1000")),
                   channel_timeout=int(os.getenv("WEB_CHANNEL_TIMEOUT", "120")))
