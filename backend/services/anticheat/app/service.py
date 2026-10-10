"""Anti-cheating logic: signal ingestion, weighted scoring, flagging, and
auto-submit trigger when the cumulative violation score crosses the threshold.

Best-effort client signals (devtools/print_screen) are weighted low and are
never the sole basis for disqualification — a human reviews flags."""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from lare_common.errors import Conflict, NotFound
from lare_common.security import new_id

from .models import Event, ProctorSession

# Weight per signal type. Hard integrity violations score high; best-effort /
# soft signals score low.
WEIGHTS = {
    "multiple_login": 60, "multiple_device": 60, "fullscreen_exit": 25,
    "tab_switch": 20, "window_blur": 15, "paste": 20, "copy": 10,
    "right_click": 5, "page_refresh": 10, "network_disconnect": 10,
    "idle_timeout": 5, "devtools_open": 15, "print_screen": 10,
}


class AntiCheatService:
    def __init__(self, threshold: int = 100, on_auto_submit=None):
        self.threshold = threshold
        # Called with exam_session_id when the auto-submit threshold is crossed.
        self.on_auto_submit = on_auto_submit

    def start(self, s: Session, data) -> ProctorSession:
        dup = s.execute(
            select(ProctorSession).where(
                ProctorSession.exam_session_id == data.exam_session_id)
        ).scalar_one_or_none()
        if dup:
            return dup
        ps = ProctorSession(id=new_id(), exam_session_id=data.exam_session_id,
                            candidate_id=data.candidate_id, drive_id=data.drive_id,
                            fingerprint=data.fingerprint, ip=data.ip, browser=data.browser)
        s.add(ps)
        s.flush()
        return ps

    def _get(self, s: Session, exam_session_id: str) -> ProctorSession:
        ps = s.execute(
            select(ProctorSession).where(
                ProctorSession.exam_session_id == exam_session_id)
        ).scalar_one_or_none()
        if not ps:
            raise NotFound("Proctor session not found", code="proctor_not_found")
        return ps

    def ingest(self, s: Session, exam_session_id: str, data) -> dict:
        ps = self._get(s, exam_session_id)
        weight = WEIGHTS.get(data.type, 5)
        s.add(Event(id=new_id(), proctor_session_id=ps.id, type=data.type, weight=weight,
                    ip=data.ip, browser=data.browser, device=data.device, meta=data.meta))
        ps.violation_score += weight

        action = "logged"
        triggered = False
        if ps.violation_score >= self.threshold and ps.status != "auto_submitted":
            ps.status = "auto_submitted"
            action = "auto_submit"   # signals the Exam Engine to force-submit
            triggered = True
        elif ps.violation_score >= self.threshold * 0.5 and ps.status == "active":
            ps.status = "flagged"
            action = "flagged"
        s.flush()

        # Deliver the auto-submit signal to the Exam Engine exactly once.
        if triggered and self.on_auto_submit:
            self.on_auto_submit(exam_session_id)

        return {"exam_session_id": exam_session_id, "type": data.type, "weight": weight,
                "violation_score": ps.violation_score, "status": ps.status,
                "action": action, "threshold": self.threshold}

    def summary(self, s: Session, exam_session_id: str) -> dict:
        ps = self._get(s, exam_session_id)
        by_type = dict(s.execute(
            select(Event.type, func.count(Event.id))
            .where(Event.proctor_session_id == ps.id).group_by(Event.type)
        ).all())
        # Integrity score: 100 minus violations, floored at 0.
        integrity = max(0, 100 - ps.violation_score)
        return {"exam_session_id": exam_session_id, "candidate_id": ps.candidate_id,
                "violation_score": ps.violation_score, "integrity_score": integrity,
                "status": ps.status, "events_by_type": by_type}

    def drive_report(self, s: Session, drive_id: str) -> dict:
        sessions = s.execute(
            select(ProctorSession).where(ProctorSession.drive_id == drive_id)
        ).scalars().all()
        return {
            "drive_id": drive_id, "sessions": len(sessions),
            "flagged": sum(1 for p in sessions if p.status in ("flagged", "auto_submitted")),
            "auto_submitted": sum(1 for p in sessions if p.status == "auto_submitted"),
            "candidates": [
                {"candidate_id": p.candidate_id, "exam_session_id": p.exam_session_id,
                 "violation_score": p.violation_score, "status": p.status}
                for p in sessions
            ],
        }
