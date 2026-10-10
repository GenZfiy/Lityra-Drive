"""The evidence ledger records signals automatically.

* ``evaluation.completed`` — a written/coding assessment was auto-graded; append
  an ``assessment`` evidence row (signal = percentage, high confidence). This is
  the same event the drive-core service uses to fill Round 1 marks, so evidence
  and marks stay consistent.

Publishing (``evidence.added`` / ``evidence.conflict.opened``) is done by the
route/handler after commit so downstream consumers (action engine, recruit-ai)
never see uncommitted rows. Handlers are idempotent-safe: append is INSERT-only,
and duplicate signals simply add another (audited) row.
"""
from __future__ import annotations

import logging

log = logging.getLogger("lare-evidence")


def register_handlers(bus, db, svc) -> None:
    def on_evaluation_completed(payload, event):
        p = payload or {}
        did = p.get("drive_id")
        cand = p.get("candidate_id")
        if not (did and cand):
            return  # assessment not linked to a drive
        pct = float(p.get("percentage", 0) or 0)
        with db.session() as s:
            res = svc.append(
                s, drive_id=did, candidate_id=cand, competency_key="overall",
                source_type="assessment", source_ref=p.get("exam_id") or p.get("session_id"),
                signal=pct, confidence="high",
                rationale="Auto-graded assessment result",
                round_key=p.get("round_key") or "round-1", actor_id="system",
            )
        bus.publish("evidence.added", {
            "drive_id": did, "candidate_id": cand,
            "competency_key": "overall", "signal": pct,
        })
        for c in res.get("conflicts", []):
            bus.publish("evidence.conflict.opened", c, key=cand)
        log.info("evidence appended for %s on drive %s (%.0f%%)", cand, did, pct)

        # Per-competency breakdown: when the assessment included a coding section,
        # emit a separate "coding" competency signal so coverage/decisions/calibration
        # can distinguish coding ability from the overall score.
        coding_total = float(p.get("coding_total", 0) or 0)
        if coding_total > 0:
            coding_pct = round(float(p.get("coding_correct", 0) or 0) / coding_total * 100, 1)
            with db.session() as s:
                svc.append(
                    s, drive_id=did, candidate_id=cand, competency_key="coding",
                    source_type="coding", source_ref=p.get("exam_id") or p.get("session_id"),
                    signal=coding_pct, confidence="high",
                    rationale="Auto-graded coding section",
                    round_key=p.get("round_key") or "round-1", actor_id="system")
            bus.publish("evidence.added", {
                "drive_id": did, "candidate_id": cand,
                "competency_key": "coding", "signal": coding_pct,
            })
            log.info("coding evidence appended for %s on drive %s (%.0f%%)", cand, did, coding_pct)

    bus.on("evaluation.completed", on_evaluation_completed)
