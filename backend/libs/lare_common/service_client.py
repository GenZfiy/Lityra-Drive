"""Best-effort east-west HTTP client (stdlib only — no requests dependency).

Every internal call carries:
  - ``X-Internal-Token``  short-lived signed service token (trust anchor)
  - ``X-User-Id`` / ``X-Roles``  the acting identity, so the callee's normal
    ``current_identity()`` / ``require_roles`` guards work unchanged.

This generalises the original anti-cheat -> exam trigger into one reusable
client used by the event bus and all synchronous east-west calls.
"""
from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request

from .internal import mint_service_token, service_url

log = logging.getLogger("lare-svc-client")


class ServiceClient:
    def __init__(self, caller: str, *, default_roles: list[str] | None = None,
                 timeout: int = 5):
        self.caller = caller
        self.default_roles = default_roles or []
        self.timeout = timeout

    def _headers(self, roles: list[str] | None, user_id: str | None) -> dict:
        roles = roles if roles is not None else self.default_roles
        return {
            "Content-Type": "application/json",
            "X-Internal-Token": mint_service_token(self.caller, roles=roles),
            "X-User-Id": user_id or f"svc-{self.caller}",
            "X-Roles": ",".join(roles),
        }

    def _request(self, method: str, url: str, payload: dict | None,
                 roles: list[str] | None, user_id: str | None) -> dict | None:
        data = json.dumps(payload).encode("utf-8") if payload is not None else None
        req = urllib.request.Request(
            url, data=data, method=method, headers=self._headers(roles, user_id)
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:  # noqa: S310
                body = resp.read()
                return json.loads(body) if body else None
        except urllib.error.HTTPError as exc:  # noqa: PERF203
            log.warning("east-west %s %s -> HTTP %s", method, url, exc.code)
            raise
        except Exception as exc:  # noqa: BLE001 — best effort
            log.warning("east-west %s %s failed: %s", method, url, exc)
            raise

    # path-based helpers (resolve service name -> base url) --------------------
    def post(self, service: str, path: str, payload: dict, *,
             roles: list[str] | None = None, user_id: str | None = None) -> dict | None:
        url = f"{service_url(service)}{path}"
        return self._request("POST", url, payload, roles, user_id)

    def get(self, service: str, path: str, *,
            roles: list[str] | None = None, user_id: str | None = None) -> dict | None:
        url = f"{service_url(service)}{path}"
        return self._request("GET", url, None, roles, user_id)

    # absolute-url helper (used by the event bus fan-out) ---------------------
    def post_url(self, url: str, payload: dict, *,
                 roles: list[str] | None = None, user_id: str | None = None) -> dict | None:
        return self._request("POST", url, payload, roles, user_id)

    def try_post(self, service: str, path: str, payload: dict, **kw) -> bool:
        """Fire-and-forget: swallow failures, return delivered?"""
        try:
            self.post(service, path, payload, **kw)
            return True
        except Exception:  # noqa: BLE001
            return False
