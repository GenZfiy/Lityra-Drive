"""HTTP layer for the Candidate Service."""
from __future__ import annotations

from flask import Blueprint, current_app, request
from pydantic import ValidationError

from lare_common.auth_context import current_identity, require_roles
from lare_common.errors import BadRequest
from lare_common.responses import created, ok
from lare_common.service_client import ServiceClient
from lare_common.file_client import FileClient

from .schemas import (
    ApplyIn, AttendIn, EducationIn, ProfileIn, ProjectIn, ResumeIn, ResumeAttendIn,
)
from .service import CandidateService

bp = Blueprint("candidate", __name__)

RECRUITER = ("super_admin", "company_admin", "recruiter")

# East-west clients: consented LMS->Drive projection + File service integration.
_CLIENT = ServiceClient("drive-candidate")
_FILES = FileClient("drive-candidate")


def _svc() -> CandidateService:
    return current_app.extensions["svc"]


def _db():
    return current_app.extensions["db"]


def _parse(model, payload):
    try:
        return model.model_validate(payload or {})
    except ValidationError as e:
        raise BadRequest("Validation failed", code="validation_error",
                         details=e.errors(include_url=False)) from e


@bp.get("/drive/v1/candidate/profile")
def get_profile():
    ident = current_identity()
    with _db().session() as s:
        cand = _svc().get_or_create(s, ident.user_id)
        return ok(_svc().profile_out(s, cand))


@bp.put("/drive/v1/candidate/profile")
def update_profile():
    ident = current_identity()
    data = _parse(ProfileIn, request.get_json(silent=True))
    with _db().session() as s:
        cand = _svc().update_profile(s, ident.user_id, data)
        return ok(_svc().profile_out(s, cand))


@bp.post("/drive/v1/candidate/resume")
def set_resume():
    ident = current_identity()
    data = _parse(ResumeIn, request.get_json(silent=True))
    # Validate the file exists, is 'ready', and cleared AV scan via the File
    # service. If the File service is unreachable (dev), degrade to accepting.
    meta = _FILES.meta(data.resume_file_id, requester_id=ident.user_id)
    if meta is not None:
        if meta.get("purpose") != "resume":
            raise BadRequest("File is not a resume upload", code="wrong_purpose")
        if meta.get("status") != "ready":
            raise BadRequest("Resume upload not completed", code="file_not_ready")
        if meta.get("scan_result") not in (None, "clean", "skipped"):
            raise BadRequest("Resume failed the malware scan", code="file_unsafe")
    with _db().session() as s:
        cand = _svc().set_resume(s, ident.user_id, data.resume_file_id)
        return ok({"resume_file_id": cand.resume_file_id,
                   "completeness": _svc()._completeness(cand)})


def _ai_complete(prompt_key, variables, fallback, user_id):
    """Call the governed AI Orchestration egress; degrade to fallback."""
    try:
        resp = _CLIENT.post("platform-ai", "/ai/v1/complete", {
            "prompt_key": prompt_key, "want_json": True, "purpose": "resume",
            "variables": variables, "json_fallback": fallback},
            roles=["recruiter"], user_id=user_id)
        return ((resp or {}).get("data") or {}).get("output") or fallback
    except Exception:  # noqa: BLE001
        return fallback


@bp.post("/drive/v1/candidate/parse-resume")
def parse_resume():
    """Resume parsing (req #5): extract skills/CGPA/projects/certs via AI and
    apply to the profile. Feature-flag gated; degrades gracefully offline."""
    from lare_common.platform import feature_enabled
    ident = current_identity()
    if not feature_enabled("resume_parsing", ident.tenant_id):
        raise BadRequest("Resume parsing is disabled", code="feature_disabled")
    body = request.get_json(silent=True) or {}
    text = (body.get("resume_text") or "").strip()
    if not text:
        raise BadRequest("resume_text is required", code="resume_text_required")
    fallback = {"skills": [], "cgpa": None, "education": [], "projects": [], "certifications": []}
    parsed = _ai_complete("resume_parse", {"resume_text": text[:8000]}, fallback, ident.user_id)
    with _db().session() as s:
        cand = _svc().apply_parsed(s, ident.user_id, parsed)
        return ok({"parsed": parsed, "profile": _svc().profile_out(s, cand)})


@bp.post("/drive/v1/candidate/<cand_user_id>/rank")
@require_roles(*RECRUITER)
def rank_candidate(cand_user_id):
    """AI resume ranking (req #6): score a candidate against job requirements."""
    ident = current_identity()
    body = request.get_json(silent=True) or {}
    requirements = body.get("requirements") or {}
    with _db().session() as s:
        cand = _svc().get_or_create(s, cand_user_id)
        profile = _svc().profile_out(s, cand)
    fallback = {"score": 0, "matched_skills": [], "missing_skills": [], "summary": "AI ranking unavailable."}
    ranking = _ai_complete("resume_rank",
                           {"requirements": requirements, "profile": profile},
                           fallback, ident.user_id)
    return ok({"candidate_id": cand_user_id, "ranking": ranking})


@bp.get("/drive/v1/candidates/search")
@require_roles(*RECRUITER)
def search_candidates():
    q = request.args.get("q", "").strip()
    with _db().session() as s:
        return ok(_svc().search(s, q) if q else [])


@bp.post("/drive/v1/candidate/photo")
def set_photo():
    ident = current_identity()
    body = request.get_json(silent=True) or {}
    file_id = body.get("photo_file_id")
    if not file_id:
        raise BadRequest("photo_file_id is required", code="photo_file_id_required")
    meta = _FILES.meta(file_id, requester_id=ident.user_id)
    if meta is not None and meta.get("purpose") != "avatar":
        raise BadRequest("File is not a photo upload", code="wrong_purpose")
    with _db().session() as s:
        cand = _svc().set_photo(s, ident.user_id, file_id)
        return ok({"photo_file_id": cand.photo_file_id})


# LARE Drive is a standalone application — no LMS coupling. Candidate profiles
# are built here (manual entry / résumé parsing), never imported from the LMS.


@bp.post("/drive/v1/candidate/education")
def add_education():
    ident = current_identity()
    data = _parse(EducationIn, request.get_json(silent=True))
    with _db().session() as s:
        e = _svc().add_education(s, ident.user_id, data)
        return created({"id": e.id, "degree": e.degree})


@bp.post("/drive/v1/candidate/projects")
def add_project():
    ident = current_identity()
    data = _parse(ProjectIn, request.get_json(silent=True))
    with _db().session() as s:
        p = _svc().add_project(s, ident.user_id, data)
        return created({"id": p.id, "title": p.title})


@bp.get("/drive/v1/candidates/resolve")
@require_roles(*RECRUITER)
def resolve_candidates():
    # Batch identity lookup for the recruiter UI (name/email/roll from user_ids).
    ids = [i for i in request.args.get("ids", "").split(",") if i]
    with _db().session() as s:
        return ok(_svc().resolve(s, ids))


@bp.post("/drive/v1/attend")
def attend():
    # Public (no login): create a pending record. Auth sends an email OTP; no
    # session is issued until the user proves control of the registered address.
    data = _parse(AttendIn, request.get_json(silent=True))
    with _db().session() as s:
        out, _user_id, drive = _svc().attend(s, data)
    _svc().send_registration_otp(data.email)
    out["drive"] = {"id": drive.get("id"), "title": drive.get("title"),
                    "company_name": drive.get("company_name")}
    return created(out)


@bp.post("/drive/v1/attend/resume")
def attend_resume():
    # Public request, but possession of the Student ID alone is insufficient.
    data = _parse(ResumeAttendIn, request.get_json(silent=True))
    with _db().session() as s:
        _svc().request_resume_otp(s, data.student_id, str(data.email))
    # Uniform response: do not reveal whether the ID and email matched.
    return ok({"sent": True})


@bp.post("/drive/v1/attend/complete")
def complete_attend():
    ident = current_identity()
    with _db().session() as s:
        drive = _svc().complete_attend(s, ident.user_id, ident.product or "")
    bus = current_app.extensions.get("bus")
    if bus and drive:
        bus.publish("candidate.registered", {
            "candidate_id": ident.user_id, "drive_id": drive["id"],
            "drive_title": drive.get("title"), "user_id": ident.user_id})
    return ok({"registered": True})


@bp.post("/drive/v1/candidate/apply")
def apply():
    ident = current_identity()
    data = _parse(ApplyIn, request.get_json(silent=True))
    with _db().session() as s:
        a = _svc().apply(s, ident.user_id, data)
        out = {"id": a.id, "drive_id": a.drive_id, "status": a.status}
    # Workflow automation (req #29): emit the domain event → Notification/Analytics/Audit.
    bus = current_app.extensions.get("bus")
    if bus:
        bus.publish("candidate.registered", {
            "candidate_id": ident.user_id, "drive_id": out["drive_id"],
            "drive_title": data.drive_id, "user_id": ident.user_id})
    return created(out)


@bp.get("/drive/v1/candidate/applications")
def my_applications():
    ident = current_identity()
    with _db().session() as s:
        return ok(_svc().applications(s, ident.user_id))


# Recruiter-facing candidate view (scoped to applied drives in a later join).
@bp.get("/drive/v1/candidates/<cid>")
@require_roles(*RECRUITER)
def recruiter_view(cid):
    with _db().session() as s:
        cand = _svc().get_by_id(s, cid)
        return ok(_svc().profile_out(s, cand))
