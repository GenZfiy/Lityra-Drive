"""Decision intelligence — deterministic coverage / agreement / confidence.

All metrics here are computed arithmetically from evidence (no LLM), so a
decision's coverage, panel agreement, and confidence are reproducible and
auditable. Evidence is fetched from the evidence service by the route layer and
passed in, keeping this logic pure and unit-testable.
"""
from __future__ import annotations

from sqlalchemy import select

from .models import Decision, DecisionEvidence


def _mean(vals):
    return sum(vals) / len(vals) if vals else 0.0


class DecisionService:
    def __init__(self, agreement_spread: float = 25.0):
        self.agreement_spread = agreement_spread

    # ---------- deterministic assessment ----------
    def assess(self, evidence_rows, model_weights=None):
        by: dict[str, list[float]] = {}
        for e in evidence_rows:
            by.setdefault(e["competency_key"], []).append(float(e["signal"]))

        required = [w["competency_key"] for w in (model_weights or [])]
        if required:
            covered = [k for k in required if k in by]
            coverage_pct = round(len(covered) / len(required) * 100)
            missing = sorted(set(required) - set(by.keys()))
        else:
            coverage_pct = None
            missing = []

        spreads = [max(v) - min(v) for v in by.values() if len(v) >= 2]
        agreement = "unknown" if not spreads else ("divergent" if max(spreads) > self.agreement_spread else "aligned")

        if model_weights:
            wmap = {w["competency_key"]: w["weight"] for w in model_weights}
            num = den = 0.0
            for k, vals in by.items():
                w = wmap.get(k, 0.0)
                if w:
                    num += _mean(vals) * w
                    den += w
            score = round(num / den, 1) if den else round(_mean([x for v in by.values() for x in v]), 1)
        else:
            score = round(_mean([x for v in by.values() for x in v]), 1)

        confidence = score
        if coverage_pct is not None:
            confidence = confidence * (0.5 + 0.5 * coverage_pct / 100)
        if agreement == "divergent":
            confidence *= 0.8
        return {
            "score": score, "confidence": round(confidence, 1),
            "coverage_pct": coverage_pct, "missing_competencies": missing,
            "panel_agreement": agreement, "evidence_count": len(evidence_rows),
            "competencies": sorted(by.keys()),
        }

    # ---------- record (cites exact evidence) ----------
    def record(self, s, *, drive_id, candidate_id, round_key, verdict, note,
               evidence_ids, decided_by, assessment):
        d = Decision(
            drive_id=drive_id, candidate_id=candidate_id, round_key=round_key,
            verdict=verdict, decided_by=decided_by,
            evidence_coverage_pct=assessment.get("coverage_pct"),
            panel_agreement=assessment.get("panel_agreement", "unknown"),
            missing_competencies=assessment.get("missing_competencies", []),
            confidence=assessment.get("confidence"), note=note,
        )
        s.add(d)
        s.flush()
        for eid in evidence_ids or []:
            s.add(DecisionEvidence(decision_id=d.id, evidence_id=eid))
        s.flush()
        return self._dump(d, cited=list(evidence_ids or []))

    # ---------- queries ----------
    def for_drive(self, s, drive_id):
        rows = s.scalars(select(Decision).where(Decision.drive_id == drive_id)
                         .order_by(Decision.created_at.desc())).all()
        return [self._dump(d) for d in rows]

    def for_candidate(self, s, candidate_id, drive_id=None):
        q = select(Decision).where(Decision.candidate_id == candidate_id)
        if drive_id:
            q = q.where(Decision.drive_id == drive_id)
        rows = s.scalars(q.order_by(Decision.created_at.desc())).all()
        return [self._dump(d) for d in rows]

    def queue(self, s, drive_id, evidence_rows, model_weights):
        by_cand: dict[str, list] = {}
        for e in evidence_rows:
            by_cand.setdefault(e["candidate_id"], []).append(e)
        decided = {d.candidate_id: d.verdict for d in
                   s.scalars(select(Decision).where(Decision.drive_id == drive_id)).all()}
        out = []
        for cand, rows in by_cand.items():
            a = self.assess(rows, model_weights)
            out.append({"candidate_id": cand, "decision": decided.get(cand), **a})
        out.sort(key=lambda x: (x["decision"] is not None, -x["confidence"]))
        return out

    # ---------- serialisation ----------
    def _dump(self, d, cited=None):
        if cited is None:
            cited = [ce.evidence_id for ce in d.cited]
        return {
            "id": d.id, "drive_id": d.drive_id, "candidate_id": d.candidate_id,
            "round_key": d.round_key, "verdict": d.verdict, "decided_by": d.decided_by,
            "evidence_coverage_pct": d.evidence_coverage_pct,
            "panel_agreement": d.panel_agreement,
            "missing_competencies": d.missing_competencies or [],
            "confidence": d.confidence, "note": d.note,
            "cited_evidence": cited,
            "created_at": d.created_at.isoformat() if d.created_at else None,
        }
