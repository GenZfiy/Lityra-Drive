import os

from lare_common.config import BaseConfig


class GatewayConfig(BaseConfig):
    SERVICE_NAME = os.getenv("SERVICE_NAME", "lare-gateway")
    APP_PRODUCT = os.getenv("APP_PRODUCT", "combined").lower()

    # Upstream service base URLs (dev defaults; override per env).
    UPSTREAMS = {
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
        "drive-evaluation": os.getenv("EVALUATION_URL", "http://127.0.0.1:8017"),
        "drive-interview": os.getenv("INTERVIEW_URL", "http://127.0.0.1:8018"),
        "drive-result": os.getenv("RESULT_URL", "http://127.0.0.1:8019"),
        # Shared platform code-execution engine (like files/AI). Used independently
        # by LMS practice and Hire coding rounds — it calls neither product.
        "platform-coding": os.getenv("CODING_URL", "http://127.0.0.1:8016"),
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

    # Longest-prefix routing table: request path prefix -> upstream key.
    # Order does not matter; the router picks the longest matching prefix.
    ROUTES = {
        "/auth/": "auth",
        "/lms/v1/colleges": "lms-institution",
        "/lms/v1/training-centers": "lms-institution",
        "/lms/v1/training-batches": "lms-institution",
        "/lms/v1/access": "lms-institution",
        "/lms/v1/branches": "lms-institution",
        "/lms/v1/cohorts": "lms-institution",
        "/lms/v1/schedule": "lms-institution",
        "/lms/v1/learners": "lms-learner",
        "/lms/v1/roster": "lms-learner",       # hierarchical roster analytics
        "/lms/v1/placement": "lms-learner",    # placement readiness analytics
        "/lms/v1/students": "lms-learner",     # student dashboard + roadmap + resources
        "/lms/v1/curricula": "lms-curriculum",
        "/lms/v1/years": "lms-curriculum",
        "/lms/v1/modules": "lms-curriculum",
        "/lms/v1/lessons": "lms-curriculum",
        "/lms/v1/objectives": "lms-curriculum",
        "/lms/v1/content": "lms-content",
        "/lms/v1/progress": "lms-progress",
        "/lms/v1/attendance": "lms-progress",
        "/lms/v1/scorecard": "lms-progress",
        "/lms/v1/assessments": "lms-assessment",
        "/lms/v1/attempts": "lms-assessment",
        "/lms/v1/answers": "lms-assessment",
        "/lms/v1/practice": "platform-coding",  # shared code-runner, not a Hire service
        "/lms/v1/careers": "lms-assessment",
        "/lms/v1/reviews": "lms-assessment",
        "/lms/v1/wallet": "lms-assessment",
        "/lms/v1/drill": "lms-assessment",
        "/lms/v1/mesh": "lms-assessment",
        "/lms/v1/micro-lessons": "lms-assessment",
        "/lms/v1/worlds": "lms-assessment",
        "/verify/wallet": "lms-assessment",
        "/lms/v1/gamification": "lms-gamification",
        "/lms/v1/cert-templates": "lms-certification",
        "/lms/v1/certificates": "lms-certification",
        "/verify/": "lms-certification",
        # --- Drive domain ---
        "/drive/v1/candidate": "drive-candidate",
        "/drive/v1/candidates": "drive-candidate",
        "/drive/v1/attend": "drive-candidate",
        "/drive/v1/drives": "drive-core",
        "/drive/v1/opportunities": "drive-core",
        "/drive/v1/access": "drive-core",
        "/drive/v1/evidence": "drive-evidence",
        "/drive/v1/competency": "drive-competency",
        "/drive/v1/decisions": "drive-decision",
        "/drive/v1/actions": "drive-action",
        "/drive/v1/insights": "drive-recruit-ai",
        "/drive/v1/calibration": "drive-recruit-ai",
        "/drive/v1/questions": "drive-questionbank",
        "/drive/v1/blueprints": "drive-questionbank",
        "/drive/v1/exams": "drive-exam",
        "/drive/v1/exam-sessions": "drive-exam",
        "/drive/v1/submissions": "drive-submission",
        "/drive/v1/proctor": "drive-anticheat",
        "/drive/v1/coding": "platform-coding",  # shared code-runner (platform infra)
        "/drive/v1/evaluations": "drive-evaluation",
        "/drive/v1/interviews": "drive-interview",
        "/drive/v1/results": "drive-result",
        "/drive/v1/offers": "drive-result",
        "/verify/offer/": "drive-result",
        # --- Shared ---
        "/notify/": "lare-notify",
        "/files/": "lare-files",
        "/analytics/": "lare-analytics",
        "/audit/": "lare-audit",
        # --- AI (longest-prefix: tutor beats the generic /ai/ orchestration) ---
        "/ai/v1/tutor": "lms-tutor",
        "/ai/": "platform-ai",
        # --- Organization layer ---
        "/org/": "platform-org",
    }

    # Independent deployments publish only their own API families. Shared
    # capabilities remain available through this product's own service copies.
    if APP_PRODUCT == "learn":
        for _path in list(ROUTES):
            if _path.startswith("/drive/") or _path == "/verify/offer/":
                del ROUTES[_path]
    elif APP_PRODUCT == "hire":
        for _path in list(ROUTES):
            if (_path.startswith("/lms/") or _path in ("/verify/wallet", "/ai/v1/tutor")):
                del ROUTES[_path]

    # Readiness must wait only for processes this product's router can reach.
    _used_upstreams = set(ROUTES.values())
    for _key in list(UPSTREAMS):
        if _key not in _used_upstreams:
            del UPSTREAMS[_key]

    # Paths that bypass auth (public). Matched by prefix.
    PUBLIC_PATHS = [
        "/auth/v1/register", "/auth/v1/login", "/auth/v1/refresh",
        "/auth/v1/otp/request", "/auth/v1/otp/verify",
        "/auth/v1/password/forgot", "/auth/v1/password/reset",
        "/auth/v1/email/confirm", "/auth/v1/.well-known/jwks.json",
        "/drive/v1/attend",     # starts an email-verified registration
        "/drive/v1/attend/resume",  # requests an OTP; does not return tokens
        "/drive/v1/attend/complete", # handler requires a Hire access token
        "/org/v1/resolve",      # white-label branding by domain (pre-login)
    ]
    PUBLIC_PREFIXES = [
        "/verify/",  # public certificate / offer verification (both prefixes)
        "/files/v1/upload/",    # pre-signed upload (token-authenticated)
        "/files/v1/download/",  # pre-signed download (token-authenticated)
    ]

    # Rate limiting (in-memory dev; Redis in prod).
    RATE_LIMIT_PER_MIN = int(os.getenv("RATE_LIMIT_PER_MIN", "240"))
    EXAM_RATE_LIMIT_PER_MIN = int(os.getenv("EXAM_RATE_LIMIT_PER_MIN", "1200"))

    PROXY_TIMEOUT = int(os.getenv("PROXY_TIMEOUT", "30"))
    # Some endpoints are legitimately slow (AI generation calls an LLM). Give
    # those a longer ceiling by path prefix instead of raising the global one,
    # which would let any slow upstream hold a connection open.
    SLOW_TIMEOUT = int(os.getenv("SLOW_TIMEOUT", "120"))
    SLOW_ROUTES = (
        "/drive/v1/results/compile",     # ranks + upserts every candidate's result
        "/drive/v1/evidence/backfill",   # emits evidence for every candidate
        "/drive/v1/questions/generate",  # LLM question generation
        "/ai/v1/complete",               # LLM completion
        "/drive/v1/coding/run-adhoc",    # multi-case code execution
        "/lms/v1/assessments/coach",     # LLM study-plan generation
        "/lms/v1/practice",              # code execution (run/submit) + AI viva
        "/lms/v1/micro-lessons",         # LLM micro-lesson generation
    )
