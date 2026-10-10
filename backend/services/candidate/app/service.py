"""Candidate business logic: profile, portfolio, résumé parsing, applications.

    Lityra Hire is a standalone application — candidate data is created here and never
imported from the LMS."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from lare_common.errors import BadRequest, Conflict, NotFound
from lare_common.security import new_id
from lare_common.service_client import ServiceClient

from .models import Application, Candidate, Education, Project, Skill

_COMPLETE_FIELDS = ("full_name", "email", "phone", "branch", "cgpa", "resume_file_id")

# East-west: Auth mints the passwordless student identity; Drive supplies the
# active drive to attend. Roles let the drive-list guard accept the call.
_AUTH = ServiceClient("drive-candidate", default_roles=["student"], timeout=10)
_DRIVE = ServiceClient("drive-candidate", default_roles=["company_admin"], timeout=10)


class CandidateService:
    # ---------- public "Attend Drive" registration ----------
    def _active_drive(self) -> dict:
        """The single currently-open drive students attend. If several are open,
        the most recently created one wins; if none, registration is closed."""
        resp = _DRIVE.get("drive-core", "/drive/v1/drives?status=open&limit=50")
        drives = (resp or {}).get("data") or []
        if not drives:
            raise Conflict("No drive is open for registration right now.",
                           code="no_active_drive")
        return drives[0]

    def _next_student_id(self, s: Session) -> str:
        """Sequential, readable Student ID: LITYRA-<year>-0001."""
        year = datetime.now(tz=timezone.utc).year
        prefix = f"LITYRA-{year}-"
        n = s.execute(select(func.count(Candidate.id)).where(
            Candidate.student_id.like(prefix + "%"))).scalar() or 0
        # Retry a few times in case of a race on the count.
        for i in range(1, 10):
            sid = f"{prefix}{n + i:04d}"
            if s.execute(select(Candidate.id).where(
                    Candidate.student_id == sid)).scalar_one_or_none() is None:
                return sid
        raise Conflict("Could not allocate a Student ID; please retry.",
                       code="student_id_alloc")

    def attend(self, s: Session, data) -> dict:
        """Create a pending Hire identity; no session is issued before email OTP."""
        drive = self._active_drive()
        full_name = f"{data.first_name} {data.last_name}".strip()
        if data.phone:
            dup = s.execute(select(Candidate).where(Candidate.phone == data.phone)).scalar_one_or_none()
            if dup:
                raise Conflict("This phone number is already registered.", code="phone_taken")
        # Auth refuses to reuse an existing account and does not issue tokens.
        ident = _AUTH.post("auth", "/auth/v1/internal/drive-user",
                           {"email": data.email, "full_name": full_name})
        ident = (ident or {}).get("data") or {}
        user_id = ident.get("user_id")
        if not user_id:
            raise BadRequest("Could not create your registration identity.",
                             code="identity_failed")
        # Store an unverified candidate record. No login token is released until
        # the user redeems the OTP delivered to this address.
        cand = Candidate(id=new_id(), user_id=user_id)
        s.add(cand)
        cand.first_name, cand.last_name = data.first_name, data.last_name
        cand.full_name, cand.email = full_name, data.email
        cand.roll_number = data.roll_number
        if getattr(data, "phone", None):
            cand.phone = data.phone
        if not cand.student_id:
            cand.student_id = self._next_student_id(s)
        s.flush()
        return {
            "student_id": cand.student_id,
            "full_name": full_name, "email": data.email,
            "roll_number": cand.roll_number,
            "drive": {"id": drive.get("id"), "title": drive.get("title"),
                      "company_name": drive.get("company_name")},
        }, user_id, drive

    @staticmethod
    def send_registration_otp(email: str) -> None:
        _AUTH.post("auth", "/auth/v1/otp/request",
                   {"email": email, "product": "hire"})

    def request_resume_otp(self, s: Session, student_id: str, email: str) -> None:
        """Send an OTP only when both the Student ID and registered email match."""
        cand = s.execute(select(Candidate).where(
            Candidate.student_id == student_id.strip().upper())).scalar_one_or_none()
        if cand and cand.email and cand.email.lower() == email.strip().lower():
            _AUTH.post("auth", "/auth/v1/otp/request",
                       {"email": cand.email, "product": "hire"})

    def complete_attend(self, s: Session, user_id: str, product: str) -> dict | None:
        """Confirm a newly registered candidate after email OTP login."""
        if product != "hire":
            raise Conflict("Sign in to Lityra Hire to complete this registration.",
                           code="wrong_product")
        cand = s.execute(select(Candidate).where(
            Candidate.user_id == user_id)).scalar_one_or_none()
        if not cand or not cand.student_id:
            raise NotFound("Registration not found for this account.", code="registration_not_found")
        try:
            drive = self._active_drive()
        except Conflict:
            drive = None
        return drive
    def get_or_create(self, s: Session, user_id: str) -> Candidate:
        cand = s.execute(
            select(Candidate).where(Candidate.user_id == user_id)
        ).scalar_one_or_none()
        if cand is None:
            cand = Candidate(id=new_id(), user_id=user_id)
            s.add(cand)
            s.flush()
        return cand

    def resolve(self, s: Session, user_ids: list[str]) -> dict:
        """Batch user_id -> {full_name, email, roll_number} for the recruiter UI,
        so drive marks sheets show real people instead of UUIDs."""
        ids = [i for i in dict.fromkeys(user_ids) if i]
        if not ids:
            return {}
        rows = s.execute(select(Candidate).where(Candidate.user_id.in_(ids))).scalars().all()
        out = {}
        for c in rows:
            name = c.full_name or (f"{c.first_name or ''} {c.last_name or ''}".strip() or None)
            out[c.user_id] = {"full_name": name, "email": c.email,
                              "roll_number": c.roll_number,
                              "phone": c.phone, "student_id": c.student_id}
        return out

    def get_by_id(self, s: Session, cid: str) -> Candidate:
        cand = s.get(Candidate, cid)
        if not cand:
            raise NotFound("Candidate not found", code="candidate_not_found")
        return cand

    def update_profile(self, s: Session, user_id: str, data) -> Candidate:
        cand = self.get_or_create(s, user_id)
        for f in ("full_name", "email", "phone", "branch", "cgpa"):
            v = getattr(data, f)
            if v is not None:
                setattr(cand, f, v)
        s.flush()
        return cand

    def set_resume(self, s: Session, user_id: str, resume_file_id: str) -> Candidate:
        cand = self.get_or_create(s, user_id)
        cand.resume_file_id = resume_file_id
        s.flush()
        return cand

    def apply_parsed(self, s: Session, user_id: str, parsed: dict) -> Candidate:
        """Apply AI-parsed resume fields onto the candidate profile."""
        cand = self.get_or_create(s, user_id)
        if parsed.get("cgpa") is not None:
            try:
                cand.cgpa = float(parsed["cgpa"])
            except (TypeError, ValueError):
                pass
        skills = parsed.get("skills") or []
        if skills:
            for sk in s.execute(select(Skill).where(Skill.candidate_id == cand.id)).scalars().all():
                s.delete(sk)
            for name in skills:
                if name:
                    s.add(Skill(id=new_id(), candidate_id=cand.id, skill=str(name), level="parsed"))
        s.flush()
        return cand

    def search(self, s: Session, q: str, limit: int = 10) -> list[dict]:
        from sqlalchemy import func
        like = f"%{q.lower()}%"
        rows = s.execute(
            select(Candidate).where(
                func.lower(Candidate.full_name).like(like)
                | func.lower(Candidate.branch).like(like)
            ).limit(limit)
        ).scalars().all()
        return [{"type": "candidate", "id": c.user_id, "title": c.full_name or c.user_id,
                 "subtitle": c.branch or "", "status": c.college_id or ""} for c in rows]

    def set_photo(self, s: Session, user_id: str, photo_file_id: str) -> Candidate:
        cand = self.get_or_create(s, user_id)
        cand.photo_file_id = photo_file_id
        s.flush()
        return cand

    def add_education(self, s: Session, user_id: str, data) -> Education:
        cand = self.get_or_create(s, user_id)
        e = Education(id=new_id(), candidate_id=cand.id, degree=data.degree,
                      institution=data.institution, year=data.year, score=data.score)
        s.add(e)
        s.flush()
        return e

    def add_project(self, s: Session, user_id: str, data) -> Project:
        cand = self.get_or_create(s, user_id)
        p = Project(id=new_id(), candidate_id=cand.id, title=data.title,
                    description=data.description, repo_url=data.repo_url)
        s.add(p)
        s.flush()
        return p

    def apply(self, s: Session, user_id: str, data) -> Application:
        cand = self.get_or_create(s, user_id)
        dup = s.execute(
            select(Application).where(
                Application.candidate_id == cand.id, Application.drive_id == data.drive_id)
        ).scalar_one_or_none()
        if dup:
            raise Conflict("Already applied to this drive", code="already_applied")
        snapshot = {"branch": cand.branch, "cgpa": cand.cgpa,
                    "completeness": self._completeness(cand)}
        app = Application(id=new_id(), candidate_id=cand.id, drive_id=data.drive_id,
                          drive_role_id=data.drive_role_id, eligibility_snapshot=snapshot)
        s.add(app)
        s.flush()
        return app

    def applications(self, s: Session, user_id: str) -> list[dict]:
        cand = self.get_or_create(s, user_id)
        rows = s.execute(
            select(Application).where(Application.candidate_id == cand.id)
        ).scalars().all()
        return [{"id": a.id, "drive_id": a.drive_id, "drive_role_id": a.drive_role_id,
                 "status": a.status, "applied_at": a.applied_at.isoformat()} for a in rows]

    def _completeness(self, cand: Candidate) -> int:
        filled = sum(1 for f in _COMPLETE_FIELDS if getattr(cand, f) not in (None, ""))
        return round(filled * 100 / len(_COMPLETE_FIELDS))

    def profile_out(self, s: Session, cand: Candidate) -> dict:
        edu = s.execute(select(Education).where(Education.candidate_id == cand.id)).scalars().all()
        skills = s.execute(select(Skill).where(Skill.candidate_id == cand.id)).scalars().all()
        projects = s.execute(select(Project).where(Project.candidate_id == cand.id)).scalars().all()
        return {
            "id": cand.id, "user_id": cand.user_id, "learner_id": cand.learner_id,
            "full_name": cand.full_name, "email": cand.email, "phone": cand.phone,
            "branch": cand.branch, "cgpa": cand.cgpa, "college_id": cand.college_id,
            "resume_file_id": cand.resume_file_id, "photo_file_id": cand.photo_file_id,
            "completeness": self._completeness(cand),
            "education": [{"degree": e.degree, "institution": e.institution,
                           "year": e.year, "score": e.score} for e in edu],
            "skills": [{"skill": sk.skill, "level": sk.level} for sk in skills],
            "projects": [{"title": p.title, "description": p.description,
                          "repo_url": p.repo_url} for p in projects],
        }
