"""Flask application factory shared by all services.

Adds: request-id propagation, CORS, JSON error handlers, health/ready routes,
and structured request logging hooks.
"""
from __future__ import annotations

import logging
import time
import uuid
from typing import Callable, Iterable

from flask import Flask, Blueprint, g, jsonify, request
from flask_cors import CORS

from .config import BaseConfig
from .errors import register_error_handlers


class _Metrics:
    """Process-local counters exposed at /metrics in Prometheus text format.
    Good enough for a scrape per service; a real deployment federates these."""

    def __init__(self):
        self.requests = 0
        self.errors = 0
        self.latency_sum_ms = 0.0
        self.by_status: dict[int, int] = {}

    def observe(self, status: int, ms: float):
        self.requests += 1
        self.latency_sum_ms += ms
        self.by_status[status] = self.by_status.get(status, 0) + 1
        if status >= 500:
            self.errors += 1

    def render(self, service: str) -> str:
        lines = [
            "# TYPE lare_requests_total counter",
            f'lare_requests_total{{service="{service}"}} {self.requests}',
            "# TYPE lare_errors_total counter",
            f'lare_errors_total{{service="{service}"}} {self.errors}',
            "# TYPE lare_request_latency_ms_sum gauge",
            f'lare_request_latency_ms_sum{{service="{service}"}} {self.latency_sum_ms:.1f}',
        ]
        for status, count in sorted(self.by_status.items()):
            lines.append(f'lare_responses_total{{service="{service}",status="{status}"}} {count}')
        return "\n".join(lines) + "\n"


def create_app(
    config: BaseConfig,
    blueprints: Iterable[tuple[Blueprint, str]] = (),
    *,
    ready_check: Callable[[], bool] | None = None,
) -> Flask:
    app = Flask(config.SERVICE_NAME)
    app.config["LARE"] = config

    logging.basicConfig(
        level=logging.DEBUG if config.DEBUG else logging.INFO,
        format='{"ts":"%(asctime)s","svc":"' + config.SERVICE_NAME +
               '","level":"%(levelname)s","msg":"%(message)s"}',
    )

    CORS(app, origins=config.CORS_ORIGINS, supports_credentials=True)
    register_error_handlers(app)

    metrics = _Metrics()
    app.extensions["metrics"] = metrics

    @app.before_request
    def _assign_request_id():
        g._t0 = time.perf_counter()
        g.request_id = request.headers.get("X-Request-Id") or str(uuid.uuid4())
        # W3C trace-context: propagate an inbound traceparent, else start one.
        g.traceparent = request.headers.get("traceparent") or (
            f"00-{uuid.uuid4().hex}{uuid.uuid4().hex[:16]}-{uuid.uuid4().hex[:16]}-01"
        )

    @app.after_request
    def _propagate_request_id(resp):
        resp.headers["X-Request-Id"] = getattr(g, "request_id", "")
        resp.headers["X-Service"] = config.SERVICE_NAME
        if getattr(g, "traceparent", None):
            resp.headers["traceparent"] = g.traceparent
        t0 = getattr(g, "_t0", None)
        if t0 is not None and request.path not in ("/metrics", "/health"):
            metrics.observe(resp.status_code, (time.perf_counter() - t0) * 1000)
        return resp

    @app.get("/health")
    def _health():
        return jsonify({"service": config.SERVICE_NAME, "status": "ok"})

    @app.get("/ready")
    def _ready():
        healthy = ready_check() if ready_check else True
        return jsonify({"service": config.SERVICE_NAME,
                        "status": "ready" if healthy else "unready"}), (200 if healthy else 503)

    @app.get("/metrics")
    def _metrics():
        return app.response_class(metrics.render(config.SERVICE_NAME),
                                  mimetype="text/plain; version=0.0.4")

    for bp, prefix in blueprints:
        app.register_blueprint(bp, url_prefix=prefix)

    return app
