"""Audit is a wildcard event sink: every domain event is appended to the
hash-chained, tamper-evident log. Drive events chain under drive:<id> so a drive
integrity report can verify the whole pipeline end to end."""
from __future__ import annotations

from types import SimpleNamespace


def register_handlers(bus, db, svc) -> None:
    def on_event(payload, event):
        p = payload or {}
        drive_id = p.get("drive_id")
        partition = f"drive:{drive_id}" if drive_id else "platform"
        # When an event names the human who caused it (administrative actions do),
        # attribute the audit record to that user rather than the emitting service.
        actor_id = p.get("actor_id")
        actor_type = p.get("actor_type") or ("user" if actor_id else "service")
        data = SimpleNamespace(
            partition_key=partition,
            actor_type=actor_type,
            actor_id=actor_id or event.source,
            action=event.type,
            entity_type=p.get("entity_type", "event"),
            entity_id=p.get("entity_id") or p.get("session_id") or event.id,
            meta=p,
            ip=None,
            device=None,
            correlation_id=event.id,
        )
        with db.session() as s:
            svc.append(s, data)

    bus.on("*", on_event)
