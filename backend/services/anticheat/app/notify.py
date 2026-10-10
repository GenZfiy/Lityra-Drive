"""Deliver the auto-submit signal to the Exam Engine (east-west).

Uses stdlib urllib (no extra dependency), best-effort with a short timeout. In
production this would publish to the Redis Streams event bus and the Exam Engine
would consume it; the direct call is the synchronous equivalent for v1. Internal
call on the private network sets trusted service headers (the Gateway strips
these on inbound public traffic, so they cannot be spoofed from outside)."""
from __future__ import annotations

import json
import logging
import urllib.request

log = logging.getLogger("lare-anticheat")


def make_exam_autosubmit_trigger(exam_engine_url: str):
    def trigger(exam_session_id: str) -> None:
        url = f"{exam_engine_url.rstrip('/')}/drive/v1/exam-sessions/{exam_session_id}/force-submit"
        payload = json.dumps({"reason": "anticheat"}).encode("utf-8")
        req = urllib.request.Request(
            url, data=payload, method="POST",
            headers={
                "Content-Type": "application/json",
                "X-User-Id": "svc-anticheat",
                "X-Roles": "company_admin",  # internal service context
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=3) as resp:  # noqa: S310
                resp.read()
            log.info("auto-submit delivered to exam engine: %s", exam_session_id)
        except Exception as exc:  # noqa: BLE001 — best-effort
            log.warning("auto-submit delivery failed for %s: %s", exam_session_id, exc)

    return trigger
