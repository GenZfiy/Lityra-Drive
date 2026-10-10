"""Question bank logic: authoring, versioning, activation, bulk import,
blueprint-based paper generation. Answer keys are never returned to non-authors."""
from __future__ import annotations

import json
import logging
import random

from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

import os

from lare_common.ai import _EnvCfg, build_client
from lare_common.errors import Conflict, NotFound, ServiceUnavailable
from lare_common.security import new_id

from .models import Blueprint, Question

log = logging.getLogger("lare-questionbank")


def _drive_ai_client():
    """Build the AI client for the DRIVE product. Drive uses Mistral by default
    (override with DRIVE_AI_PROVIDER); this is independent of the LMS provider so
    the two products never share an AI backend."""
    cfg = type("DriveAICfg", (), {k: getattr(_EnvCfg, k)
                                  for k in dir(_EnvCfg) if k.isupper()})
    cfg.AI_PROVIDER = os.getenv("DRIVE_AI_PROVIDER", "mistral")
    return build_client(cfg)


def _clean_cases(raw) -> list[dict]:
    out = []
    for c in raw or []:
        if not isinstance(c, dict):
            continue
        inp, exp = str(c.get("input", "")), str(c.get("expected", ""))
        if inp.strip() or exp.strip():
            out.append({"input": inp, "expected": exp})
    return out


class QuestionBankService:
    # ---------- AI generation (Gemini/Claude via lare_common.ai) ----------
    def generate(self, data) -> dict:
        """Draft exam-ready questions with the configured AI provider.

        Every returned question is validated the same way the exam builder is:
        a blank stem, an MCQ with fewer than two options or no marked answer, or
        a coding question with no test cases is DROPPED — never surfaced. If the
        provider is unavailable (stub) or nothing valid comes back, we raise so
        the recruiter sees an honest error rather than placeholder questions."""
        client = _drive_ai_client()
        if data.type == "coding":
            system, prompt, parse = self._coding_prompt(data)
        else:
            system, prompt, parse = self._mcq_prompt(data)
        # Coding questions (statement + sample + hidden cases) are token-heavy;
        # give the batch generous headroom so nothing truncates.
        budget = 1200 * data.count + 1024
        parsed, res = client.complete_json(
            system=system, messages=[{"role": "user", "content": prompt}],
            fallback=None, max_tokens=budget)
        if res.stub:
            if res.error == "rate_limited":
                raise ServiceUnavailable(
                    "The AI provider's quota/rate limit was hit. Wait a minute and "
                    "retry, or lower the count - the free tier is capped per day.",
                    code="ai_rate_limited")
            if res.error == "provider_error":
                raise ServiceUnavailable(
                    "The AI provider returned an error. Please try again shortly.",
                    code="ai_provider_error")
            raise ServiceUnavailable(
                "AI generation is not configured — set GEMINI_API_KEY to enable it.",
                code="ai_unavailable")
        if parsed is None:
            raise ServiceUnavailable(
                "The AI response could not be read. Please try again.",
                code="ai_unparseable")
        questions = parse(parsed)
        if not questions:
            raise ServiceUnavailable(
                "The AI did not return usable questions. Try a more specific topic.",
                code="ai_empty")
        return {"questions": questions, "count": len(questions),
                "model": res.model, "provider": client.mode}

    def _mcq_prompt(self, data):
        system = (
            "You are an expert campus-recruitment assessment author. You write "
            "clear, unambiguous multiple-choice questions with exactly one correct "
            "answer. Output STRICT JSON only, no prose.")
        prompt = (
            f"Write {data.count} {data.difficulty} multiple-choice questions on "
            f"\"{data.topic}\" for a {data.category} section of a campus placement test.\n"
            "Return JSON of this exact shape:\n"
            '{"questions":[{"stem":"...","options":[{"id":"a","text":"..."},'
            '{"id":"b","text":"..."},{"id":"c","text":"..."},{"id":"d","text":"..."}],'
            '"correct":"a","explanation":"..."}]}\n'
            "Rules: 4 options (ids a,b,c,d); exactly one correct id; no blank text; "
            "self-contained stems; vary the correct option across questions.")

        def parse(obj):
            out = []
            for q in (obj.get("questions") if isinstance(obj, dict) else obj) or []:
                stem = str(q.get("stem", "")).strip()
                opts = [{"id": str(o.get("id")), "text": str(o.get("text", "")).strip()}
                        for o in (q.get("options") or []) if isinstance(o, dict)
                        and str(o.get("text", "")).strip()]
                correct = str(q.get("correct", "")).strip()
                if not stem or len(opts) < 2 or correct not in {o["id"] for o in opts}:
                    log.warning("dropped invalid AI MCQ: stem=%r opts=%d", stem[:40], len(opts))
                    continue
                out.append({"type": "mcq", "stem": stem, "options": opts,
                            "correct": correct, "category": data.category,
                            "difficulty": data.difficulty, "weight": 1,
                            "explanation": str(q.get("explanation", "")).strip()})
            return out
        return system, prompt, parse

    def _coding_prompt(self, data):
        langs = ", ".join(data.languages)
        system = (
            "You are an expert programming-assessment author. You write precise "
            "coding problems with deterministic stdin/stdout test cases. Output "
            "STRICT JSON only, no prose.")
        prompt = (
            f"Write {data.count} {data.difficulty} coding problems on \"{data.topic}\".\n"
            "Each reads input from STDIN and writes the answer to STDOUT. Provide "
            "sample cases (shown to candidates) and hidden cases (for grading).\n"
            "Return JSON of this exact shape:\n"
            '{"questions":[{"stem":"full problem statement incl. input/output format",'
            '"sample_cases":[{"input":"...","expected":"..."}],'
            '"hidden_cases":[{"input":"...","expected":"..."}]}]}\n'
            "Rules: expected outputs must be EXACT (no trailing prose); >=1 sample "
            f"and >=2 hidden cases each; solvable in any of: {langs}.")

        def parse(obj):
            out = []
            for q in (obj.get("questions") if isinstance(obj, dict) else obj) or []:
                stem = str(q.get("stem", "")).strip()
                sample = _clean_cases(q.get("sample_cases"))
                hidden = _clean_cases(q.get("hidden_cases"))
                if not stem or not (sample or hidden):
                    log.warning("dropped invalid AI coding q: stem=%r cases=%d",
                                stem[:40], len(sample) + len(hidden))
                    continue
                out.append({"type": "coding", "stem": stem,
                            "sample_cases": sample or [{"input": "", "expected": ""}],
                            "hidden_cases": hidden, "languages": list(data.languages),
                            "category": "programming", "difficulty": data.difficulty,
                            "weight": 5})
            return out
        return system, prompt, parse

    # ---------- authoring ----------
    def create(self, s: Session, data, author: str) -> Question:
        q = Question(id=new_id(), type=data.type, category=data.category,
                     difficulty=data.difficulty, tags=data.tags, stem=data.stem,
                     options=data.options, answer_key=data.answer_key,
                     explanation=data.explanation, weight=data.weight, author_id=author)
        s.add(q)
        s.flush()
        return q

    def get(self, s: Session, qid: str) -> Question:
        q = s.get(Question, qid)
        if not q:
            raise NotFound("Question not found", code="question_not_found")
        return q

    def edit(self, s: Session, qid: str, data) -> Question:
        q = self.get(s, qid)
        # Keys are immutable once used in a live (active) exam: bump version but
        # block key edits on active items (QB-2).
        if q.status == "active" and data.answer_key is not None:
            raise Conflict("Cannot change key of an active question; create a new version",
                           code="active_key_locked")
        for f in ("stem", "options", "answer_key", "explanation", "difficulty", "tags"):
            v = getattr(data, f)
            if v is not None:
                setattr(q, f, v)
        q.version += 1
        s.flush()
        return q

    def activate(self, s: Session, qid: str) -> Question:
        q = self.get(s, qid)
        q.status = "active"
        s.flush()
        return q

    def bulk_import(self, s: Session, questions, author: str) -> dict:
        created = 0
        for item in questions:
            self.create(s, item, author)
            created += 1
        return {"imported": created}

    def search(self, s: Session, q: str, limit: int = 10) -> list[dict]:
        from sqlalchemy import func
        like = f"%{q.lower()}%"
        rows = s.execute(
            select(Question).where(func.lower(Question.stem).like(like)).limit(limit)
        ).scalars().all()
        return [{"type": "question", "id": qq.id, "title": qq.stem[:80],
                 "subtitle": f"{qq.category} · {qq.difficulty}", "status": qq.status}
                for qq in rows]

    # ---------- approval workflow (draft -> review -> approved -> active) ----------
    def transition(self, s: Session, qid: str, action: str, actor: str) -> Question:
        q = self.get(s, qid)
        flow = {
            "submit": ("draft", "review"),
            "approve": ("review", "approved"),
            "reject": ("review", "draft"),
            "publish": ("approved", "active"),
        }
        if action not in flow:
            raise Conflict("Unknown workflow action", code="bad_action")
        expected_from, to = flow[action]
        # Allow publish from approved OR (lenient) from draft for backward-compat.
        if action == "publish" and q.status in ("approved", "draft", "review"):
            q.status = "active"
        elif q.status == expected_from:
            q.status = to
        else:
            raise Conflict(f"Cannot {action} a question in '{q.status}' state",
                           code="bad_transition")
        s.flush()
        return q

    # ---------- import from CSV / JSON (req #11) ----------
    def import_text(self, s: Session, fmt: str, content: str, author: str) -> dict:
        from types import SimpleNamespace
        items: list = []
        if fmt == "json":
            import json
            data = json.loads(content)
            rows = data if isinstance(data, list) else data.get("questions", [])
            for r in rows:
                items.append(SimpleNamespace(
                    type=r.get("type", "mcq"), category=r.get("category", "aptitude"),
                    difficulty=r.get("difficulty", "easy"), tags=r.get("tags", []),
                    stem=r.get("stem", ""), options=r.get("options", []),
                    answer_key=r.get("answer_key", {}), explanation=r.get("explanation"),
                    weight=float(r.get("weight", 1))))
        elif fmt == "csv":
            import csv as _csv
            import io as _io
            reader = _csv.DictReader(_io.StringIO(content))
            for row in reader:
                opts_raw = (row.get("options") or "").split("|")
                options = [{"id": "abcd"[i], "text": t.strip()} for i, t in enumerate(opts_raw) if t.strip()]
                correct = (row.get("correct") or "a").strip().lower()
                items.append(SimpleNamespace(
                    type=row.get("type", "mcq").strip(), category=row.get("category", "aptitude").strip(),
                    difficulty=row.get("difficulty", "easy").strip(),
                    tags=[t for t in (row.get("tags", "").split(";")) if t],
                    stem=row.get("stem", "").strip(), options=options,
                    answer_key={"option": correct}, explanation=row.get("explanation"),
                    weight=float(row.get("weight", 1) or 1)))
        else:
            raise Conflict("Unsupported import format (use csv or json; xlsx/docx need optional libs)",
                           code="unsupported_format")
        return self.bulk_import(s, items, author)

    def list(self, s: Session, *, category=None, difficulty=None, qtype=None,
             status=None, limit=50) -> list[Question]:
        q = select(Question)
        conds = []
        if category:
            conds.append(Question.category == category)
        if difficulty:
            conds.append(Question.difficulty == difficulty)
        if qtype:
            conds.append(Question.type == qtype)
        if status:
            conds.append(Question.status == status)
        if conds:
            q = q.where(and_(*conds))
        return list(s.execute(q.limit(limit)).scalars().all())

    def meta(self, s: Session, ids: list[str]) -> list[dict]:
        """Topic metadata for a set of question IDs — no stems, no answer keys.
        Used by the Cognitive Twin to map answered questions to skills/topics."""
        ids = [i for i in dict.fromkeys(ids) if i]
        if not ids:
            return []
        rows = s.execute(select(Question).where(Question.id.in_(ids))).scalars().all()
        return [{"id": q.id, "category": q.category, "difficulty": q.difficulty,
                 "tags": q.tags or []} for q in rows]

    # ---------- blueprints ----------
    def create_blueprint(self, s: Session, data) -> Blueprint:
        bp = Blueprint(id=new_id(), name=data.name, spec=data.spec)
        s.add(bp)
        s.flush()
        return bp

    def generate_paper(self, s: Session, blueprint_id: str) -> dict:
        bp = s.get(Blueprint, blueprint_id)
        if not bp:
            raise NotFound("Blueprint not found", code="blueprint_not_found")
        picked = []
        shortfalls = []
        for section in bp.spec:
            cat = section.get("category")
            diff = section.get("difficulty")
            count = int(section.get("count", 0))
            pool = self.list(s, category=cat, difficulty=diff, status="active", limit=1000)
            if len(pool) < count:
                shortfalls.append({"category": cat, "difficulty": diff,
                                   "requested": count, "available": len(pool)})
            chosen = random.sample(pool, min(count, len(pool)))
            picked.extend(self.item_for_paper(q) for q in chosen)
        random.shuffle(picked)
        return {"blueprint": bp.name, "count": len(picked),
                "questions": picked, "shortfalls": shortfalls}

    # ---------- serializers ----------
    @staticmethod
    def item_for_paper(q: Question) -> dict:
        # No answer key — this is exam-facing.
        return {"id": q.id, "type": q.type, "category": q.category,
                "difficulty": q.difficulty, "stem": q.stem, "options": q.options,
                "weight": q.weight}

    @staticmethod
    def out(q: Question, *, with_key: bool = False) -> dict:
        base = {"id": q.id, "type": q.type, "category": q.category,
                "difficulty": q.difficulty, "tags": q.tags, "stem": q.stem,
                "options": q.options, "weight": q.weight, "version": q.version,
                "status": q.status, "explanation": q.explanation}
        if with_key:
            base["answer_key"] = q.answer_key
        return base
