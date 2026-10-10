"""Attention engine — derive prioritised actions from cross-service state.

Deterministic rules over evidence conflicts + the decision queue (both fetched
east-west by the route layer and passed in). Regeneration is idempotent via a
per-drive dedupe key; user resolution/dismissal is preserved across recomputes.
"""
from __future__ import annotations

from sqlalchemy import select

from .models import Action

_PRIO_RANK = {"critical": 0, "high": 1, "medium": 2}


class ActionService:
    def __init__(self, coverage_floor: float = 60.0, ready_confidence: float = 75.0):
        self.coverage_floor = coverage_floor
        self.ready_confidence = ready_confidence

    def _derive(self, conflicts, queue):
        out = []
        for c in conflicts or []:
            cid = c.get("candidate_id")
            out.append(dict(
                kind="evidence_conflict", priority="high", target_ref=cid,
                title=f"Reconcile evidence for {cid}",
                detail=f"{c.get('competency_key')} signals diverge by {round(c.get('delta', 0))} pts — reconcile before deciding.",
                impact_note="Blocks a trustworthy decision"))
        for q in queue or []:
            if q.get("decision"):
                continue
            cid = q.get("candidate_id")
            if q.get("panel_agreement") == "divergent":
                out.append(dict(
                    kind="panel_divergent", priority="high", target_ref=cid,
                    title=f"Divergent evaluations for {cid}",
                    detail="Panel signals disagree — a calibration or tie-break review is needed.",
                    impact_note="Decision confidence reduced"))
            cov = q.get("coverage_pct")
            if cov is not None and cov < self.coverage_floor:
                out.append(dict(
                    kind="coverage_gap", priority="medium", target_ref=cid,
                    title=f"Thin evidence for {cid}",
                    detail=f"Only {cov}% of the evaluation model is covered — gather more signal.",
                    impact_note="Low-confidence decision risk"))
            if (q.get("confidence") or 0) >= self.ready_confidence:
                out.append(dict(
                    kind="ready_decision", priority="medium", target_ref=cid,
                    title=f"{cid} is ready to decide",
                    detail=f"Decision confidence {q.get('confidence')} with strong evidence — advance or close.",
                    impact_note="Avoid pipeline aging"))
        return out

    def recompute(self, s, drive_id, conflicts, queue):
        derived = self._derive(conflicts, queue)
        existing = {a.dedupe_key: a for a in
                    s.scalars(select(Action).where(Action.drive_id == drive_id)).all()}
        for d in derived:
            key = f"{d['kind']}:{d['target_ref']}"
            a = existing.get(key)
            if a:
                if a.status == "open":
                    a.title, a.detail, a.priority = d["title"], d["detail"], d["priority"]
                    a.impact_note = d["impact_note"]
            else:
                s.add(Action(
                    drive_id=drive_id, dedupe_key=key, kind=d["kind"], priority=d["priority"],
                    title=d["title"], detail=d["detail"], target_ref=d["target_ref"],
                    impact_note=d["impact_note"]))
        s.flush()
        return self.list_open(s, drive_id)

    def list_open(self, s, drive_id):
        rows = s.scalars(select(Action).where(
            Action.drive_id == drive_id, Action.status == "open")).all()
        rows.sort(key=lambda a: (_PRIO_RANK.get(a.priority, 9), a.created_at or 0))
        return [self._dump(a) for a in rows]

    def resolve(self, s, action_id, by, status="resolved"):
        from lare_common.errors import NotFound
        a = s.get(Action, action_id)
        if not a:
            raise NotFound("Action not found")
        a.status = status
        a.resolved_by = by
        s.flush()
        return self._dump(a)

    @staticmethod
    def _dump(a):
        return {
            "id": a.id, "drive_id": a.drive_id, "kind": a.kind, "priority": a.priority,
            "title": a.title, "detail": a.detail, "target_ref": a.target_ref,
            "impact_note": a.impact_note, "status": a.status, "resolved_by": a.resolved_by,
            "created_at": a.created_at.isoformat() if a.created_at else None,
        }
