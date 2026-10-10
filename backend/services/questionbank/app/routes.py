"""HTTP layer for the Question Bank Service.

Answer keys are returned only to authors/managers (with_key), never on the
exam-facing paper generation path or to students."""
from __future__ import annotations

from flask import Blueprint, current_app, request
from pydantic import ValidationError

from lare_common.auth_context import require_roles
from lare_common.errors import BadRequest
from lare_common.responses import created, ok

from .schemas import BlueprintIn, BulkIn, GenerateIn, QuestionEdit, QuestionIn
from .service import QuestionBankService

bp = Blueprint("questionbank", __name__)

AUTHOR = ("super_admin", "company_admin", "trainer", "recruiter")


def _svc() -> QuestionBankService:
    return current_app.extensions["svc"]


def _db():
    return current_app.extensions["db"]


def _parse(model, payload):
    try:
        return model.model_validate(payload or {})
    except ValidationError as e:
        raise BadRequest("Validation failed", code="validation_error",
                         details=e.errors(include_url=False)) from e


def _identity():
    from lare_common.auth_context import current_identity
    return current_identity()


@bp.post("/drive/v1/questions/generate")
@require_roles(*AUTHOR)
def generate():
    # Draft exam-ready questions with the configured AI provider. Returns drafts
    # for the recruiter to review/edit — nothing is persisted until they save.
    data = _parse(GenerateIn, request.get_json(silent=True))
    return ok(_svc().generate(data))


@bp.post("/drive/v1/questions")
@require_roles(*AUTHOR)
def create():
    ident = _identity()
    data = _parse(QuestionIn, request.get_json(silent=True))
    with _db().session() as s:
        q = _svc().create(s, data, ident.user_id)
        return created(_svc().out(q, with_key=True))


@bp.get("/drive/v1/questions")
@require_roles(*AUTHOR)
def list_questions():
    with _db().session() as s:
        rows = _svc().list(
            s,
            category=request.args.get("category"),
            difficulty=request.args.get("difficulty"),
            qtype=request.args.get("type"),
            status=request.args.get("status"),
            limit=min(int(request.args.get("limit", 50)), 500),
        )
        return ok([_svc().out(q) for q in rows])


@bp.get("/drive/v1/questions/<qid>")
@require_roles(*AUTHOR)
def get_question(qid):
    with _db().session() as s:
        return ok(_svc().out(_svc().get(s, qid), with_key=True))


@bp.put("/drive/v1/questions/<qid>")
@require_roles(*AUTHOR)
def edit_question(qid):
    data = _parse(QuestionEdit, request.get_json(silent=True))
    with _db().session() as s:
        return ok(_svc().out(_svc().edit(s, qid, data), with_key=True))


@bp.post("/drive/v1/questions/<qid>/activate")
@require_roles(*AUTHOR)
def activate(qid):
    with _db().session() as s:
        return ok(_svc().out(_svc().activate(s, qid), with_key=True))


# Approval workflow (req #14): submit -> approve/reject -> publish.
REVIEWER = ("super_admin", "company_admin")


@bp.post("/drive/v1/questions/<qid>/workflow/<action>")
@require_roles(*AUTHOR)
def workflow(qid, action):
    ident = _identity()
    # Only reviewers may approve/reject; authors may submit/publish own drafts.
    if action in ("approve", "reject") and not ident.has_role(*REVIEWER):
        raise BadRequest("Reviewer role required", code="reviewer_required")
    with _db().session() as s:
        return ok(_svc().out(_svc().transition(s, qid, action, ident.user_id), with_key=True))


@bp.post("/drive/v1/questions/meta")
@require_roles(*AUTHOR)
def question_meta():
    # Topic metadata for a set of question IDs (internal — Cognitive Twin). No
    # stems or answer keys are returned.
    body = request.get_json(silent=True) or {}
    with _db().session() as s:
        return ok(_svc().meta(s, body.get("ids") or []))


@bp.get("/drive/v1/questions/search")
@require_roles(*AUTHOR)
def search_questions():
    q = request.args.get("q", "").strip()
    with _db().session() as s:
        return ok(_svc().search(s, q) if q else [])


@bp.post("/drive/v1/questions/import")
@require_roles(*AUTHOR)
def import_questions():
    ident = _identity()
    body = request.get_json(silent=True) or {}
    fmt = (body.get("format") or "json").lower()
    content = body.get("content") or ""
    if not content:
        raise BadRequest("content is required", code="content_required")
    with _db().session() as s:
        return created(_svc().import_text(s, fmt, content, ident.user_id))


@bp.post("/drive/v1/questions/bulk")
@require_roles(*AUTHOR)
def bulk():
    ident = _identity()
    data = _parse(BulkIn, request.get_json(silent=True))
    with _db().session() as s:
        return ok(_svc().bulk_import(s, data.questions, ident.user_id))


@bp.post("/drive/v1/blueprints")
@require_roles(*AUTHOR)
def create_blueprint():
    data = _parse(BlueprintIn, request.get_json(silent=True))
    with _db().session() as s:
        b = _svc().create_blueprint(s, data)
        return created({"id": b.id, "name": b.name})


@bp.post("/drive/v1/blueprints/<bid>/generate-paper")
@require_roles(*AUTHOR)
def generate_paper(bid):
    with _db().session() as s:
        return ok(_svc().generate_paper(s, bid))
