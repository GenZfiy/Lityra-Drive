"""Redis access with a graceful in-memory fallback.

Production sets ``REDIS_URL`` and installs the ``redis`` package; then caching,
rate-limiting counters, and the event-bus stream all use Redis. When either is
absent (local dev), callers transparently fall back to process-local structures
so nothing has to branch on "is Redis available".
"""
from __future__ import annotations

import threading
import time

_client = None
_checked = False


def get_redis(url: str | None):
    """Return a connected redis client, or None if unavailable.

    Cached after the first call. Never raises — a failed connection returns None
    and the caller uses its in-memory fallback.
    """
    global _client, _checked
    if _checked:
        return _client
    _checked = True
    if not url:
        return None
    try:
        import redis  # type: ignore

        c = redis.Redis.from_url(url, decode_responses=True)
        c.ping()
        _client = c
    except Exception:  # noqa: BLE001 — degrade silently to in-memory
        _client = None
    return _client


class InMemoryCounter:
    """Fixed-window counter used by rate limiting when Redis is absent.

    Not shared across processes (each gunicorn worker keeps its own) — good
    enough for dev; production uses the Redis-backed counter below.
    """

    def __init__(self):
        self._buckets: dict[str, tuple[int, float]] = {}
        self._lock = threading.Lock()

    def incr(self, key: str, window_sec: int) -> int:
        now = time.time()
        with self._lock:
            count, start = self._buckets.get(key, (0, now))
            if now - start >= window_sec:
                count, start = 0, now
            count += 1
            self._buckets[key] = (count, start)
            return count


class RateLimiter:
    """Fixed-window limiter backed by Redis if present, else in-memory."""

    def __init__(self, redis_url: str | None):
        self._redis = get_redis(redis_url)
        self._mem = InMemoryCounter()

    def hit(self, key: str, limit: int, window_sec: int = 60) -> tuple[bool, int]:
        """Return (allowed, current_count)."""
        if self._redis is not None:
            try:
                pipe = self._redis.pipeline()
                pipe.incr(key)
                pipe.expire(key, window_sec)
                count = int(pipe.execute()[0])
                return count <= limit, count
            except Exception:  # noqa: BLE001 — fall through to memory
                pass
        count = self._mem.incr(key, window_sec)
        return count <= limit, count
