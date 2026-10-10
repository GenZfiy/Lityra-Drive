"""Longest-prefix router: map an incoming path to an upstream base URL."""
from __future__ import annotations

from .config import GatewayConfig


class Router:
    def __init__(self, cfg: GatewayConfig):
        self.cfg = cfg
        # Pre-sort prefixes longest-first for greedy matching.
        self._prefixes = sorted(cfg.ROUTES.keys(), key=len, reverse=True)

    def resolve(self, path: str) -> str | None:
        """Return the upstream base URL for a path, or None if unknown."""
        for prefix in self._prefixes:
            if path == prefix or path.startswith(prefix):
                key = self.cfg.ROUTES[prefix]
                return self.cfg.UPSTREAMS.get(key)
        return None

    def is_public(self, path: str) -> bool:
        return (path in self.cfg.PUBLIC_PATHS
                or any(path.startswith(p) for p in self.cfg.PUBLIC_PREFIXES))
