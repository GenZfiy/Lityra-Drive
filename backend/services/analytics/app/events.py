"""Analytics is a wildcard event sink: every domain event becomes one or more
facts in the append-only fact store, feeding the KPI rollups and the college
readiness index. Replaces the old manual fact ingestion."""
from __future__ import annotations

from types import SimpleNamespace


def _fact(**kw) -> SimpleNamespace:
    base = dict(kind="event", metric="event", value=1.0, college_id=None,
                cohort_id=None, learner_id=None, drive_id=None)
    base.update(kw)
    return SimpleNamespace(**base)


def _facts_for(etype: str, p: dict) -> list[SimpleNamespace]:
    if etype in ("exam.submitted", "submission.finalized"):
        return [_fact(kind="drive", metric="exam_submitted", value=1.0,
                      drive_id=p.get("drive_id"), learner_id=p.get("candidate_id"))]
    if etype == "assessment.scored":
        return [_fact(kind="lms", metric="avg_score", value=float(p.get("score", 0)),
                      learner_id=p.get("learner_id"), college_id=p.get("college_id"))]
    if etype == "content.completed":
        return [_fact(kind="lms", metric="engagement", value=100.0,
                      learner_id=p.get("learner_id"), college_id=p.get("college_id"))]
    if etype == "year.completed":
        return [
            _fact(kind="lms", metric="attendance", value=float(p.get("attendance_pct", 0)),
                  learner_id=p.get("learner_id"), college_id=p.get("college_id")),
            _fact(kind="lms", metric="avg_score", value=float(p.get("avg_score", 0)),
                  learner_id=p.get("learner_id"), college_id=p.get("college_id")),
        ]
    if etype == "certificate.issued":
        return [_fact(kind="lms", metric="certification", value=100.0,
                      learner_id=p.get("learner_id"), college_id=p.get("college_id"))]
    if etype == "result.published":
        won = str(p.get("outcome", "")).lower() in ("selected", "ppo", "offer")
        return [_fact(kind="drive", metric="placement", value=100.0 if won else 0.0,
                      drive_id=p.get("drive_id"), learner_id=p.get("candidate_id"),
                      college_id=p.get("college_id"))]
    # generic fact so nothing is lost
    return [_fact(kind="event", metric=etype.replace(".", "_"),
                  value=float(p.get("value", 1)), college_id=p.get("college_id"),
                  learner_id=p.get("learner_id"), drive_id=p.get("drive_id"))]


def register_handlers(bus, db, svc) -> None:
    def on_event(payload, event):
        facts = _facts_for(event.type, payload or {})
        if facts:
            with db.session() as s:
                svc.ingest(s, facts)

    bus.on("*", on_event)
