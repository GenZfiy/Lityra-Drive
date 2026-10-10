"""Evaluation subscribes to exam submission: when an exam is submitted (by the
candidate, on timeout, or force-submitted by Anti-Cheating) it auto-grades the
session against the stored answer key. If no key has been registered yet the run
is skipped (logged) — grading happens once the key exists / on re-evaluation."""
from __future__ import annotations

import logging
from types import SimpleNamespace

from lare_common.errors import NotFound

log = logging.getLogger("lare-evaluation")


def register_handlers(bus, db, svc) -> None:
    def on_submitted(payload, event):
        p = payload or {}
        if not (p.get("exam_id") and p.get("session_id")):
            return
        data = SimpleNamespace(
            exam_id=p["exam_id"],
            session_id=p["session_id"],
            candidate_id=p.get("candidate_id", "unknown"),
            answers=p.get("answers") or {},
            coding_scores=p.get("coding_scores") or {},
        )
        with db.session() as s:
            try:
                result = svc.run(s, data)
                log.info("auto-graded session %s: %.1f%%", data.session_id,
                         result.get("percentage", 0))
            except NotFound:
                log.info("no answer key for exam %s yet; skipping auto-grade", data.exam_id)
                return
        # Publish the graded result so the Drive can post it into the written-test
        # round marks. Carries the drive linkage the exam.submitted event provided.
        bus.publish("evaluation.completed", {
            "exam_id": data.exam_id, "session_id": data.session_id,
            "candidate_id": data.candidate_id,
            "drive_id": p.get("drive_id"), "round_id": p.get("round_id"),
            "total": result.get("total", 0), "max_score": result.get("max_score", 0),
            "percentage": result.get("percentage", 0),
            "passed": result.get("passed", False),
            "needs_review": result.get("needs_review", False),
            "total_questions": result.get("total_questions", 0),
            "correct_count": result.get("correct_count", 0),
            "attempted_count": result.get("attempted_count", 0),
            "coding_total": result.get("coding_total", 0),
            "coding_attempted": result.get("coding_attempted", 0),
            "coding_correct": result.get("coding_correct", 0),
        })

    bus.on("exam.submitted", on_submitted)
    bus.on("submission.finalized", on_submitted)
