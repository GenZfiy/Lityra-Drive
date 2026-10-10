"""HTTP layer for the AI Orchestration Service (governed Claude egress).

Internal/staff-facing: other services (e.g. AI Tutor) call this east-west with a
prompt_key. The prompt library is the guardrail — no raw prompts accepted."""
from __future__ import annotations

from flask import Blueprint, current_app, request
from pydantic import ValidationError

from lare_common.auth_context import current_identity, require_roles
from lare_common.errors import BadRequest, NotFound
from lare_common.responses import created, ok

from .schemas import CompleteIn
from .service import AIService

bp = Blueprint("ai", __name__)

# Staff + internal service roles may invoke the model.
INVOKE = ("super_admin", "company_admin", "college_admin", "trainer", "recruiter")


def _svc() -> AIService:
    return current_app.extensions["svc"]


def _db():
    return current_app.extensions["db"]


def _parse(model, payload):
    try:
        return model.model_validate(payload or {})
    except ValidationError as e:
        raise BadRequest("Validation failed", code="validation_error",
                         details=e.errors(include_url=False)) from e


@bp.get("/ai/v1/prompts")
@require_roles(*INVOKE)
def list_prompts():
    return ok(_svc().prompts())


@bp.post("/ai/v1/complete")
@require_roles(*INVOKE)
def complete():
    ident = current_identity()
    data = _parse(CompleteIn, request.get_json(silent=True))
    from .prompts import PROMPTS
    if data.prompt_key not in PROMPTS:
        raise NotFound("Unknown prompt_key", code="unknown_prompt")
    with _db().session() as s:
        return created(_svc().run(
            s, prompt_key=data.prompt_key, variables=data.variables,
            actor_id=ident.user_id, purpose=data.purpose, want_json=data.want_json,
            history=data.history, json_fallback=data.json_fallback))


@bp.get("/ai/v1/usage")
@require_roles("super_admin", "company_admin")
def usage():
    with _db().session() as s:
        return ok(_svc().usage(s))
