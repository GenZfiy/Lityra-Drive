"""Drive subscribes to two upstream events so the recruiter console stays live:

* ``candidate.registered`` — a student applied; register them on the drive so
  they show under Candidates and are seeded into Round 1.
* ``evaluation.completed`` — a written test was auto-graded; post the score
  into the marks sheet of the ROUND that exam belongs to (each written round
  has its own paper). Panel rounds are still entered by hand.

Both handlers are idempotent and ignore events for drives this instance does not
own, so replays and cross-drive fan-out are harmless.
"""
from __future__ import annotations

import logging

log = logging.getLogger("lare-drive")


def register_handlers(bus, db, svc) -> None:
    def on_candidate_registered(payload, event):
        p = payload or {}
        did = p.get("drive_id")
        cand = p.get("candidate_id") or p.get("user_id")
        if not (did and cand):
            return
        with db.session() as s:
            svc.ensure_registration(s, did, cand)
        log.info("registered candidate %s on drive %s", cand, did)

    def on_evaluation_completed(payload, event):
        p = payload or {}
        did = p.get("drive_id")
        cand = p.get("candidate_id")
        if not (did and cand):
            return  # exam not linked to a drive, or unknown candidate
        with db.session() as s:
            svc.record_evaluation(
                s, did, cand,
                total=p.get("total", 0), max_score=p.get("max_score", 0),
                percentage=p.get("percentage", 0), passed=p.get("passed", False),
                needs_review=p.get("needs_review", False),
                total_questions=p.get("total_questions", 0),
                correct_count=p.get("correct_count", 0),
                attempted_count=p.get("attempted_count", 0),
                coding_total=p.get("coding_total", 0),
                coding_attempted=p.get("coding_attempted", 0),
                coding_correct=p.get("coding_correct", 0),
                round_id=p.get("round_id"))          # → post into the exam's round
        log.info("recorded written-test result for %s on drive %s (%.0f%%)",
                 cand, did, p.get("percentage", 0))

    bus.on("candidate.registered", on_candidate_registered)
    bus.on("evaluation.completed", on_evaluation_completed)
