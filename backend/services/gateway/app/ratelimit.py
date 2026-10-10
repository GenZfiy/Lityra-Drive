"""Gateway rate limiter.

Prefers a Redis fixed-window counter (shared across gateway workers/instances)
when ``REDIS_URL`` is set and reachable; otherwise falls back to a per-process
in-memory sliding window. Same ``allow(key, limit_per_min)`` interface either way.
"""
from __future__ import annotations

import os
import threading
import time
from collections import defaultdict, deque

from lare_common.redis_helper import get_redis


class RateLimiter:
    def __init__(self, redis_url: str | None = None):
        self._redis = get_redis(redis_url if redis_url is not None else os.getenv("REDIS_URL", ""))
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()
        self.backend = "redis" if self._redis is not None else "memory"

    def allow(self, key: str, limit_per_min: int) -> bool:
        if self._redis is not None:
            try:
                # Fixed 60s window bucketed by minute, shared across instances.
                bucket = f"rl:{key}:{int(time.time() // 60)}"
                pipe = self._redis.pipeline()
                pipe.incr(bucket)
                pipe.expire(bucket, 60)
                count = int(pipe.execute()[0])
                return count <= limit_per_min
            except Exception:  # noqa: BLE001 — fall back to memory on Redis hiccup
                pass
        now = time.time()
        window_start = now - 60
        with self._lock:
            q = self._hits[key]
            while q and q[0] < window_start:
                q.popleft()
            if len(q) >= limit_per_min:
                return False
            q.append(now)
            return True
