"""Domain event bus — one abstraction, two interchangeable backends.

Backends
--------
* **redis**  ``XADD`` to a single stream; each subscribing service runs a
  consumer-group reader (``start_consumer``) that dispatches to its handlers.
* **http**   synchronous best-effort fan-out: the publisher POSTs the event to
  each subscriber's ``/events/v1/ingest`` webhook (stdlib, no broker needed).
* **memory** in-process dispatch to locally registered handlers (tests).

``EVENT_BUS_BACKEND=auto`` (default) picks redis when ``REDIS_URL`` is reachable,
otherwise http. Handlers are written once and work under every backend.

The publish/subscribe topology lives in ``SUBSCRIBERS`` below so it is auditable
in one place. Analytics and Audit are wildcard sinks — they receive every event.
"""
from __future__ import annotations

import json
import logging
import threading
import time
import uuid
from dataclasses import asdict, dataclass, field

from flask import Blueprint, g, request

from .redis_helper import get_redis
from .responses import ok, error_payload
from .service_client import ServiceClient
from .internal import verify_service_token

log = logging.getLogger("lare-events")


# --- topology: event type -> subscribing service names ------------------------
SUBSCRIBERS: dict[str, list[str]] = {
    "exam.submitted":       ["drive-evaluation"],
    "submission.finalized": ["drive-evaluation"],
    # Auto-graded written-test result flows back to the drive's round marks.
    "evaluation.completed": ["drive-core"],
    "assessment.scored":    ["lms-progress", "lms-gamification"],
    "content.completed":    ["lms-progress", "lms-gamification"],
    "year.completed":       ["lms-certification", "lare-notify"],
    "certificate.issued":   ["lare-notify"],
    "result.published":     ["lare-notify"],
    "round.shortlisted":    ["lare-notify"],
    "offer.created":        ["lare-notify"],
    "badge.earned":         ["lare-notify"],
    "coach.nudge":          ["lare-notify"],
    "drive.registered":     [],
    # Drive registers the applicant so they appear in Candidates + Round 1.
    "candidate.registered": ["drive-core", "lare-notify"],
    "interview.decided":    ["lare-notify"],
}
# Sinks that receive EVERY event.
WILDCARD_SUBSCRIBERS: list[str] = ["lare-analytics", "lare-audit"]


def subscribers_for(event_type: str) -> list[str]:
    seen: list[str] = []
    for name in SUBSCRIBERS.get(event_type, []) + WILDCARD_SUBSCRIBERS:
        if name not in seen:
            seen.append(name)
    return seen


@dataclass
class Event:
    type: str
    payload: dict
    source: str
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    ts: float = field(default_factory=time.time)

    def as_dict(self) -> dict:
        return asdict(self)


class EventBus:
    def __init__(self, service_name: str, cfg):
        self.service = service_name
        self.cfg = cfg
        self.stream = getattr(cfg, "EVENT_STREAM", "lare:events")
        # Internal event delivery acts with broad internal roles so downstream
        # require_roles guards on any east-west follow-ups pass.
        self.client = ServiceClient(
            service_name, default_roles=["super_admin", "company_admin"], timeout=4
        )
        self._handlers: dict[str, list] = {}
        self._recorder: list[Event] = []  # test hook

        want = getattr(cfg, "EVENT_BUS_BACKEND", "auto")
        self.redis = get_redis(getattr(cfg, "REDIS_URL", "")) if want in ("auto", "redis") else None
        if want == "redis":
            self.backend = "redis"
        elif want == "http":
            self.backend = "http"
        elif want == "memory":
            self.backend = "memory"
        else:  # auto
            self.backend = "redis" if self.redis is not None else "http"
        log.info("event bus for %s using backend=%s", service_name, self.backend)

    # --- subscription (handlers live in the subscribing service) --------------
    def on(self, event_type: str, handler) -> None:
        self._handlers.setdefault(event_type, []).append(handler)

    def dispatch(self, event: Event) -> None:
        """Run local handlers for an incoming event (ingest / consumer / memory)."""
        for h in self._handlers.get(event.type, []) + self._handlers.get("*", []):
            try:
                h(event.payload, event)
            except Exception:  # noqa: BLE001 — one bad handler must not kill others
                log.exception("handler error for %s", event.type)

    # --- publication ----------------------------------------------------------
    def publish(self, event_type: str, payload: dict, *, key: str | None = None) -> Event:
        event = Event(type=event_type, payload=payload, source=self.service)
        self._recorder.append(event)
        if self.backend == "memory":
            self.dispatch(event)
            return event
        if self.backend == "redis" and self.redis is not None:
            try:
                self.redis.xadd(self.stream, {"e": json.dumps(event.as_dict())})
                return event
            except Exception:  # noqa: BLE001 — fall back to http fan-out
                log.warning("redis publish failed; falling back to http fan-out")
        # http fan-out
        for svc in subscribers_for(event_type):
            delivered = self.client.try_post(svc, "/events/v1/ingest", event.as_dict())
            if not delivered:
                log.warning("event %s not delivered to %s", event_type, svc)
        return event

    # --- redis consumer (prod) ------------------------------------------------
    def start_consumer(self) -> None:
        """Spawn a daemon consumer-group reader (no-op without Redis)."""
        if self.backend != "redis" or self.redis is None or not self._handlers:
            return
        group = f"cg-{self.service}"
        try:
            self.redis.xgroup_create(self.stream, group, id="$", mkstream=True)
        except Exception:  # noqa: BLE001 — group already exists
            pass

        def _loop():
            consumer = f"{self.service}-{uuid.uuid4().hex[:6]}"
            while True:
                try:
                    resp = self.redis.xreadgroup(
                        group, consumer, {self.stream: ">"}, count=16, block=5000
                    )
                    for _stream, entries in resp or []:
                        for msg_id, fields in entries:
                            try:
                                data = json.loads(fields["e"])
                                self.dispatch(Event(**data))
                            finally:
                                self.redis.xack(self.stream, group, msg_id)
                except Exception:  # noqa: BLE001
                    log.exception("consumer loop error")
                    time.sleep(1)

        threading.Thread(target=_loop, daemon=True, name=f"evbus-{self.service}").start()
        log.info("event consumer started for %s", self.service)


def setup_event_publisher(app, cfg) -> EventBus:
    """Give a service an EventBus (in ``app.extensions['bus']``) for publishing."""
    bus = EventBus(cfg.SERVICE_NAME, cfg)
    app.extensions["bus"] = bus
    return bus


def setup_event_subscriber(app, cfg, db, svc, register_handlers) -> EventBus:
    """Wire a service as an event subscriber: register its handlers, mount the
    ``/events/v1/ingest`` webhook (HTTP fan-out), and start the Redis consumer
    (no-op without Redis). The returned bus can also publish (chained events)."""
    bus = EventBus(cfg.SERVICE_NAME, cfg)
    register_handlers(bus, db, svc)
    app.register_blueprint(make_events_blueprint(bus))
    app.extensions["bus"] = bus
    bus.start_consumer()
    return bus


def make_events_blueprint(bus: EventBus) -> Blueprint:
    """Mount ``POST /events/v1/ingest`` so this service can receive HTTP fan-out.

    Internal-only: authenticated by the signed service token. The Gateway has no
    ``/events/`` route, so this webhook is never publicly reachable.
    """
    bp = Blueprint("events", __name__)

    @bp.post("/events/v1/ingest")
    def ingest():
        token = request.headers.get("X-Internal-Token", "")
        try:
            verify_service_token(token)
        except Exception:  # noqa: BLE001
            return error_payload("unauthorized", "invalid internal token"), 401
        body = request.get_json(silent=True) or {}
        try:
            event = Event(
                type=body["type"], payload=body.get("payload", {}),
                source=body.get("source", "?"),
                id=body.get("id", str(uuid.uuid4())), ts=body.get("ts", time.time()),
            )
        except KeyError:
            return error_payload("bad_request", "missing event type"), 400
        g.request_id = getattr(g, "request_id", event.id)
        bus.dispatch(event)
        return ok({"received": event.type})

    return bp
