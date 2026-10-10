"""East-west (service-to-service) plumbing shared by every service.

Two responsibilities:
  1. ``SERVICE_URLS`` — the single source of truth for internal base URLs,
     mirroring the Gateway's UPSTREAMS. Overridable per-env via ``<NAME>_URL``.
  2. Internal service tokens — a short-lived HS256 JWT signed with
     ``INTERNAL_JWT_SECRET`` so a receiving service can trust an east-west
     caller even though the Gateway (which normally injects identity) is not in
     the private path. The Gateway strips ``X-Internal-Token`` on public ingress,
     so it cannot be spoofed from outside.
"""
from __future__ import annotations

import os
import time

import jwt

# --- canonical internal service registry (name -> base url) -------------------
# Keys match the Gateway UPSTREAMS keys so both maps stay in lock-step.
SERVICE_URLS: dict[str, str] = {
    "auth": os.getenv("AUTH_URL", "http://127.0.0.1:8001"),
    "lms-institution": os.getenv("INSTITUTION_URL", "http://127.0.0.1:8002"),
    "lms-learner": os.getenv("LEARNER_URL", "http://127.0.0.1:8003"),
    "lms-curriculum": os.getenv("CURRICULUM_URL", "http://127.0.0.1:8004"),
    "lms-content": os.getenv("CONTENT_URL", "http://127.0.0.1:8005"),
    "lms-progress": os.getenv("PROGRESS_URL", "http://127.0.0.1:8006"),
    "lms-assessment": os.getenv("ASSESSMENT_URL", "http://127.0.0.1:8007"),
    "lms-gamification": os.getenv("GAMIFICATION_URL", "http://127.0.0.1:8008"),
    "lms-certification": os.getenv("CERTIFICATION_URL", "http://127.0.0.1:8009"),
    "drive-candidate": os.getenv("CANDIDATE_URL", "http://127.0.0.1:8010"),
    "drive-core": os.getenv("DRIVE_URL", "http://127.0.0.1:8011"),
    "drive-questionbank": os.getenv("QUESTIONBANK_URL", "http://127.0.0.1:8012"),
    "drive-exam": os.getenv("EXAM_URL", "http://127.0.0.1:8013"),
    "drive-submission": os.getenv("SUBMISSION_URL", "http://127.0.0.1:8014"),
    "drive-anticheat": os.getenv("ANTICHEAT_URL", "http://127.0.0.1:8015"),
    # Shared platform code-execution engine (both products use it independently).
    "platform-coding": os.getenv("CODING_URL", "http://127.0.0.1:8016"),
    "drive-evaluation": os.getenv("EVALUATION_URL", "http://127.0.0.1:8017"),
    "drive-interview": os.getenv("INTERVIEW_URL", "http://127.0.0.1:8018"),
    "drive-result": os.getenv("RESULT_URL", "http://127.0.0.1:8019"),
    "lare-notify": os.getenv("NOTIFY_URL", "http://127.0.0.1:8020"),
    "lare-files": os.getenv("FILES_URL", "http://127.0.0.1:8021"),
    "lare-analytics": os.getenv("ANALYTICS_URL", "http://127.0.0.1:8022"),
    "lare-audit": os.getenv("AUDIT_URL", "http://127.0.0.1:8023"),
    "platform-ai": os.getenv("AI_ORCH_URL", "http://127.0.0.1:8024"),  # governed AI egress (both products)
    "lms-tutor": os.getenv("AI_TUTOR_URL", "http://127.0.0.1:8025"),
    "platform-org": os.getenv("ORG_URL", "http://127.0.0.1:8026"),
    "drive-evidence": os.getenv("EVIDENCE_URL", "http://127.0.0.1:8027"),
    "drive-competency": os.getenv("COMPETENCY_URL", "http://127.0.0.1:8028"),
    "drive-decision": os.getenv("DECISION_URL", "http://127.0.0.1:8029"),
    "drive-action": os.getenv("ACTION_URL", "http://127.0.0.1:8030"),
    "drive-recruit-ai": os.getenv("RECRUIT_AI_URL", "http://127.0.0.1:8031"),
}


def service_url(name: str) -> str:
    try:
        return SERVICE_URLS[name].rstrip("/")
    except KeyError as exc:  # noqa: BLE001
        raise KeyError(f"unknown internal service '{name}'") from exc


# --- internal service tokens --------------------------------------------------

def _secret() -> str:
    return os.getenv("INTERNAL_JWT_SECRET", "dev-internal-secret-change-me")


def mint_service_token(service_name: str, *, roles: list[str] | None = None,
                       ttl_sec: int = 60) -> str:
    """Sign a short-lived token identifying the calling service."""
    now = int(time.time())
    payload = {
        "sub": f"svc-{service_name}",
        "type": "service",
        "svc": service_name,
        "roles": roles or [],
        "iat": now,
        "exp": now + ttl_sec,
    }
    return jwt.encode(payload, _secret(), algorithm="HS256")


def verify_service_token(token: str) -> dict:
    """Verify an internal token; raises on invalid/expired."""
    claims = jwt.decode(token, _secret(), algorithms=["HS256"])
    if claims.get("type") != "service":
        raise ValueError("not a service token")
    return claims
