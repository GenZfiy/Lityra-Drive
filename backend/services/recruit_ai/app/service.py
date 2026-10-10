"""Recruitment insight + calibration logic — deterministic derivations.

Structural computations (which candidates are ready, coverage gaps, panel
divergence, interviewer drift) are deterministic and reproducible. The stored
insight shape is LLM-ready; today it is narrated by rules (mode="derived").
"""
from __future__ import annotations

import json

from sqlalchemy import delete, select

from .models import Calibration, Insight


class RecruitAiService:
    def __init__(self, ready_confidence: float = 75.0, coverage_floor: float = 60.0, ai=None):
        self.ready_confidence = ready_confidence
        self.coverage_floor = coverage_floor
        self.ai = ai  # optional lare_common.ai client; narrates when live

    def _narrate(self, derived):
        """When a live AI provider is configured, sharpen each insight's impact
        line. Deterministic structure is preserved; only prose is rewritten.
        Falls back to the derived text (mode 'derived') on stub/failure."""
        if not derived or not self.ai or getattr(self.ai, "mode", "stub") == "stub":
            return derived, "derived", "rule-based"
        system = (
            "You are a recruitment operations analyst. For each insight, rewrite ONLY the "
            "'impact' as one sharp, specific sentence for a hiring lead. Do not invent numbers "
            "or names. Return JSON {\"items\":[{\"title\":str,\"impact\":str}]} preserving order and titles."
        )
        payload = {"items": [{"title": d["title"], "observation": d["observation"], "impact": d["impact"]} for d in derived]}
        try:
            parsed, res = self.ai.complete_json(
                system=system, messages=[{"role": "user", "content": json.dumps(payload)}],
                fallback={"items": []})
        except Exception:  # noqa: BLE001
            return derived, "derived", "rule-based"
        if getattr(res, "stub", True) or not parsed.get("items"):
            return derived, "derived", "rule-based"
        by_title = {it.get("title"): it.get("impact") for it in parsed["items"] if it.get("title")}
        for d in derived:
            if by_title.get(d["title"]):
                d["impact"] = by_title[d["title"]]
        return derived, "live", getattr(res, "model", "llm")

    # ---------- insights (O/R/I/A) ----------
    def _derive(self, queue, conflicts):
        insights = []
        ready = [q for q in queue if not q.get("decision") and (q.get("confidence") or 0) >= self.ready_confidence]
        thin = [q for q in queue if q.get("coverage_pct") is not None and q["coverage_pct"] < self.coverage_floor and not q.get("decision")]
        divergent = [q for q in queue if q.get("panel_agreement") == "divergent" and not q.get("decision")]

        if conflicts:
            cands = sorted({c.get("candidate_id") for c in conflicts})
            insights.append(dict(
                severity="warn", title="Evidence conflicts need reconciliation",
                observation=f"{len(conflicts)} open evidence conflict(s) across {len(cands)} candidate(s).",
                reason="Two or more signals for the same competency diverge beyond the trust threshold.",
                impact="Decisions built on conflicting evidence are low-trust and may be reversed.",
                recommended_action={"label": "Open Evidence Ledger", "target": "evidence"},
                related_refs=cands[:8]))
        if ready:
            top = max(ready, key=lambda q: q.get("confidence") or 0)
            insights.append(dict(
                severity="teal", title=f"{len(ready)} candidate(s) ready to decide",
                observation=f"{len(ready)} undecided candidate(s) have decision confidence ≥ {int(self.ready_confidence)}, led by {top.get('candidate_id')} ({top.get('confidence')}).",
                reason="Coverage and agreement are sufficient for a confident call.",
                impact="Deciding now shortens time-to-offer and reduces pipeline aging.",
                recommended_action={"label": "Open Decisions", "target": "decisions"},
                related_refs=[q.get("candidate_id") for q in ready][:8]))
        if thin:
            insights.append(dict(
                severity="brand", title=f"{len(thin)} candidate(s) have thin evidence",
                observation=f"{len(thin)} candidate(s) are below {int(self.coverage_floor)}% model coverage.",
                reason="Too few competencies have been evaluated to decide reliably.",
                impact="Any decision now carries an elevated risk of being wrong.",
                recommended_action={"label": "Review candidates", "target": "candidates"},
                related_refs=[q.get("candidate_id") for q in thin][:8]))
        if divergent:
            insights.append(dict(
                severity="risk", title=f"{len(divergent)} candidate(s) show panel divergence",
                observation=f"Evaluators disagree on {len(divergent)} candidate(s).",
                reason="Signal spread for at least one competency exceeds the agreement threshold.",
                impact="Divergence signals a calibration gap that skews decisions.",
                recommended_action={"label": "Open calibration", "target": "calibration"},
                related_refs=[q.get("candidate_id") for q in divergent][:8]))
        return insights

    def generate(self, s, drive_id, queue, conflicts):
        derived = self._derive(queue, conflicts)
        derived, mode, model = self._narrate(derived)
        s.execute(delete(Insight).where(Insight.drive_id == drive_id))
        rows = []
        for d in derived:
            row = Insight(drive_id=drive_id, mode=mode, model=model, **d)
            s.add(row)
            rows.append(row)
        s.flush()
        return [self._dump_insight(r) for r in rows]

    def list_insights(self, s, drive_id):
        rows = s.scalars(select(Insight).where(Insight.drive_id == drive_id)
                         .order_by(Insight.created_at.desc())).all()
        return [self._dump_insight(r) for r in rows]

    # ---------- calibration (interviewer drift vs consensus) ----------
    def calibration(self, s, drive_id, evidence_rows):
        groups: dict[tuple, list[float]] = {}
        for e in evidence_rows:
            groups.setdefault((e["candidate_id"], e["competency_key"]), []).append(float(e["signal"]))
        gmean = {k: sum(v) / len(v) for k, v in groups.items()}

        agg: dict[tuple, dict] = {}
        for e in evidence_rows:
            if e.get("source_type") != "interview":
                continue
            actor = e.get("actor_id")
            if not actor:
                continue
            key = (actor, e["competency_key"])
            d = float(e["signal"]) - gmean[(e["candidate_id"], e["competency_key"])]
            a = agg.setdefault(key, {"sum": 0.0, "n": 0})
            a["sum"] += d
            a["n"] += 1

        s.execute(delete(Calibration).where(Calibration.drive_id == drive_id))
        out = []
        for (actor, comp), a in agg.items():
            mean_delta = round(a["sum"] / a["n"], 1) if a["n"] else 0.0
            row = Calibration(drive_id=drive_id, interviewer_id=actor, competency_key=comp,
                              mean_delta=mean_delta, sample_n=a["n"])
            s.add(row)
            out.append({"interviewer_id": actor, "competency_key": comp,
                        "mean_delta": mean_delta, "sample_n": a["n"]})
        s.flush()
        out.sort(key=lambda x: abs(x["mean_delta"]), reverse=True)
        return out

    def cross_calibration(self, s):
        """Aggregate stored per-drive calibration into a cross-drive view per
        interviewer + competency (mean drift weighted by sample size)."""
        rows = s.scalars(select(Calibration)).all()
        agg: dict[tuple, dict] = {}
        for r in rows:
            a = agg.setdefault((r.interviewer_id, r.competency_key), {"num": 0.0, "n": 0, "drives": set()})
            a["num"] += r.mean_delta * r.sample_n
            a["n"] += r.sample_n
            a["drives"].add(r.drive_id)
        out = []
        for (iv, comp), a in agg.items():
            out.append({
                "interviewer_id": iv, "competency_key": comp,
                "mean_delta": round(a["num"] / a["n"], 1) if a["n"] else 0.0,
                "sample_n": a["n"], "drive_count": len(a["drives"]),
            })
        out.sort(key=lambda x: abs(x["mean_delta"]), reverse=True)
        return out

    @staticmethod
    def _dump_insight(r):
        return {
            "id": r.id, "drive_id": r.drive_id, "severity": r.severity, "title": r.title,
            "observation": r.observation, "reason": r.reason, "impact": r.impact,
            "recommended_action": r.recommended_action or {}, "related_refs": r.related_refs or [],
            "mode": r.mode, "model": r.model,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
