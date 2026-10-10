"""Coding assessment logic: problems, IDE sessions, run vs samples, submit vs
hidden cases, weighted scoring. Hidden expected outputs are never returned."""
from __future__ import annotations

import logging

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from lare_common.errors import Conflict, Forbidden, NotFound
from lare_common.security import new_id

from .executor import Executor
from .models import CodingSession, CodingSubmission, CodingViva, Problem

log = logging.getLogger("lare-coding")

VIVA_PASS = 60.0  # explanation score needed to "verify" a solved problem


def _norm(s: str) -> str:
    return "\n".join(line.rstrip() for line in (s or "").strip().splitlines())


class CodingService:
    def __init__(self, executor: Executor, timeout_sec: int = 5):
        self.executor = executor
        self.timeout = timeout_sec

    # ---------- problems ----------
    def create_problem(self, s: Session, data) -> Problem:
        p = Problem(id=new_id(), title=data.title, statement=data.statement,
                    languages=data.languages, time_limit_sec=data.time_limit_sec,
                    sample_cases=[c.model_dump() for c in data.sample_cases],
                    hidden_cases=[c.model_dump() for c in data.hidden_cases],
                    max_score=data.max_score,
                    skill=getattr(data, "skill", "General"),
                    difficulty=getattr(data, "difficulty", "easy"),
                    practice=getattr(data, "practice", False))
        s.add(p)
        s.flush()
        return p

    def get_problem(self, s: Session, pid: str) -> Problem:
        p = s.get(Problem, pid)
        if not p:
            raise NotFound("Problem not found", code="problem_not_found")
        return p

    # ---------- sessions ----------
    def open_session(self, s: Session, candidate_id: str, data) -> dict:
        p = self.get_problem(s, data.problem_id)
        cs = CodingSession(id=new_id(), problem_id=p.id, candidate_id=candidate_id,
                           exam_session_id=data.exam_session_id, language=data.language,
                           kind="exam")
        s.add(cs)
        s.flush()
        return {"session_id": cs.id, "problem": self.problem_for_candidate(p),
                "language": cs.language}

    # ---------- LMS practice (feeds the Cognitive Twin) ----------
    def list_practice(self, s: Session, skill: str | None = None,
                      difficulty: str | None = None) -> list[dict]:
        """The Lityra Learn practice bank — problems flagged practice=True. For
        each, tell the learner whether they've already solved it (best score)."""
        q = select(Problem).where(Problem.practice.is_(True))
        if skill:
            q = q.where(Problem.skill == skill)
        if difficulty:
            q = q.where(Problem.difficulty == difficulty)
        return [self.problem_card(p) for p in
                s.execute(q.order_by(Problem.difficulty, Problem.title)).scalars().all()]

    def open_practice(self, s: Session, learner_id: str, data) -> dict:
        p = self.get_problem(s, data.problem_id)
        if not p.practice:
            raise NotFound("Practice problem not found", code="problem_not_found")
        lang = data.language if data.language in (p.languages or ["python"]) else \
            (p.languages or ["python"])[0]
        cs = CodingSession(id=new_id(), problem_id=p.id, candidate_id=learner_id,
                           exam_session_id=None, language=lang, kind="practice")
        s.add(cs)
        s.flush()
        return {"session_id": cs.id, "problem": self.problem_for_candidate(p),
                "language": cs.language, "skill": p.skill, "difficulty": p.difficulty}

    def practice_skills(self, s: Session, learner_id: str) -> dict:
        """Aggregate a learner's practice history into a coding skill profile:
        best score per problem, rolled up by skill and by language. Consumed by
        the assessment service's Cognitive Twin and by the learner's own view."""
        rows = s.execute(
            select(CodingSession.problem_id, CodingSession.language,
                   Problem.skill, Problem.max_score,
                   func.max(CodingSubmission.score).label("best"),
                   func.max(CodingSubmission.cases_passed).label("best_cases"),
                   func.max(CodingSubmission.total_cases).label("total_cases"))
            .join(CodingSubmission, CodingSubmission.coding_session_id == CodingSession.id)
            .join(Problem, Problem.id == CodingSession.problem_id)
            .where(CodingSession.candidate_id == learner_id,
                   CodingSession.kind == "practice")
            .group_by(CodingSession.problem_id, CodingSession.language,
                      Problem.skill, Problem.max_score)
        ).all()

        # Collapse to the learner's best attempt per problem (across languages).
        per_problem: dict[str, dict] = {}
        lang_of_best: dict[str, str] = {}
        for pid, lang, skill, max_score, best, best_cases, total_cases in rows:
            mx = float(max_score or 100.0)
            pct = round(float(best or 0) * 100.0 / mx, 1) if mx else 0.0
            solved = 1 if (total_cases and best_cases >= total_cases) else 0
            cur = per_problem.get(pid)
            if cur is None or pct > cur["pct"]:
                per_problem[pid] = {"skill": skill or "General", "pct": pct,
                                    "solved": solved, "lang": lang}
                lang_of_best[pid] = lang

        def _band(pct: float) -> str:
            return "strong" if pct >= 80 else ("developing" if pct >= 55 else "weak")

        skill_acc: dict[str, dict] = {}
        lang_acc: dict[str, dict] = {}

        def _bump(store: dict, key: str, pct: float, solved: int):
            b = store.setdefault(key, {"attempted": 0, "solved": 0, "pct_sum": 0.0})
            b["attempted"] += 1
            b["solved"] += solved
            b["pct_sum"] += pct

        for pid, v in per_problem.items():
            _bump(skill_acc, v["skill"], v["pct"], v["solved"])
            _bump(lang_acc, v["lang"], v["pct"], v["solved"])

        def _fmt(store: dict) -> list[dict]:
            out = []
            for k, b in store.items():
                m = round(b["pct_sum"] / b["attempted"], 1) if b["attempted"] else 0.0
                out.append({"name": k, "attempted": b["attempted"], "solved": b["solved"],
                            "mastery": m, "band": _band(m)})
            out.sort(key=lambda r: r["mastery"], reverse=True)
            return out

        # Which solved problems has the learner actually *explained* (passed a
        # viva)? Verified problems are cheat-resistant proof of competence.
        verified_pids = set(s.execute(
            select(CodingViva.problem_id).where(
                CodingViva.candidate_id == learner_id,
                CodingViva.passed.is_(True)).distinct()
        ).scalars().all())

        skill_verified: dict[str, int] = {}
        for pid, v in per_problem.items():
            if pid in verified_pids:
                skill_verified[v["skill"]] = skill_verified.get(v["skill"], 0) + 1

        def _fmt_v(store: dict) -> list[dict]:
            out = _fmt(store)
            for r in out:
                r["verified"] = skill_verified.get(r["name"], 0)
            return out

        attempted = len(per_problem)
        solved = sum(v["solved"] for v in per_problem.values())
        verified = len([1 for pid in per_problem if pid in verified_pids])
        overall = round(sum(v["pct"] for v in per_problem.values()) / attempted, 1) \
            if attempted else 0.0
        return {
            "learner_id": learner_id,
            "attempted": attempted,
            "solved": solved,
            "verified": verified,
            "mastery": overall,
            "by_skill": _fmt_v(skill_acc),
            "by_language": _fmt(lang_acc),
        }

    # ---------- adversarial viva (cheat-resistant proof of competence) ----------
    def _latest_submission(self, s: Session, sid: str) -> CodingSubmission | None:
        return s.execute(
            select(CodingSubmission).where(CodingSubmission.coding_session_id == sid)
            .order_by(CodingSubmission.submitted_at.desc())
        ).scalars().first()

    def start_viva(self, s: Session, sid: str, candidate_id: str) -> dict:
        """After a submission, generate ONE probing question that checks the
        author truly understands their own solution."""
        cs = self._session(s, sid, candidate_id)  # ownership check
        sub = self._latest_submission(s, sid)
        if sub is None:
            raise Conflict("Submit your solution before the viva", code="no_submission")
        p = self.get_problem(s, cs.problem_id)
        # Reuse an outstanding (un-graded) viva so a reload doesn't re-ask.
        existing = s.execute(
            select(CodingViva).where(CodingViva.coding_session_id == sid,
                                     CodingViva.candidate_id == candidate_id,
                                     CodingViva.status == "asked")
            .order_by(CodingViva.created_at.desc())
        ).scalars().first()
        if existing is not None:
            return {"viva_id": existing.id, "question": existing.question}
        question, generated = self._viva_question(p, sub.code, cs.language)
        v = CodingViva(id=new_id(), coding_session_id=sid, problem_id=p.id,
                       candidate_id=candidate_id, question=question,
                       ai_generated=generated, status="asked")
        s.add(v)
        s.flush()
        return {"viva_id": v.id, "question": question}

    def grade_viva(self, s: Session, viva_id: str, candidate_id: str, answer: str) -> dict:
        v = s.get(CodingViva, viva_id)
        if v is None:
            raise NotFound("Viva not found", code="viva_not_found")
        if v.candidate_id != candidate_id:
            raise Forbidden("Not your viva")
        if v.status == "graded":
            return {"score": v.score, "passed": v.passed, "verdict": v.verdict,
                    "already_graded": True}
        if not (answer or "").strip():
            raise Conflict("Write your explanation first", code="empty_answer")
        p = self.get_problem(s, v.problem_id)
        sub = self._latest_submission(s, v.coding_session_id)
        code = sub.code if sub else ""
        score, verdict, passed, generated = self._viva_grade(p, code, v.question, answer)
        v.answer = answer[:4096]
        v.score = score
        v.passed = passed
        v.verdict = verdict
        v.ai_generated = generated
        v.status = "graded"
        s.flush()
        return {"score": score, "passed": passed, "verdict": verdict,
                "verified": passed}

    # ---- AI (LMS Gemini) with a rule-based fallback so it always works ----
    @staticmethod
    def _viva_question(p: Problem, code: str, language: str) -> tuple[str, bool]:
        fallback = ("In your own words, explain your approach to “{}”. "
                    "What is the time complexity of your solution, and why is it "
                    "correct?".format(p.title))
        system = ("You are a fair but sharp coding examiner. Ask ONE short question "
                  "that checks whether the student genuinely understands the solution "
                  "they wrote — their approach, its complexity, or a tricky edge case. "
                  "Do not reveal the answer.")
        prompt = ("Problem: {}\n\nStudent's {} code:\n{}\n\n"
                  "Return JSON only: {{\"question\": \"...\"}}").format(
                      p.statement, language, (code or "")[:2000])
        try:
            from lare_common.ai import build_client_from_env
            client = build_client_from_env()
            parsed, res = client.complete_json(
                system=system, messages=[{"role": "user", "content": prompt}],
                fallback={"question": fallback}, max_tokens=200)
            q = (parsed or {}).get("question") or fallback
            return q, (not getattr(res, "stub", True))
        except Exception:  # noqa: BLE001
            log.warning("viva question generation failed; using fallback")
            return fallback, False

    @staticmethod
    def _viva_grade(p: Problem, code: str, question: str, answer: str) -> tuple[float, str, bool, bool]:
        # Rule-based fallback: reward a substantive explanation that engages with
        # complexity / reasoning. Deliberately lenient — real grading uses the AI.
        def _fallback() -> tuple[float, str, bool, bool]:
            a = (answer or "").lower().strip()
            words = len(a.split())
            signals = sum(t in a for t in (
                "complex", "o(", "loop", "iterat", "recurs", "sort", "hash",
                "because", "index", "compare", "edge", "time", "space", "array"))
            score = min(100.0, words * 2.0 + signals * 8.0)
            passed = score >= VIVA_PASS
            verdict = ("Solid explanation that engages with how and why your solution works."
                       if passed else
                       "Too thin to confirm understanding — explain your approach and its "
                       "complexity in more depth.")
            return round(score, 1), verdict, passed, False

        system = ("You grade a student's spoken-style explanation of their own code. "
                  "Reward genuine understanding of the approach, correctness, and "
                  "complexity; penalise vague or copied-sounding answers. Be fair but "
                  "rigorous — this is an anti-cheating check.")
        prompt = ("Problem: {}\n\nStudent's code:\n{}\n\nExaminer question: {}\n\n"
                  "Student's explanation: {}\n\n"
                  "Grade understanding 0-100. Return JSON only: "
                  "{{\"score\": <int>, \"verdict\": \"one sentence\", "
                  "\"passed\": <true if score>=60>}}").format(
                      p.statement, (code or "")[:1500], question, (answer or "")[:1500])
        try:
            from lare_common.ai import build_client_from_env
            client = build_client_from_env()
            parsed, res = client.complete_json(
                system=system, messages=[{"role": "user", "content": prompt}],
                fallback={}, max_tokens=250)
            if not parsed or getattr(res, "stub", True):
                return _fallback()
            score = float(parsed.get("score", 0))
            score = max(0.0, min(100.0, score))
            passed = bool(parsed.get("passed", score >= VIVA_PASS))
            verdict = str(parsed.get("verdict") or "").strip() or "Graded."
            return round(score, 1), verdict, passed, True
        except Exception:  # noqa: BLE001
            log.warning("viva grading failed; using rule-based fallback")
            return _fallback()

    def _session(self, s: Session, sid: str, candidate_id: str) -> CodingSession:
        cs = s.get(CodingSession, sid)
        if not cs:
            raise NotFound("Coding session not found", code="coding_session_not_found")
        if cs.candidate_id != candidate_id:
            from lare_common.errors import Forbidden
            raise Forbidden("Not your session")
        return cs

    def save(self, s: Session, sid: str, candidate_id: str, code: str) -> dict:
        cs = self._session(s, sid, candidate_id)
        if cs.status != "open":
            raise Conflict("Session already submitted", code="already_submitted")
        cs.draft_code = code
        s.flush()
        return {"saved": True, "length": len(code)}

    # ---------- run / submit ----------
    def run_samples(self, s: Session, sid: str, candidate_id: str, code: str) -> dict:
        cs = self._session(s, sid, candidate_id)
        p = self.get_problem(s, cs.problem_id)
        results = []
        for case in p.sample_cases:
            r = self.executor.run(cs.language, code, case.get("input", ""),
                                  min(self.timeout, p.time_limit_sec),
                                  mem_mb=getattr(p, "memory_limit_mb", 256))
            passed = (not r.timed_out and r.exit_code == 0
                      and _norm(r.stdout) == _norm(case.get("expected", "")))
            results.append({
                "input": case.get("input", ""), "expected": case.get("expected", ""),
                "stdout": r.stdout, "stderr": r.stderr, "passed": passed,
                "time_ms": r.time_ms, "timed_out": r.timed_out,
                "compile_log": r.compile_log, "compile_failed": r.compile_failed,
            })
        return {"cases": results, "language": cs.language,
                "compile_failed": any(x["compile_failed"] for x in results),
                "passed": sum(1 for x in results if x["passed"]), "total": len(results)}

    def languages(self) -> dict:
        return {"languages": self.executor.language_versions()}

    def run_adhoc(self, language: str, code: str, cases: list, timeout: int = 5,
                  mem_mb: int = 256) -> dict:
        """Stateless run for exam coding questions: execute code against the
        supplied (visible) test cases and report pass/fail per case. No stored
        problem needed — the exam question carries its own sample cases."""
        results = []
        compile_failed = False
        compile_log = ""
        for case in cases[:20]:
            r = self.executor.run(language, code, case.get("input", ""),
                                  min(self.timeout, timeout), mem_mb=mem_mb)
            if r.compile_failed:
                compile_failed = True
                compile_log = r.compile_log
            passed = (not r.timed_out and r.exit_code == 0
                      and _norm(r.stdout) == _norm(case.get("expected", "")))
            results.append({
                "input": case.get("input", ""), "expected": case.get("expected", ""),
                "stdout": r.stdout, "stderr": r.stderr, "passed": passed,
                "time_ms": r.time_ms, "timed_out": r.timed_out,
            })
        return {"language": language, "compile_failed": compile_failed,
                "compile_log": compile_log, "cases": results,
                "passed": sum(1 for x in results if x["passed"]), "total": len(results)}

    def submit(self, s: Session, sid: str, candidate_id: str, code: str) -> dict:
        cs = self._session(s, sid, candidate_id)
        if cs.status != "open":
            raise Conflict("Session already submitted", code="already_submitted")
        p = self.get_problem(s, cs.problem_id)
        detail = []
        passed = 0
        for i, case in enumerate(p.hidden_cases):
            r = self.executor.run(cs.language, code, case.get("input", ""),
                                  min(self.timeout, p.time_limit_sec),
                                  mem_mb=getattr(p, "memory_limit_mb", 256))
            ok = (not r.timed_out and r.exit_code == 0
                  and _norm(r.stdout) == _norm(case.get("expected", "")))
            if ok:
                passed += 1
            # NOTE: no expected/stdout leaked for hidden cases.
            detail.append({"case": i + 1, "passed": ok, "timed_out": r.timed_out,
                           "time_ms": r.time_ms})
        total = len(p.hidden_cases)
        score = round(p.max_score * passed / total, 2) if total else 0.0
        cs.draft_code = code
        cs.status = "submitted"
        sub = CodingSubmission(id=new_id(), coding_session_id=sid, code=code, score=score,
                               cases_passed=passed, total_cases=total, detail=detail)
        s.add(sub)
        s.flush()
        return {"session_id": sid, "score": score, "cases_passed": passed,
                "total_cases": total, "detail": detail}

    def result(self, s: Session, sid: str) -> dict:
        sub = s.execute(
            select(CodingSubmission).where(CodingSubmission.coding_session_id == sid)
            .order_by(CodingSubmission.submitted_at.desc())
        ).scalars().first()
        if not sub:
            raise NotFound("No submission", code="no_submission")
        return {"session_id": sid, "score": sub.score, "cases_passed": sub.cases_passed,
                "total_cases": sub.total_cases, "detail": sub.detail}

    # ---------- serializers ----------
    @staticmethod
    def problem_for_candidate(p: Problem) -> dict:
        # Only sample cases are visible; hidden cases (and their count) withheld.
        return {"id": p.id, "title": p.title, "statement": p.statement,
                "languages": p.languages, "time_limit_sec": p.time_limit_sec,
                "sample_cases": p.sample_cases, "max_score": p.max_score,
                "skill": getattr(p, "skill", "General"),
                "difficulty": getattr(p, "difficulty", "easy")}

    @staticmethod
    def problem_card(p: Problem) -> dict:
        # Practice-bank listing card — no cases, just the metadata a learner needs
        # to pick a problem.
        return {"id": p.id, "title": p.title, "skill": p.skill,
                "difficulty": p.difficulty, "languages": p.languages,
                "max_score": p.max_score}
