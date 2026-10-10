"""Recruitment drive logic: drives, roles, eligibility, rounds, funnel, PPO."""
from __future__ import annotations

import secrets
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from datetime import datetime, timedelta, timezone

from lare_common.errors import BadRequest, Conflict, NotFound
from lare_common.security import new_id
from lare_common.service_client import ServiceClient

_ACCESS_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
DRIVE_ACCESS_HOURS = 12


def _as_utc(dt: datetime) -> datetime:
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt

# East-west clients: Candidate has name/email/roll; Auth is the fallback for
# name/email (e.g. staff accounts with no candidate record).
_AUTH = ServiceClient("drive-core", default_roles=["company_admin"], timeout=5)
_CAND = ServiceClient("drive-core", default_roles=["company_admin"], timeout=5)
# Reads the candidate's Hire skill profile (drive-exam performance) for matching.
_EVAL = ServiceClient("drive-core", default_roles=["recruiter"], timeout=6)


def _resolve_names(candidate_ids: list[str]) -> dict[str, dict]:
    """Best-effort user_id -> {name, email, roll}. Prefers the Candidate service
    (has the roll number), falls back to Auth for any missing name/email. Never
    fatal: on failure candidates simply show by id."""
    ids = [c for c in dict.fromkeys(candidate_ids) if c]
    if not ids:
        return {}
    out: dict[str, dict] = {}
    try:
        resp = _CAND.get("drive-candidate", "/drive/v1/candidates/resolve?ids=" + ",".join(ids))
        for uid, info in ((resp or {}).get("data") or {}).items():
            out[uid] = {"name": info.get("full_name"), "email": info.get("email"),
                        "roll": info.get("roll_number"), "phone": info.get("phone"),
                        "student_id": info.get("student_id")}
    except Exception:  # noqa: BLE001 — labelling is cosmetic
        pass
    # Fill gaps (no candidate record / missing name) from Auth.
    missing = [i for i in ids if not (out.get(i) or {}).get("name")]
    if missing:
        try:
            resp = _AUTH.get("auth", "/auth/v1/users?ids=" + ",".join(missing))
            for u in (resp or {}).get("data", []):
                cur = out.get(u["id"], {})
                out[u["id"]] = {"name": cur.get("name") or u.get("full_name"),
                                "email": cur.get("email") or u.get("email"),
                                "roll": cur.get("roll")}
        except Exception:  # noqa: BLE001
            pass
    return out


def _utcnow() -> datetime:
    return datetime.now(tz=timezone.utc)

from .models import (
    ApplicationForm, Drive, DriveAccessCode, DriveAccessSession, DriveRole,
    EligibilityRule, FormSubmission, PpoConfig, Registration, Round, RoundScore,
    SeatAllocation,
)


class DriveService:
    # ---------- drives ----------
    def create(self, s: Session, data, creator: str) -> Drive:
        d = Drive(id=new_id(), company_id=data.company_id, company_name=data.company_name,
                  title=data.title, reporting_time=data.reporting_time, venue=data.venue,
                  contact_email=data.contact_email, created_by=creator)
        s.add(d)
        s.flush()
        return d

    def get(self, s: Session, did: str) -> Drive:
        d = s.get(Drive, did)
        if not d:
            raise NotFound("Drive not found", code="drive_not_found")
        return d

    def list(self, s: Session, status: str | None, limit: int) -> list[Drive]:
        q = select(Drive)
        if status:
            q = q.where(Drive.status == status)
        return list(s.execute(q.limit(limit)).scalars().all())

    def delete(self, s: Session, did: str) -> dict:
        """Delete a drive and all its data (roles, rounds, registrations, scores,
        forms, seats, PPO). FK ON DELETE CASCADE handles the dependents."""
        d = self.get(s, did)
        title = d.title
        s.delete(d)
        s.flush()
        return {"id": did, "title": title, "deleted": True}

    def open_drive(self, s: Session, did: str) -> Drive:
        d = self.get(s, did)
        if not d.rounds:
            raise Conflict("Add at least one round before opening", code="no_rounds")
        d.status = "open"
        return d

    # ---------- Skills-to-Opportunity match (Lityra Hire) ----------
    def _candidate_skill_map(self, candidate_id: str) -> dict[str, float]:
        """name(lower) -> mastery, from the candidate's Hire skill twin (their
        drive-exam performance). Best-effort: no twin data → empty map → every
        required skill counts as a gap, which is the honest 0% match."""
        try:
            resp = _EVAL.get("drive-evaluation",
                             "/drive/v1/evaluations/twin/{}".format(candidate_id),
                             user_id=candidate_id)
        except Exception:  # noqa: BLE001
            return {}
        data = (resp or {}).get("data") or resp or {}
        m: dict[str, float] = {}
        for row in (data.get("topics") or []) + (data.get("by_category") or []):
            name = str(row.get("name", "")).strip().lower()
            if name:
                m[name] = max(m.get(name, 0.0), float(row.get("mastery") or 0))
        return m

    @staticmethod
    def _drive_required_skills(d: Drive) -> dict[str, float]:
        """Merge required skills across a drive's roles: skill name -> max weight."""
        req: dict[str, float] = {}
        for role in (d.roles or []):
            for sk in (role.skills or []):
                name = str(sk.get("name", "")).strip()
                if not name:
                    continue
                w = float(sk.get("weight") or 1.0)
                req[name] = max(req.get(name, 0.0), w)
        return req

    def match_opportunities(self, s: Session, candidate_id: str,
                            threshold: float = 55.0, bound_drive_id: str | None = None) -> dict:
        """Rank OPEN drives by how well the candidate's skills match the roles'
        required skills. Returns matched skills, gaps, and a match %."""
        skill_map = self._candidate_skill_map(candidate_id)
        drives = self.list(s, status="open", limit=200)
        # A gated candidate is bound to one drive — only that drive is an option.
        if bound_drive_id:
            drives = [d for d in drives if d.id == bound_drive_id]
        matches, unspecified = [], []
        for d in drives:
            req = self._drive_required_skills(d)
            base = {"drive_id": d.id, "title": d.title, "company_name": d.company_name,
                    "reporting_time": d.reporting_time, "venue": d.venue,
                    "roles": [self.role_out(r) for r in (d.roles or [])]}
            if not req:
                unspecified.append(base)
                continue
            matched, missing = [], []
            num = den = 0.0
            for name, weight in req.items():
                mastery = skill_map.get(name.lower(), 0.0)
                num += weight * min(mastery, 100.0) / 100.0
                den += weight
                entry = {"name": name, "mastery": round(mastery, 1), "weight": weight}
                (matched if mastery >= threshold else missing).append(entry)
            match_pct = round(num / den * 100.0, 1) if den else 0.0
            matched.sort(key=lambda r: r["mastery"], reverse=True)
            missing.sort(key=lambda r: (-r["weight"], r["mastery"]))
            matches.append({**base, "match_pct": match_pct,
                            "matched": matched, "missing": missing,
                            "required_count": len(req)})
        matches.sort(key=lambda r: r["match_pct"], reverse=True)
        return {"candidate_id": candidate_id, "has_skill_data": bool(skill_map),
                "matches": matches, "unspecified": unspecified}

    # ---------- roles / eligibility / rounds ----------
    def add_role(self, s: Session, did: str, data) -> DriveRole:
        self.get(s, did)
        skills = [{"name": sk.name, "weight": sk.weight}
                  for sk in (getattr(data, "skills", None) or [])]
        r = DriveRole(id=new_id(), drive_id=did, title=data.title, ctc=data.ctc,
                      positions=data.positions, description=data.description,
                      skills=skills)
        s.add(r)
        s.flush()
        return r

    def set_eligibility(self, s: Session, did: str, data) -> EligibilityRule:
        self.get(s, did)
        rule = {"min_cgpa": data.min_cgpa, "branches": data.branches,
                "max_backlogs": data.max_backlogs, "min_lms_score": data.min_lms_score}
        er = s.execute(
            select(EligibilityRule).where(EligibilityRule.drive_id == did)
        ).scalar_one_or_none()
        if er is None:
            er = EligibilityRule(id=new_id(), drive_id=did, rule=rule)
            s.add(er)
        else:
            er.rule = rule
        s.flush()
        return er

    def add_round(self, s: Session, did: str, data) -> Round:
        self.get(s, did)
        r = Round(id=new_id(), drive_id=did, order=data.order, type=data.type,
                  config=data.config, service_ref=data.service_ref)
        s.add(r)
        s.flush()
        return r

    def rounds(self, s: Session, did: str) -> list[Round]:
        return list(s.execute(
            select(Round).where(Round.drive_id == did).order_by(Round.order)
        ).scalars().all())

    # ---------- configurable workflow engine (req #4) ----------
    def set_workflow(self, s: Session, did: str, stages: list[dict]) -> list[dict]:
        """Replace the drive's ordered stage pipeline in one shot (drag-and-drop
        reorder on the client). Each stage: {type, label?, optional?, config?}."""
        self.get(s, did)
        for r in self.rounds(s, did):
            s.delete(r)
        s.flush()
        out = []
        for i, st in enumerate(stages, start=1):
            r = Round(id=new_id(), drive_id=did, order=st.get("order", i),
                      type=st.get("type", "aptitude"), label=st.get("label"),
                      optional=bool(st.get("optional", False)),
                      config=st.get("config", {}), service_ref=st.get("service_ref"))
            s.add(r)
            out.append(st)
        s.flush()
        return self.workflow(s, did)

    def workflow(self, s: Session, did: str) -> list[dict]:
        return [{"order": r.order, "type": r.type, "label": r.label,
                 "optional": r.optional, "config": r.config, "service_ref": r.service_ref}
                for r in self.rounds(s, did)]

    def delete_round(self, s: Session, did: str, order: int) -> dict:
        """Remove one round mid-pipeline and re-sequence everything after it, so
        candidates flow straight into the next round. E.g. deleting GD (round 2)
        from Written→GD→JAM→Interview leaves Written→JAM→Interview and the people
        who were heading to GD now sit in JAM."""
        self.get(s, did)
        rounds = self.rounds(s, did)
        if len(rounds) <= 1:
            raise BadRequest("A drive must keep at least one round.", code="min_one_round")
        if not any(r.order == order for r in rounds):
            raise NotFound("Round not found.", code="round_not_found")

        # 1) drop the round definition and its marks rows
        for r in rounds:
            if r.order == order:
                s.delete(r)
        for rs in s.execute(select(RoundScore).where(
                RoundScore.drive_id == did, RoundScore.round_order == order)).scalars().all():
            s.delete(rs)
        s.flush()

        # 2) shift every later round (and its marks) up by one slot
        for r in self.rounds(s, did):
            if r.order > order:
                r.order -= 1
        for rs in s.execute(select(RoundScore).where(
                RoundScore.drive_id == did, RoundScore.round_order > order)).scalars().all():
            rs.round_order -= 1
        # 3) move candidates: those past the deleted round step back one; those who
        #    were sitting in it now belong to the round that shifted into its slot
        for reg in s.execute(select(Registration).where(
                Registration.drive_id == did)).scalars().all():
            if reg.current_round > order:
                reg.current_round -= 1
        s.flush()

        # 4) seed the new round's marks sheet for candidates now sitting in it
        n_rounds = len(self.rounds(s, did))
        if order <= n_rounds:
            existing = {rs.candidate_id for rs in s.execute(select(RoundScore).where(
                RoundScore.drive_id == did, RoundScore.round_order == order)).scalars().all()}
            for reg in s.execute(select(Registration).where(
                    Registration.drive_id == did,
                    Registration.current_round == order,
                    Registration.status != "rejected")).scalars().all():
                if reg.candidate_id not in existing:
                    s.add(RoundScore(id=new_id(), drive_id=did, round_order=order,
                                     candidate_id=reg.candidate_id))
            s.flush()
        return {"deleted_round": order, "rounds": self.workflow(s, did)}

    # ---------- round marks sheet (written auto + panel-scored rounds) ----------
    def _score_out(self, r: RoundScore, names: dict | None = None) -> dict:
        pct = round(r.marks * 100.0 / r.max_marks, 1) if r.max_marks else 0.0
        info = (names or {}).get(r.candidate_id) or {}
        return {"candidate_id": r.candidate_id, "marks": r.marks, "max_marks": r.max_marks,
                "percentage": pct, "remarks": r.remarks, "cleared": r.cleared,
                "referred": r.referred, "entered_by": r.entered_by,
                "candidate_name": info.get("name"), "candidate_email": info.get("email"),
                "candidate_roll": info.get("roll"),
                "candidate_phone": info.get("phone"),
                "candidate_student_id": info.get("student_id"),
                "coding_attempted": r.coding_attempted, "coding_correct": r.coding_correct,
                "coding_total": r.coding_total}

    # ---------- event-driven intake (applications, auto-graded results) ----------
    def ensure_registration(self, s: Session, did: str, candidate_id: str) -> None:
        """Idempotently register an applicant so they appear in the Candidates tab
        and get seeded into Round 1. Called from the candidate.registered event."""
        if not (did and candidate_id):
            return
        if s.get(Drive, did) is None:
            return  # event for a drive this instance doesn't own; ignore
        reg = s.execute(select(Registration).where(
            Registration.drive_id == did,
            Registration.candidate_id == candidate_id)).scalar_one_or_none()
        if reg is None:
            s.add(Registration(id=new_id(), drive_id=did, candidate_id=candidate_id,
                               status="applied", current_round=0, eligible="unknown"))
        # Seed the Round 1 marks row so the written-test sheet lists them at once.
        rs = s.execute(select(RoundScore).where(
            RoundScore.drive_id == did, RoundScore.round_order == 1,
            RoundScore.candidate_id == candidate_id)).scalar_one_or_none()
        if rs is None:
            s.add(RoundScore(id=new_id(), drive_id=did, round_order=1,
                             candidate_id=candidate_id))
        s.flush()

    def record_evaluation(self, s: Session, did: str, candidate_id: str, *,
                          total: float, max_score: float, percentage: float,
                          passed: bool, needs_review: bool,
                          total_questions: int = 0, correct_count: int = 0,
                          attempted_count: int = 0, coding_total: int = 0,
                          coding_attempted: int = 0, coding_correct: int = 0,
                          round_id: str | None = None) -> None:
        """Post an auto-graded written-test result into the marks sheet of the
        round the exam belongs to (each written round has its own paper).

        Marks column = number of correct answers, Out-of = questions attempted.
        Values refresh on every (re-)grade; `cleared` defaults from pass/fail but
        never overwrites an admin's manual clear/reject decision."""
        if s.get(Drive, did) is None:
            return
        # Resolve which round this exam belongs to; fall back to Round 1 for
        # legacy papers with no round_id.
        order = 1
        if round_id:
            rnd = s.get(Round, round_id)
            if rnd and rnd.drive_id == did:
                order = rnd.order
        self.ensure_registration(s, did, candidate_id)
        rs = s.execute(select(RoundScore).where(
            RoundScore.drive_id == did, RoundScore.round_order == order,
            RoundScore.candidate_id == candidate_id)).scalar_one_or_none()
        if rs is None:
            rs = RoundScore(id=new_id(), drive_id=did, round_order=order,
                            candidate_id=candidate_id)
            s.add(rs)
        rs.marks = float(correct_count)          # Marks = correct answers
        rs.max_marks = float(attempted_count)    # Out of = questions attempted
        rs.coding_attempted = int(coding_attempted)
        rs.coding_correct = int(coding_correct)
        rs.coding_total = int(coding_total)
        note = f"{correct_count} correct of {total_questions} questions ({percentage:.0f}%)"
        if needs_review:
            note += " · needs review"
        rs.remarks = note
        # Default `cleared` from the pass result, but never overwrite an admin's
        # manual decision — once a human touches the row, entered_by is their id.
        if rs.entered_by in (None, "auto-evaluation"):
            rs.cleared = bool(passed)
        rs.entered_by = "auto-evaluation"
        rs.updated_at = _utcnow()
        s.flush()

    def round_scores(self, s: Session, did: str, order: int) -> dict:
        self.get(s, did)
        # Round 1 is seeded from the applicants; later rounds are seeded when the
        # previous round is published (only cleared candidates advance).
        if order == 1:
            existing = {r.candidate_id for r in s.execute(
                select(RoundScore).where(RoundScore.drive_id == did, RoundScore.round_order == 1)
            ).scalars().all()}
            for reg in s.execute(select(Registration).where(Registration.drive_id == did)).scalars().all():
                if reg.candidate_id not in existing:
                    s.add(RoundScore(id=new_id(), drive_id=did, round_order=1, candidate_id=reg.candidate_id))
            s.flush()
        rows = s.execute(
            select(RoundScore).where(RoundScore.drive_id == did, RoundScore.round_order == order)
            .order_by(RoundScore.marks.desc())
        ).scalars().all()
        wf = self.workflow(s, did)
        stage = next((w for w in wf if w["order"] == order), None)
        names = _resolve_names([r.candidate_id for r in rows])
        return {"drive_id": did, "round_order": order,
                "round": stage or {"order": order, "type": "round", "label": f"Round {order}"},
                "scores": [self._score_out(r, names) for r in rows]}

    def set_round_score(self, s: Session, did: str, order: int, candidate_id: str,
                        *, marks=None, max_marks=None, remarks=None, cleared=None,
                        entered_by=None) -> dict:
        row = s.execute(
            select(RoundScore).where(
                RoundScore.drive_id == did, RoundScore.round_order == order,
                RoundScore.candidate_id == candidate_id)
        ).scalar_one_or_none()
        if row is None:
            row = RoundScore(id=new_id(), drive_id=did, round_order=order, candidate_id=candidate_id)
            s.add(row)
        if marks is not None:
            row.marks = float(marks)
        if max_marks is not None:
            row.max_marks = float(max_marks)
        if remarks is not None:
            row.remarks = remarks
        if cleared is not None:
            row.cleared = bool(cleared)
        row.entered_by = entered_by
        row.updated_at = _utcnow()
        s.flush()
        return self._score_out(row)

    def add_round_candidate(self, s: Session, did: str, order: int, candidate_id: str,
                            entered_by: str | None) -> dict:
        """Admin adds a referred candidate directly into a round."""
        row = s.execute(
            select(RoundScore).where(
                RoundScore.drive_id == did, RoundScore.round_order == order,
                RoundScore.candidate_id == candidate_id)
        ).scalar_one_or_none()
        if row is None:
            row = RoundScore(id=new_id(), drive_id=did, round_order=order,
                             candidate_id=candidate_id, referred=True, entered_by=entered_by)
            s.add(row)
            # ensure a registration exists so they flow through the funnel
            reg = s.execute(select(Registration).where(
                Registration.drive_id == did, Registration.candidate_id == candidate_id)).scalar_one_or_none()
            if reg is None:
                s.add(Registration(id=new_id(), drive_id=did, candidate_id=candidate_id,
                                   status="in_round", current_round=order - 1, eligible="yes"))
            s.flush()
        return self._score_out(row)

    def remove_round_candidate(self, s: Session, did: str, order: int, candidate_id: str) -> dict:
        # Delete this candidate's score for the round.
        row = s.execute(
            select(RoundScore).where(
                RoundScore.drive_id == did, RoundScore.round_order == order,
                RoundScore.candidate_id == candidate_id)
        ).scalar_one_or_none()
        if row:
            s.delete(row)
        # Round 1 is auto-seeded from the registrations, so deleting just the
        # score row would reappear on the next reload. Removing a student from
        # Round 1 therefore means removing them from the drive entirely: drop
        # the registration and all their round scores so the delete sticks.
        if order == 1:
            reg = s.execute(select(Registration).where(
                Registration.drive_id == did,
                Registration.candidate_id == candidate_id)).scalar_one_or_none()
            if reg:
                s.delete(reg)
            for rs in s.execute(select(RoundScore).where(
                    RoundScore.drive_id == did,
                    RoundScore.candidate_id == candidate_id)).scalars().all():
                s.delete(rs)
        s.flush()
        return {"candidate_id": candidate_id, "removed": True}

    def publish_round(self, s: Session, did: str, order: int) -> dict:
        """Advance cleared candidates to the next round; reject the rest for now.

        Returns a `notify` list the route fans out as events so each shortlisted
        (or selected) candidate gets an in-app message + email from the company."""
        drive = self.get(s, did)
        rows = s.execute(
            select(RoundScore).where(RoundScore.drive_id == did, RoundScore.round_order == order)
        ).scalars().all()
        wf = self.workflow(s, did)
        is_last = order >= len(wf)
        this_stage = next((w for w in wf if w["order"] == order), None)
        next_stage = next((w for w in wf if w["order"] == order + 1), None)
        this_label = (this_stage or {}).get("label") or f"Round {order}"
        next_label = (next_stage or {}).get("label") or f"Round {order + 1}"
        names = _resolve_names([r.candidate_id for r in rows])
        advanced = 0
        notify = []
        for r in rows:
            reg = s.execute(select(Registration).where(
                Registration.drive_id == did, Registration.candidate_id == r.candidate_id)).scalar_one_or_none()
            info = names.get(r.candidate_id) or {}
            base = {"candidate_id": r.candidate_id, "user_id": r.candidate_id,
                    "email": info.get("email"), "name": info.get("name"),
                    "drive_id": did, "drive_title": drive.title,
                    "company_name": drive.company_name,
                    "company_email": drive.contact_email,
                    "round_label": this_label}
            if r.cleared:
                advanced += 1
                if reg:
                    reg.current_round = order
                    reg.status = "selected" if is_last else "in_round"
                if not is_last:
                    nxt = s.execute(select(RoundScore).where(
                        RoundScore.drive_id == did, RoundScore.round_order == order + 1,
                        RoundScore.candidate_id == r.candidate_id)).scalar_one_or_none()
                    if nxt is None:
                        s.add(RoundScore(id=new_id(), drive_id=did, round_order=order + 1,
                                        candidate_id=r.candidate_id))
                notify.append({**base, "outcome": "selected" if is_last else "shortlisted",
                               "next_label": None if is_last else next_label})
            else:
                if reg:
                    reg.status = "rejected"
                # Non-cleared candidates are NOT notified — only selected/
                # shortlisted students receive the email + in-app message.
        s.flush()
        return {"drive_id": did, "round_order": order, "advanced": advanced,
                "final_round": is_last, "next_round": None if is_last else order + 1,
                "notify": notify}

    # ---------- extended post-selection workflow (req #3) ----------
    def set_joining_status(self, s: Session, did: str, candidate_id: str, status: str) -> dict:
        order = ["offer_accepted", "docs_verified", "joined", "declined"]
        if status not in order:
            raise BadRequest("Unknown joining status", code="bad_joining_status")
        reg = s.execute(
            select(Registration).where(
                Registration.drive_id == did, Registration.candidate_id == candidate_id)
        ).scalar_one_or_none()
        if not reg:
            raise NotFound("Registration not found", code="registration_not_found")
        reg.joining_status = status
        s.flush()
        return {"candidate_id": candidate_id, "joining_status": status}

    # ---------- eligibility evaluation ----------
    def _evaluate(self, s: Session, did: str, cand) -> bool:
        er = s.execute(
            select(EligibilityRule).where(EligibilityRule.drive_id == did)
        ).scalar_one_or_none()
        if not er:
            return True
        rule = er.rule or {}
        if rule.get("min_cgpa") is not None and (cand.cgpa or 0) < rule["min_cgpa"]:
            return False
        if rule.get("branches") and cand.branch not in rule["branches"]:
            return False
        if rule.get("max_backlogs") is not None and (cand.backlogs or 0) > rule["max_backlogs"]:
            return False
        if rule.get("min_lms_score") is not None and (cand.lms_score or 0) < rule["min_lms_score"]:
            return False
        return True

    # ---------- registration / shortlist / advance ----------
    def register(self, s: Session, did: str, data) -> dict:
        self.get(s, did)
        dup = s.execute(
            select(Registration).where(
                Registration.drive_id == did, Registration.candidate_id == data.candidate_id)
        ).scalar_one_or_none()
        if dup:
            raise Conflict("Already registered", code="already_registered")
        eligible = self._evaluate(s, did, data)
        reg = Registration(id=new_id(), drive_id=did, candidate_id=data.candidate_id,
                           eligible="yes" if eligible else "no")
        s.add(reg)
        s.flush()
        return {"id": reg.id, "candidate_id": reg.candidate_id, "eligible": reg.eligible,
                "status": reg.status}

    def shortlist(self, s: Session, did: str, candidate_ids: list[str]) -> dict:
        self.get(s, did)
        ids = [c for c in dict.fromkeys(candidate_ids) if c]
        # Batch-load the registrations in ONE query (was a SELECT per candidate).
        regs = {r.candidate_id: r for r in s.execute(
            select(Registration).where(
                Registration.drive_id == did, Registration.candidate_id.in_(ids))
        ).scalars().all()} if ids else {}
        updated = 0
        skipped = []
        for cid in ids:
            reg = regs.get(cid)
            if not reg or reg.eligible == "no":
                skipped.append(cid)
                continue
            reg.status = "shortlisted"
            reg.current_round = 1
            updated += 1
        s.flush()
        return {"shortlisted": updated, "skipped": skipped}

    def advance(self, s: Session, did: str, candidate_id: str) -> dict:
        self.get(s, did)
        reg = s.execute(
            select(Registration).where(
                Registration.drive_id == did, Registration.candidate_id == candidate_id)
        ).scalar_one_or_none()
        if not reg:
            raise NotFound("Registration not found", code="registration_not_found")
        total_rounds = len(self.rounds(s, did))
        if reg.current_round < total_rounds:
            reg.current_round += 1
            reg.status = "in_round"
        else:
            reg.status = "selected"
        s.flush()
        return {"candidate_id": candidate_id, "status": reg.status,
                "current_round": reg.current_round, "total_rounds": total_rounds}

    def registrations(self, s: Session, did: str) -> list[dict]:
        self.get(s, did)
        rows = s.execute(
            select(Registration).where(Registration.drive_id == did)
        ).scalars().all()
        names = _resolve_names([r.candidate_id for r in rows])
        # Each candidate's real performance: average % across their round marks,
        # so the console can rank by actual scores, not just pipeline stage.
        pcts: dict[str, list[float]] = {}
        for rs in s.execute(select(RoundScore).where(RoundScore.drive_id == did)).scalars().all():
            if rs.max_marks:
                pcts.setdefault(rs.candidate_id, []).append(rs.marks * 100.0 / rs.max_marks)
        scores = {cid: round(sum(v) / len(v), 1) for cid, v in pcts.items() if v}
        out = []
        for r in rows:
            info = names.get(r.candidate_id) or {}
            out.append({"candidate_id": r.candidate_id, "status": r.status,
                        "eligible": r.eligible, "current_round": r.current_round,
                        "score": scores.get(r.candidate_id),
                        "candidate_name": info.get("name"),
                        "candidate_email": info.get("email"),
                        "candidate_roll": info.get("roll")})
        return out

    def funnel(self, s: Session, did: str) -> dict:
        self.get(s, did)
        counts = dict(s.execute(
            select(Registration.status, func.count(Registration.id))
            .where(Registration.drive_id == did).group_by(Registration.status)
        ).all())
        total = s.execute(
            select(func.count(Registration.id)).where(Registration.drive_id == did)
        ).scalar_one()
        return {"drive_id": did, "total": total, "by_status": counts}

    # ---------- analytics + exports ----------
    def analytics(self, s: Session, did: str) -> dict:
        """Written-test (Round 1) analytics: attendance, pass rate, score
        distribution and coding-question stats for the admin dashboard."""
        self.get(s, did)
        total_registered = s.execute(
            select(func.count(Registration.id)).where(Registration.drive_id == did)
        ).scalar_one()
        reg_by_status = dict(s.execute(
            select(Registration.status, func.count(Registration.id))
            .where(Registration.drive_id == did).group_by(Registration.status)
        ).all())

        r1 = s.execute(select(RoundScore).where(
            RoundScore.drive_id == did, RoundScore.round_order == 1)).scalars().all()
        # "Attended" = the written test produced/holds a score for them.
        attended = [r for r in r1 if r.entered_by is not None]
        n_att = len(attended)
        n_cleared = len([r for r in r1 if r.cleared])

        buckets = [0, 0, 0, 0, 0]  # 0–20, 20–40, 40–60, 60–80, 80–100 (%)
        pct_sum = 0.0
        for r in attended:
            pct = (r.marks * 100.0 / r.max_marks) if r.max_marks else 0.0
            pct_sum += pct
            buckets[min(int(pct // 20), 4)] += 1

        coding = [r for r in attended if (r.coding_total or 0) > 0]
        total_cod_att = sum(r.coding_attempted or 0 for r in coding)
        total_cod_cor = sum(r.coding_correct or 0 for r in coding)
        return {
            "drive_id": did,
            "total_registered": total_registered,
            "registrations_by_status": reg_by_status,
            "written": {
                "attended": n_att,
                "cleared": n_cleared,
                "pass_rate": round(n_cleared * 100.0 / n_att, 1) if n_att else 0.0,
                "avg_percentage": round(pct_sum / n_att, 1) if n_att else 0.0,
                "score_distribution": [
                    {"band": "0–20%", "count": buckets[0]},
                    {"band": "20–40%", "count": buckets[1]},
                    {"band": "40–60%", "count": buckets[2]},
                    {"band": "60–80%", "count": buckets[3]},
                    {"band": "80–100%", "count": buckets[4]},
                ],
            },
            "coding": {
                "students_with_coding": len(coding),
                "students_attempted": len([r for r in coding if (r.coding_attempted or 0) > 0]),
                "total_questions": sum(r.coding_total or 0 for r in coding),
                "total_attempted": total_cod_att,
                "total_correct": total_cod_cor,
                "accuracy": round(total_cod_cor * 100.0 / total_cod_att, 1) if total_cod_att else 0.0,
            },
        }

    def export_round(self, s: Session, did: str, order: int,
                     cleared_only: bool = False) -> tuple[bytes, str]:
        """Build an .xlsx of a round's marks sheet (all attendees, or only the
        cleared ones) for sharing with college officials."""
        from lare_common.exports import to_xlsx
        data = self.round_scores(s, did, order)
        scores = data["scores"]
        if cleared_only:
            scores = [x for x in scores if x.get("cleared")]
        headers = ["Name", "Email", "Roll No", "Correct", "Attempted", "Percentage",
                   "Coding Correct", "Coding Attempted", "Coding Total", "Remarks", "Result"]
        rows = []
        for x in scores:
            rows.append([
                x.get("candidate_name") or "",
                x.get("candidate_email") or "",
                x.get("candidate_roll") or "",
                x.get("marks") or 0,
                x.get("max_marks") or 0,
                x.get("percentage") or 0,
                x.get("coding_correct") if x.get("coding_correct") is not None else "",
                x.get("coding_attempted") if x.get("coding_attempted") is not None else "",
                x.get("coding_total") if x.get("coding_total") is not None else "",
                x.get("remarks") or "",
                "Cleared" if x.get("cleared") else "Not cleared",
            ])
        kind = "cleared" if cleared_only else "attendees"
        blob = to_xlsx(headers, rows, sheet=kind.capitalize())
        return blob, f"drive-{kind}-round{order}.xlsx"

    def set_ppo(self, s: Session, did: str, data) -> PpoConfig:
        self.get(s, did)
        cfg = s.get(PpoConfig, did)
        if cfg is None:
            cfg = PpoConfig(drive_id=did)
            s.add(cfg)
        cfg.eligibility = data.eligibility
        cfg.stages = data.stages
        cfg.conversion_criteria = data.conversion_criteria
        s.flush()
        return cfg

    # ---------- search (req #27) ----------
    def search(self, s: Session, q: str, limit: int = 10) -> list[dict]:
        like = f"%{q.lower()}%"
        rows = s.execute(
            select(Drive).where(
                func.lower(Drive.title).like(like) | func.lower(Drive.company_name).like(like)
            ).limit(limit)
        ).scalars().all()
        return [{"type": "drive", "id": d.id, "title": d.title,
                 "subtitle": d.company_name, "status": d.status} for d in rows]

    # ---------- dynamic form builder (req #21) ----------
    def set_form(self, s: Session, did: str, fields: list) -> dict:
        self.get(s, did)
        form = s.get(ApplicationForm, did)
        if form is None:
            form = ApplicationForm(drive_id=did, fields=fields)
            s.add(form)
        else:
            form.fields = fields
        s.flush()
        return {"drive_id": did, "fields": form.fields}

    def get_form(self, s: Session, did: str) -> dict:
        form = s.get(ApplicationForm, did)
        return {"drive_id": did, "fields": form.fields if form else []}

    def submit_form(self, s: Session, did: str, candidate_id: str, answers: dict) -> dict:
        form = s.get(ApplicationForm, did)
        # Validate required fields declared in the schema.
        missing = [f["key"] for f in (form.fields if form else [])
                   if f.get("required") and not answers.get(f["key"])]
        if missing:
            raise BadRequest(f"Missing required fields: {', '.join(missing)}",
                             code="form_incomplete")
        sub = s.execute(
            select(FormSubmission).where(
                FormSubmission.drive_id == did, FormSubmission.candidate_id == candidate_id)
        ).scalar_one_or_none()
        if sub is None:
            sub = FormSubmission(id=new_id(), drive_id=did, candidate_id=candidate_id, answers=answers)
            s.add(sub)
        else:
            sub.answers = answers
        s.flush()
        return {"id": sub.id, "drive_id": did, "candidate_id": candidate_id, "submitted": True}

    def form_submissions(self, s: Session, did: str) -> list[dict]:
        rows = s.execute(
            select(FormSubmission).where(FormSubmission.drive_id == did)
        ).scalars().all()
        return [{"candidate_id": r.candidate_id, "answers": r.answers,
                 "submitted_at": r.submitted_at.isoformat()} for r in rows]

    # ---------- recruitment calendar (req #16) ----------
    def set_schedule(self, s: Session, did: str, schedule: dict) -> dict:
        d = self.get(s, did)
        d.schedule = {**(d.schedule or {}), **schedule}
        s.flush()
        return d.schedule

    def calendar(self, s: Session, did: str | None = None) -> list[dict]:
        """Flatten drive schedule dates into calendar events. When did is None,
        returns events across all drives."""
        q = select(Drive)
        if did:
            q = q.where(Drive.id == did)
        events: list[dict] = []
        for d in s.execute(q).scalars().all():
            sched = d.schedule or {}
            for key, label in (("registration_deadline", "Registration closes"),
                               ("exam_date", "Assessment"),
                               ("interview_date", "Interviews"),
                               ("joining_date", "Joining")):
                if sched.get(key):
                    events.append({"date": sched[key], "type": key, "label": label,
                                   "drive_id": d.id, "title": f"{d.title} — {label}"})
        return sorted(events, key=lambda e: e["date"])

    # ---------- seat allocation (req #18) ----------
    def allocate_seats(self, s: Session, did: str, labs: list[dict]) -> dict:
        """Round-robin allocate registered candidates to lab/system/seat.
        labs: [{name, systems}] where systems is the machine count per lab."""
        self.get(s, did)
        if not labs:
            raise BadRequest("At least one lab with capacity is required", code="no_labs")
        regs = s.execute(
            select(Registration).where(Registration.drive_id == did)
            .order_by(Registration.candidate_id)
        ).scalars().all()
        # clear prior allocations
        for a in s.execute(select(SeatAllocation).where(SeatAllocation.drive_id == did)).scalars().all():
            s.delete(a)
        s.flush()
        # build a flat seat list: (lab, system_no, seat_no)
        seats = []
        for lab in labs:
            for n in range(1, int(lab.get("systems", 0)) + 1):
                seats.append((lab["name"], n, f"{lab['name']}-{n:02d}"))
        if len(regs) > len(seats):
            raise Conflict(f"Not enough seats: {len(regs)} candidates, {len(seats)} seats",
                           code="insufficient_seats")
        allocated = []
        for reg, (lab, sysno, seat) in zip(regs, seats):
            s.add(SeatAllocation(id=new_id(), drive_id=did, candidate_id=reg.candidate_id,
                                 lab=lab, system_no=sysno, seat_no=seat))
            allocated.append({"candidate_id": reg.candidate_id, "lab": lab,
                              "system_no": sysno, "seat_no": seat})
        s.flush()
        return {"drive_id": did, "allocated": len(allocated), "seats": len(seats),
                "allocations": allocated}

    def seat_map(self, s: Session, did: str) -> list[dict]:
        rows = s.execute(
            select(SeatAllocation).where(SeatAllocation.drive_id == did)
            .order_by(SeatAllocation.lab, SeatAllocation.system_no)
        ).scalars().all()
        return [{"candidate_id": a.candidate_id, "lab": a.lab,
                 "system_no": a.system_no, "seat_no": a.seat_no} for a in rows]

    # ---------- hall ticket (req #17) ----------
    def hall_ticket(self, s: Session, did: str, candidate_id: str) -> tuple[bytes, str]:
        from lare_common.exports import to_pdf
        from lare_common.security import hash_token
        d = self.get(s, did)
        # Deterministic verify code from drive+candidate (no extra storage needed).
        code = hash_token(f"{did}:{candidate_id}")[:10].upper()
        payload = f"HALLTICKET|{did}|{candidate_id}|{code}"
        lines = [
            "", f"Drive: {d.title}",
            f"Company: {d.company_name or '-'}",
            f"Candidate ID: {candidate_id}",
            f"Venue: {d.venue or 'To be announced'}",
            f"Reporting time: {d.reporting_time or 'To be announced'}",
            "",
            "Instructions:",
            "  - Carry a government-issued photo ID.",
            "  - Report 30 minutes before the reporting time.",
            "  - Present this hall ticket (QR / code) at entry.",
            "",
            f"Verify code: {code}",
            f"QR payload: {payload}",
        ]
        return to_pdf(f"Hall Ticket — {d.title}", lines), f"hallticket-{did}-{candidate_id}.pdf"

    # ---------- serializers ----------
    @staticmethod
    def out(d: Drive) -> dict:
        return {"id": d.id, "company_name": d.company_name, "title": d.title,
                "status": d.status, "reporting_time": d.reporting_time, "venue": d.venue,
                "contact_email": d.contact_email}

    @staticmethod
    def role_out(r: DriveRole) -> dict:
        return {"id": r.id, "title": r.title, "ctc": r.ctc, "positions": r.positions,
                "skills": r.skills or []}

    @staticmethod
    def round_out(r: Round) -> dict:
        return {"id": r.id, "order": r.order, "type": r.type, "service_ref": r.service_ref}

    def candidate_round(self, s: Session, did: str, user_id: str) -> dict:
        """A candidate's progress in a drive: their eligible round + the pipeline.
        The learning surface reveals only the round they've qualified for."""
        drive = self.get(s, did)
        reg = s.execute(
            select(Registration).where(Registration.drive_id == did,
                                        Registration.candidate_id == user_id)
        ).scalar_one_or_none()
        current = reg.current_round if reg else 0
        # A candidate can enter round R once they're marked CLEARED in round R-1
        # (round 1 is open to everyone registered). Basing this on the cleared flag
        # — not current_round — means marking a candidate cleared unlocks the next
        # round for them immediately, without waiting for the round to be published.
        cleared = {rs.round_order: rs.cleared for rs in s.execute(
            select(RoundScore).where(RoundScore.drive_id == did,
                                     RoundScore.candidate_id == user_id)).scalars().all()}
        eligible, r = 1, 1
        while cleared.get(r):
            eligible, r = r + 1, r + 1
        return {
            "current_round": current,
            "eligible_round": eligible,
            "rounds": [{"id": rd.id, "order": rd.order, "type": rd.type, "label": rd.label}
                       for rd in sorted(drive.rounds or [], key=lambda x: x.order)],
        }

    # ---------- Drive Access Gate ----------
    def _gen_drive_code(self, s: Session, drive_title: str) -> str:
        base = "".join(ch for ch in (drive_title or "DRIVE").upper() if ch.isalnum())[:5] or "DRIVE"
        for _ in range(20):
            suffix = "".join(secrets.choice(_ACCESS_ALPHABET) for _ in range(4))
            code = f"{base}-{suffix}"
            if not s.execute(select(DriveAccessCode.id).where(DriveAccessCode.code == code)).first():
                return code
        raise Conflict("Could not generate a unique code", code="code_gen_failed")

    def create_access_code(self, s: Session, data, created_by: str | None) -> DriveAccessCode:
        drive = s.get(Drive, data.drive_id)
        if not drive:
            raise NotFound("Drive not found", code="drive_not_found")
        exp = None
        if data.expires_at:
            try:
                exp = datetime.fromisoformat(data.expires_at.replace("Z", "+00:00"))
            except ValueError as e:
                raise BadRequest("Invalid expires_at", code="bad_datetime") from e
        ac = DriveAccessCode(id=new_id(), code=self._gen_drive_code(s, drive.title),
                             drive_id=drive.id, label=data.label, expires_at=exp,
                             created_by=created_by)
        s.add(ac)
        s.flush()
        return ac

    def list_access_codes(self, s: Session, drive_id: str | None) -> list[DriveAccessCode]:
        stmt = select(DriveAccessCode).order_by(DriveAccessCode.created_at.desc())
        if drive_id:
            stmt = stmt.where(DriveAccessCode.drive_id == drive_id)
        return list(s.execute(stmt).scalars().all())

    def set_access_status(self, s: Session, code_id: str, status: str) -> DriveAccessCode:
        ac = s.get(DriveAccessCode, code_id)
        if not ac:
            raise NotFound("Access code not found", code="code_not_found")
        ac.status = status
        s.flush()
        return ac

    def regenerate_access_code(self, s: Session, code_id: str) -> DriveAccessCode:
        ac = s.get(DriveAccessCode, code_id)
        if not ac:
            raise NotFound("Access code not found", code="code_not_found")
        drive = s.get(Drive, ac.drive_id)
        ac.code = self._gen_drive_code(s, drive.title if drive else "DRIVE")
        s.flush()
        return ac

    def validate_access(self, s: Session, code: str, user_id: str) -> dict:
        ac = s.execute(
            select(DriveAccessCode).where(DriveAccessCode.code == code.strip().upper())
        ).scalar_one_or_none()
        if not ac or ac.status != "active":
            raise NotFound("Invalid or inactive access code", code="invalid_access_code")
        if ac.expires_at and _as_utc(ac.expires_at) < datetime.now(tz=timezone.utc):
            raise BadRequest("This access code has expired", code="access_code_expired")
        drive = s.get(Drive, ac.drive_id)
        for old in s.execute(select(DriveAccessSession).where(DriveAccessSession.user_id == user_id)).scalars().all():
            s.delete(old)
        sess = DriveAccessSession(id=new_id(), user_id=user_id, drive_id=ac.drive_id,
                                  code_id=ac.id,
                                  expires_at=datetime.now(tz=timezone.utc) + timedelta(hours=DRIVE_ACCESS_HOURS))
        s.add(sess)
        ac.used_count += 1
        s.flush()
        return {"drive_id": ac.drive_id, "drive_title": drive.title if drive else None,
                "company_name": drive.company_name if drive else None,
                "label": ac.label, "expires_at": sess.expires_at.isoformat()}

    def clear_access_session(self, s: Session, user_id: str) -> None:
        for sess in s.execute(select(DriveAccessSession).where(DriveAccessSession.user_id == user_id)).scalars().all():
            s.delete(sess)

    @staticmethod
    def access_code_out(ac: DriveAccessCode) -> dict:
        return {"id": ac.id, "code": ac.code, "drive_id": ac.drive_id, "label": ac.label,
                "status": ac.status, "used_count": ac.used_count,
                "expires_at": ac.expires_at.isoformat() if ac.expires_at else None,
                "created_at": ac.created_at.isoformat()}
