"""Evaluation logic: deterministic auto-grading, ranking, difficulty index.

Objective items are graded against the hidden key with optional negative
marking; coding items take a pre-computed score from the Coding service. In
production, answers come from the Submission export and keys from the Question
Bank — the run endpoint accepts them assembled. Re-evaluation preserves history
by bumping the version."""
from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from lare_common.errors import NotFound
from lare_common.security import new_id
from lare_common.service_client import ServiceClient

from .models import AnswerKey, Evaluation, Rank

log = logging.getLogger("lare-evaluation")


def _attempted(resp) -> bool:
    """Did the candidate actually answer this question?"""
    if not resp:
        return False
    if isinstance(resp, dict):
        if "code" in resp:
            return bool(str(resp.get("code") or "").strip())
        if "options" in resp:
            return bool(resp.get("options"))
        if "option" in resp:
            return resp.get("option") not in (None, "")
        return any(v not in (None, "", []) for v in resp.values())
    return bool(str(resp).strip())

# East-west client to the Coding service for running submissions during grading.
_CODE = ServiceClient("drive-evaluation", default_roles=["company_admin"], timeout=90)
# East-west client to the Question Bank — resolves question IDs to topic tags for
# the Cognitive Twin skill profile.
_QB = ServiceClient("drive-evaluation", default_roles=["company_admin"], timeout=15)


def _mastery(correct: int, attempted: int) -> float:
    return round(correct * 100.0 / attempted, 1) if attempted else 0.0


def _band(pct: float) -> str:
    if pct >= 80:
        return "strong"
    if pct >= 55:
        return "developing"
    return "weak"


class EvaluationService:
    def upsert_key(self, s: Session, data) -> AnswerKey:
        k = s.get(AnswerKey, data.exam_id)
        items = [i.model_dump() for i in data.items]
        if k is None:
            k = AnswerKey(exam_id=data.exam_id, items=items,
                          passing_pct=data.passing_pct, negative_marking=data.negative_marking)
            s.add(k)
        else:
            k.items = items
            k.passing_pct = data.passing_pct
            k.negative_marking = data.negative_marking
        s.flush()
        return k

    def get_key(self, s: Session, exam_id: str) -> dict:
        """Return the stored answer key (correct answers + coding cases) for the
        admin question-paper view. Staff-only route."""
        k = s.get(AnswerKey, exam_id)
        if not k:
            raise NotFound("No answer key for exam", code="key_not_found")
        return {"exam_id": k.exam_id, "passing_pct": k.passing_pct,
                "negative_marking": k.negative_marking, "items": k.items}

    # ---------- objective grading (deterministic) ----------
    def _grade_objective(self, item: dict, response, neg: float):
        qtype, weight = item["type"], item["weight"]
        resp = response or {}
        if qtype in ("mcq", "true_false"):
            correct = resp.get("option") == item.get("correct", {}).get("option")
        elif qtype == "multi":
            correct = set(resp.get("options") or []) == set(item.get("correct", {}).get("options") or [])
        else:
            correct = False
        awarded = weight if correct else -neg
        return awarded, weight, correct

    # ---------- coding grading (execute against ALL cases, proportional) ----------
    def _run_coding(self, language: str, code: str, cases: list):
        """Return (passed, total, system_error). Retries transient failures so a
        blip never costs a student marks; a genuine student error (wrong output,
        compile fail) is NOT a system error — it just fails those cases."""
        attempts = 3
        for i in range(attempts):
            try:
                resp = _CODE.post("platform-coding", "/drive/v1/coding/run-adhoc",
                                  {"language": language, "code": code, "cases": cases})
                d = (resp or {}).get("data") or {}
                # A valid 200 response (even compile_failed) is a real result.
                return int(d.get("passed", 0)), int(d.get("total", len(cases))), False
            except Exception as exc:  # noqa: BLE001 — transient/system failure
                log.warning("coding run attempt %d/%d failed: %s", i + 1, attempts, exc)
        return 0, len(cases), True

    def _grade_coding(self, item: dict, response) -> dict:
        weight = item["weight"]
        cases = item.get("cases") or []
        resp = response or {}
        code = (resp.get("code") or "").strip()
        if not code:
            return {"awarded": 0.0, "max": weight, "correct": False,
                    "needs_review": False, "detail": "no submission"}
        if not cases:
            # No test cases to grade against — do NOT guess; hold for review.
            return {"awarded": None, "max": weight, "correct": False,
                    "needs_review": True, "detail": "no test cases configured"}
        language = resp.get("language") or item.get("language") or "python"
        passed, total, sys_err = self._run_coding(language, code, cases)
        if sys_err:
            # System couldn't execute — never auto-zero a student for this.
            return {"awarded": None, "max": weight, "correct": False,
                    "needs_review": True, "detail": "execution unavailable — manual review"}
        awarded = round(weight * passed / total, 2) if total else 0.0
        return {"awarded": awarded, "max": weight, "correct": passed == total,
                "needs_review": False, "detail": f"{passed}/{total} cases passed",
                "passed": passed, "total": total}

    def run(self, s: Session, data) -> dict:
        key = s.get(AnswerKey, data.exam_id)
        if not key:
            raise NotFound("No answer key for exam", code="key_not_found")

        q_scores = []
        total = 0.0
        max_score = 0.0
        gradable = 0
        correct_count = 0
        attempted = 0
        needs_review = False
        for item in key.items:
            qid, qtype, weight = item["question_id"], item["type"], item["weight"]
            resp = data.answers.get(qid)
            did_attempt = _attempted(resp)
            if did_attempt:
                attempted += 1
            if qtype == "coding":
                g = self._grade_coding(item, resp)
                if g["needs_review"]:
                    # Exclude from the auto total/max so a system fault can never
                    # lower the score; a human finalises this item.
                    needs_review = True
                    q_scores.append({"question_id": qid, "type": "coding", "awarded": None,
                                     "max": weight, "correct": False, "needs_review": True,
                                     "attempted": did_attempt, "detail": g["detail"]})
                    continue
                total += g["awarded"]
                max_score += weight
                gradable += 1
                if g["correct"]:
                    correct_count += 1
                q_scores.append({"question_id": qid, "type": "coding", "awarded": g["awarded"],
                                 "max": weight, "correct": g["correct"], "attempted": did_attempt,
                                 "detail": g["detail"]})
            else:
                awarded, w, correct = self._grade_objective(item, resp, key.negative_marking)
                total += awarded
                max_score += w
                gradable += 1
                if correct:
                    correct_count += 1
                q_scores.append({"question_id": qid, "type": qtype, "awarded": round(awarded, 2),
                                 "max": w, "correct": correct, "attempted": did_attempt})

        total = max(0.0, round(total, 2))
        percentage = round(total * 100.0 / max_score, 1) if max_score else 0.0
        accuracy = round(correct_count * 100.0 / gradable, 1) if gradable else 0.0
        passed = percentage >= key.passing_pct

        ev = s.execute(
            select(Evaluation).where(Evaluation.session_id == data.session_id)
        ).scalar_one_or_none()
        if ev is None:
            ev = Evaluation(id=new_id(), exam_id=data.exam_id, session_id=data.session_id,
                            candidate_id=data.candidate_id)
            s.add(ev)
        else:
            ev.version += 1  # re-evaluation preserves prior via version bump
        ev.total = total
        ev.max_score = max_score
        ev.percentage = percentage
        ev.accuracy = accuracy
        ev.passed = passed
        ev.needs_review = needs_review
        ev.question_scores = q_scores
        s.flush()
        return self.out(ev)

    def get(self, s: Session, session_id: str) -> dict:
        ev = s.execute(
            select(Evaluation).where(Evaluation.session_id == session_id)
        ).scalar_one_or_none()
        if not ev:
            raise NotFound("Evaluation not found", code="evaluation_not_found")
        return self.out(ev)

    # ---------- Cognitive Twin v0.1: per-learner skill profile ----------
    def _question_meta(self, qids: list[str]) -> dict:
        """qid -> {category, difficulty, tags} from the Question Bank."""
        if not qids:
            return {}
        try:
            resp = _QB.post("drive-questionbank", "/drive/v1/questions/meta", {"ids": qids})
            items = (resp or {}).get("data") or []
            return {it["id"]: it for it in items}
        except Exception:  # noqa: BLE001 — twin degrades gracefully without topics
            log.warning("question-bank meta lookup failed; skill map without topics")
            return {}

    def skill_profile(self, s: Session, candidate_id: str) -> dict:
        """Build a learner's skill model from every written test they've taken:
        per-topic, per-category and per-difficulty mastery. The foundation of the
        Cognitive Twin — computed from data the platform already collects."""
        evals = s.execute(
            select(Evaluation).where(Evaluation.candidate_id == candidate_id)
        ).scalars().all()

        # Fold every question the learner has answered into attempted/correct.
        per_q: dict[str, dict] = {}
        for ev in evals:
            for qs in (ev.question_scores or []):
                qid = qs.get("qid") or qs.get("question_id")
                if not qid:
                    continue
                rec = per_q.setdefault(qid, {"attempted": 0, "correct": 0})
                rec["attempted"] += 1
                ok_flag = qs.get("correct")
                if ok_flag is None:
                    ok_flag = float(qs.get("awarded", 0) or 0) > 0
                if ok_flag:
                    rec["correct"] += 1

        meta = self._question_meta(list(per_q.keys()))

        def _bucket(store: dict, key: str, rec: dict):
            b = store.setdefault(key, {"attempted": 0, "correct": 0})
            b["attempted"] += rec["attempted"]
            b["correct"] += rec["correct"]

        by_cat, by_topic, by_diff = {}, {}, {}
        tot_a = tot_c = 0
        for qid, rec in per_q.items():
            m = meta.get(qid) or {}
            _bucket(by_cat, m.get("category") or "other", rec)
            _bucket(by_diff, m.get("difficulty") or "easy", rec)
            for tag in (m.get("tags") or []):
                _bucket(by_topic, str(tag), rec)
            tot_a += rec["attempted"]
            tot_c += rec["correct"]

        def _fmt(store: dict, sort: bool = False) -> list[dict]:
            rows = [{"name": k, "attempted": v["attempted"], "correct": v["correct"],
                     "mastery": _mastery(v["correct"], v["attempted"]),
                     "band": _band(_mastery(v["correct"], v["attempted"]))}
                    for k, v in store.items()]
            rows.sort(key=lambda r: (r["mastery"] if sort else 0, r["attempted"]), reverse=sort)
            return rows

        topics = _fmt(by_topic, sort=True)
        return {
            "candidate_id": candidate_id,
            "exams_taken": len(evals),
            "overall": {"attempted": tot_a, "correct": tot_c, "mastery": _mastery(tot_c, tot_a)},
            "by_category": _fmt(by_cat),
            "by_difficulty": _fmt(by_diff),
            "strengths": [t for t in topics if t["band"] == "strong"][:6],
            "focus_areas": sorted(
                [t for t in topics if t["band"] in ("weak", "developing")],
                key=lambda r: r["mastery"])[:6],
            "topics": topics,
        }

    def compute_ranks(self, s: Session, exam_id: str) -> list[dict]:
        evals = s.execute(
            select(Evaluation).where(Evaluation.exam_id == exam_id)
        ).scalars().all()
        # Tie-breakers: percentage desc, accuracy desc, candidate_id asc (stable).
        ordered = sorted(evals, key=lambda e: (-e.percentage, -e.accuracy, e.candidate_id))
        # Batch-load existing ranks in ONE query (was a SELECT per candidate — an
        # N+1 that times out over a remote DB with hundreds of candidates).
        existing = {r.candidate_id: r for r in s.execute(
            select(Rank).where(Rank.exam_id == exam_id)).scalars().all()}
        out = []
        for i, e in enumerate(ordered):
            tie = f"pct={e.percentage},acc={e.accuracy}"
            r = existing.get(e.candidate_id)
            if r is None:
                r = Rank(id=new_id(), exam_id=exam_id, candidate_id=e.candidate_id,
                         rank=i + 1, percentage=e.percentage, tie_break=tie)
                s.add(r)
                existing[e.candidate_id] = r
            else:
                r.rank = i + 1
                r.percentage = e.percentage
                r.tie_break = tie
            out.append({"rank": i + 1, "candidate_id": e.candidate_id,
                        "percentage": e.percentage, "accuracy": e.accuracy})
        s.flush()
        return out

    def difficulty(self, s: Session, exam_id: str) -> list[dict]:
        evals = s.execute(
            select(Evaluation).where(Evaluation.exam_id == exam_id)
        ).scalars().all()
        stats: dict[str, list[int]] = {}
        for e in evals:
            for qs in e.question_scores:
                agg = stats.setdefault(qs["question_id"], [0, 0])  # [correct, attempts]
                agg[1] += 1
                if qs["correct"]:
                    agg[0] += 1
        out = []
        for qid, (correct, attempts) in stats.items():
            ratio = round(correct / attempts, 2) if attempts else 0.0
            level = "hard" if ratio < 0.4 else ("medium" if ratio < 0.75 else "easy")
            out.append({"question_id": qid, "attempts": attempts,
                        "correct_ratio": ratio, "difficulty_index": round(1 - ratio, 2),
                        "observed_level": level})
        return sorted(out, key=lambda x: -x["difficulty_index"])

    @staticmethod
    def out(ev: Evaluation) -> dict:
        qs = ev.question_scores or []
        total_questions = len(qs)
        correct_count = sum(1 for q in qs if q.get("correct"))
        attempted_count = sum(1 for q in qs if q.get("attempted"))
        coding = [q for q in qs if q.get("type") == "coding"]
        coding_total = len(coding)
        coding_attempted = sum(1 for q in coding if q.get("attempted"))
        coding_correct = sum(1 for q in coding if q.get("correct"))
        return {"id": ev.id, "exam_id": ev.exam_id, "session_id": ev.session_id,
                "candidate_id": ev.candidate_id, "total": ev.total, "max_score": ev.max_score,
                "percentage": ev.percentage, "accuracy": ev.accuracy, "passed": ev.passed,
                "needs_review": ev.needs_review, "version": ev.version,
                "total_questions": total_questions, "correct_count": correct_count,
                "attempted_count": attempted_count, "coding_total": coding_total,
                "coding_attempted": coding_attempted, "coding_correct": coding_correct,
                "question_scores": ev.question_scores}
