"""API Gateway app: verify identity, strip spoofed headers, inject trusted
context, rate-limit, and reverse-proxy to the resolved upstream service."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed

import jwt
import requests
from flask import Flask, g, jsonify, request
from flask_cors import CORS

from lare_common.errors import register_error_handlers
from lare_common.responses import error_payload
from lare_common.security import decode_token

from .config import GatewayConfig
from .proxy import forward
from .ratelimit import RateLimiter
from .routing import Router


def product_claim_matches(claims: dict, expected_product: str | None) -> bool:
    """Legacy tokens without a product claim never satisfy a product boundary."""
    return expected_product is None or claims.get("product") == expected_product


def build_app() -> Flask:
    cfg = GatewayConfig()
    if cfg.ENV == "production" and "*" in cfg.CORS_ORIGINS:
        raise RuntimeError("CORS_ORIGINS must list explicit trusted origins in production")
    if cfg.APP_PRODUCT not in ("learn", "hire", "combined"):
        raise RuntimeError("APP_PRODUCT must be learn, hire, or combined")
    app = Flask(cfg.SERVICE_NAME)
    app.config["LARE"] = cfg
    CORS(app, origins=cfg.CORS_ORIGINS, supports_credentials=True)
    register_error_handlers(app)

    router = Router(cfg)
    limiter = RateLimiter()

    def _client_key() -> str:
        ident = getattr(g, "identity_claims", None)
        if ident:
            return f"user:{ident['sub']}"
        # X-Real-IP is overwritten by the trusted edge proxy. Do not trust an
        # arbitrary client-supplied X-Forwarded-For chain for rate-limit keys.
        return f"ip:{request.headers.get('X-Real-IP') or request.remote_addr}"

    @app.get("/health")
    def health():
        return jsonify({"service": cfg.SERVICE_NAME, "status": "ok"})

    @app.get("/ready")
    def ready():
        # Check upstreams concurrently so latency does not multiply by the
        # number of services behind the gateway.
        results = {}

        def check_upstream(key, base):
            try:
                r = requests.get(base.rstrip("/") + "/health", timeout=1.5)
                return key, r.ok
            except requests.RequestException:
                return key, False

        with ThreadPoolExecutor(max_workers=min(32, max(1, len(cfg.UPSTREAMS)))) as pool:
            checks = [pool.submit(check_upstream, key, base)
                      for key, base in cfg.UPSTREAMS.items()]
            for check in as_completed(checks):
                key, is_ready = check.result()
                results[key] = is_ready
        ready = all(results.values())
        return jsonify({"service": cfg.SERVICE_NAME,
                        "status": "ready" if ready else "unready",
                        "upstreams": results}), (200 if ready else 503)

    @app.route("/<path:path>", methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"])
    def gateway(path: str):
        full = "/" + path

        # Resolve upstream first (unknown route -> 404 without leaking topology).
        upstream = router.resolve(full)
        if upstream is None:
            return jsonify(error_payload("route_not_found", "Unknown route")), 404

        # Rate limit (exam paths get a higher ceiling).
        limit = cfg.EXAM_RATE_LIMIT_PER_MIN if "/exam" in full else cfg.RATE_LIMIT_PER_MIN

        injected: dict[str, str] = {}
        if not router.is_public(full):
            # Verify the access token (offline). Dev = HS256; prod = RS256/JWKS.
            auth = request.headers.get("Authorization", "")
            if not auth.startswith("Bearer "):
                return jsonify(error_payload("unauthorized", "Authentication required")), 401
            try:
                claims = decode_token(
                    auth[7:],
                    alg=cfg.JWT_ALG,
                    verify_key=cfg.verify_key,
                    issuer=cfg.JWT_ISSUER,
                    audience=cfg.JWT_AUDIENCE,
                )
            except Exception:  # noqa: BLE001
                return jsonify(error_payload("unauthorized", "Invalid or expired token")), 401
            if claims.get("type") != "access":
                return jsonify(error_payload("unauthorized", "Not an access token")), 401

            # Product isolation is enforced for every authenticated route,
            # including shared capabilities, on independent product deployments.
            token_product = claims.get("product")
            expected_product = (cfg.APP_PRODUCT if cfg.APP_PRODUCT in ("learn", "hire")
                                else ("learn" if full.startswith("/lms/")
                                      else "hire" if full.startswith("/drive/") else None))
            if not product_claim_matches(claims, expected_product):
                return jsonify(error_payload(
                    "wrong_product",
                    "A valid product-specific session is required")), 403

            g.identity_claims = claims
            injected = {
                "X-User-Id": claims["sub"],
                "X-Roles": ",".join(claims.get("roles", [])),
                "X-Permissions": ",".join(claims.get("permissions", [])),
                "X-Scope-Level": claims.get("scope_level", "self"),
                "X-Branch-Ids": ",".join(claims.get("branch_ids", [])),
                "X-Cohort-Ids": ",".join(claims.get("cohort_ids", [])),
                "X-Tenant-Id": claims.get("tenant_id", "lare"),
                "X-College-Ids": ",".join(claims.get("college_ids", [])),
                "X-Product": token_product or "",
            }

            # LMS Access Gate — a student must have validated their class Access
            # ID this session (a short-lived grant) to reach the learning
            # environment. Staff/admins are exempt; the access endpoints (where
            # the code is validated) are exempt so the gate can be passed.
            roles = claims.get("roles", [])
            if ("student" in roles and full.startswith("/lms/v1/")
                    and not full.startswith("/lms/v1/access")):
                grant = request.headers.get("X-Access-Grant", "")
                cohort_id = ""
                valid = False
                if grant:
                    try:
                        gclaims = jwt.decode(grant, cfg.INTERNAL_JWT_SECRET, algorithms=["HS256"])
                        if (gclaims.get("scope") == "lms_access"
                                and gclaims.get("sub") == claims.get("sub")):
                            valid = True
                            cohort_id = gclaims.get("cohort_id", "")
                    except Exception:  # noqa: BLE001 — invalid/expired grant
                        valid = False
                if not valid:
                    return jsonify(error_payload(
                        "access_gate_required",
                        "Enter your class Access ID to continue")), 403
                injected["X-Cohort-Id"] = cohort_id

            # Drive Access Gate — a candidate must present a valid Drive Access ID
            # this session to reach a recruitment drive. Recruiters/admins are
            # exempt; the access endpoints and public attend flow are exempt.
            if ("student" in roles and full.startswith("/drive/v1/")
                    and not full.startswith("/drive/v1/access")
                    and not full.startswith("/drive/v1/attend")):
                grant = request.headers.get("X-Access-Grant", "")
                drive_id = ""
                valid = False
                if grant:
                    try:
                        gclaims = jwt.decode(grant, cfg.INTERNAL_JWT_SECRET, algorithms=["HS256"])
                        if (gclaims.get("scope") == "drive_access"
                                and gclaims.get("sub") == claims.get("sub")):
                            valid = True
                            drive_id = gclaims.get("drive_id", "")
                    except Exception:  # noqa: BLE001
                        valid = False
                if not valid:
                    return jsonify(error_payload(
                        "access_gate_required",
                        "Enter your Drive Access ID to continue")), 403
                injected["X-Drive-Id"] = drive_id

        if not limiter.allow(_client_key(), limit):
            return jsonify(error_payload("rate_limited", "Too many requests")), 429

        # Always attach a request id for tracing.
        rid = request.headers.get("X-Request-Id") or g.get("request_id", "")
        if rid:
            injected["X-Request-Id"] = rid

        timeout = cfg.PROXY_TIMEOUT
        if any(full.startswith(p) for p in cfg.SLOW_ROUTES):
            timeout = cfg.SLOW_TIMEOUT
        try:
            return forward(upstream, full, injected=injected, timeout=timeout)
        except requests.Timeout:
            return jsonify(error_payload("upstream_timeout", "Upstream timed out")), 504
        except requests.ConnectionError:
            return jsonify(error_payload("upstream_unavailable", "Service unavailable")), 503

    @app.after_request
    def _hdrs(resp):
        resp.headers["X-Service"] = cfg.SERVICE_NAME
        return resp

    return app
